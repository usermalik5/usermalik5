// Minimal SMTP client over Cloudflare Workers sockets (STARTTLS for 587,
// implicit TLS for 465). The socket factory is injected via `io` so the
// conversation can be unit-tested with a fake socket in Node.

export function buildEmail({ to, subject, body, from }) {
  return {
    to,
    data: `From: ${from}\r\n` +
      `To: ${to}\r\n` +
      `Subject: ${subject}\r\n` +
      `MIME-Version: 1.0\r\n` +
      `Content-Type: text/plain; charset=UTF-8\r\n` +
      `Content-Transfer-Encoding: 7bit\r\n` +
      `\r\n` +
      body.replace(/\r?\n/g, "\r\n"),
  };
}

export async function sendEmail(env, mail, io) {
  const { connect } = io;
  const port = Number(env.SMTP_PORT || 587);
  const secureTransport = port === 465 ? "on" : "starttls";
  const socket = connect({ hostname: env.SMTP_HOST, port, secureTransport });
  const writer = socket.writer.getWriter();
  const reader = socket.reader.getReader();
  const enc = new TextEncoder();
  let buf = new Uint8Array();

  const writeLine = (line) => writer.write(enc.encode(line + "\r\n"));

  const readLine = async (timeoutMs) => {
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const nl = buf.indexOf(10);
      if (nl >= 0) {
        const line = new TextDecoder().decode(buf.slice(0, nl)).replace(/\r$/, "");
        buf = buf.slice(nl + 1);
        return line;
      }
      if (Date.now() > deadline) throw new Error("SMTP read timeout");
      const { value, done } = await reader.read();
      if (done) throw new Error("SMTP connection closed");
      const merged = new Uint8Array(buf.length + value.length);
      merged.set(buf);
      merged.set(value, buf.length);
      buf = merged;
    }
  };

  const expect = async (prefixes, timeoutMs = 30000) => {
    for (;;) {
      const line = await readLine(timeoutMs);
      if (/^\d{3}-/.test(line)) continue;
      if (prefixes.some((p) => line.startsWith(p))) return line;
      throw new Error(`SMTP unexpected response: ${line}`);
    }
  };

  const b64 = (s) => btoa(s);

  try {
    await expect(["220"]);
    await writeLine("EHLO gelotech-auth-proxy");
    await expect(["250"]);
    if (secureTransport === "starttls") {
      await writeLine("STARTTLS");
      await expect(["220"]);
      await writeLine("EHLO gelotech-auth-proxy");
      await expect(["250"]);
    }
    await writeLine("AUTH LOGIN");
    await expect(["334"]);
    await writeLine(b64(env.SMTP_USER));
    await expect(["334"]);
    await writeLine(b64(env.SMTP_PASSWORD));
    await expect(["235"]);
    await writeLine(`MAIL FROM:<${env.SMTP_FROM || env.SMTP_USER}>`);
    await expect(["250"]);
    await writeLine(`RCPT TO:<${mail.to}>`);
    await expect(["250", "251"]);
    await writeLine("DATA");
    await expect(["354"]);
    const stuffed = mail.data.replace(/^\./gm, "..");
    await writer.write(enc.encode(stuffed + "\r\n.\r\n"));
    await expect(["250"]);
    await writeLine("QUIT");
    await expect(["221"]);
    await writer.close();
    await socket.closed?.catch(() => {});
    return { ok: true };
  } catch (e) {
    try { await writer.close(); } catch { /* ignore */ }
    return { ok: false, error: e.message || String(e) };
  }
}