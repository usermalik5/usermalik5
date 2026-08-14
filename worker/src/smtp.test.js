import { test } from "node:test";
import assert from "node:assert/strict";
import { sendEmail, buildEmail } from "./smtp.js";

const env = {
  SMTP_HOST: "smtp.gmail.com",
  SMTP_PORT: "587",
  SMTP_USER: "user@gmail.com",
  SMTP_PASSWORD: "app-password",
  SMTP_FROM: "user@gmail.com",
};

function fakeSocket({ responses, onConnect, onWrite }) {
  const sent = [];
  let readIndex = 0;
  const socket = {
    closed: Promise.resolve(),
    writer: {
      getWriter: () => ({
        write: (chunk) => {
          sent.push(Buffer.from(chunk).toString("utf8"));
          onWrite?.();
          return Promise.resolve();
        },
        close: () => Promise.resolve(),
      }),
    },
    reader: {
      getReader: () => ({
        read: async () => {
          if (readIndex >= responses.length) {
            return { value: undefined, done: true };
          }
          const chunk = responses[readIndex++];
          return { value: Buffer.from(chunk), done: false };
        },
      }),
    },
  };
  const factory = (opts) => {
    onConnect?.(opts);
    return socket;
  };
  return { io: { connect: factory }, sent };
}

const transcript = (sent) => sent.join("");

const GMAIL_RESPONSES = [
  "220 smtp.gmail.com ESMTP at your service\r\n",
  "250-smtp.gmail.com at your service\r\n250-SIZE 35882577\r\n250-8BITMIME\r\n250 OK\r\n",
  "220 2.0.0 Ready to start TLS\r\n",
  "250-smtp.gmail.com at your service\r\n250 OK\r\n",
  "334 VXNlcm5hbWU6\r\n",
  "334 UGFzc3dvcmQ6\r\n",
  "235 2.7.0 Accepted\r\n",
  "250 2.1.0 OK\r\n",
  "250 2.1.5 OK\r\n",
  "354 Go ahead\r\n",
  "250 2.0.0 OK 1723 qp-google-smtp-in.l.google.com\r\n",
  "221 2.0.0 closing connection\r\n",
];

test("full STARTTLS conversation succeeds", async () => {
  const { io, sent } = fakeSocket({ responses: GMAIL_RESPONSES });
  const result = await sendEmail(env, buildEmail({
    to: "target@example.com",
    from: env.SMTP_FROM,
    subject: "GeloTech-Tool account credentials",
    body: "Hello\nYour one-time password: abc123\nThanks",
  }), io);
  assert.deepEqual(result, { ok: true });
  const t = transcript(sent);
  assert.ok(t.startsWith("EHLO gelotech-auth-proxy\r\n"));
  assert.ok(t.includes("STARTTLS\r\n"));
  assert.ok(t.includes(`AUTH LOGIN\r\n${btoa(env.SMTP_USER)}\r\n${btoa(env.SMTP_PASSWORD)}\r\n`));
  assert.ok(t.includes(`MAIL FROM:<${env.SMTP_FROM}>\r\n`));
  assert.ok(t.includes("RCPT TO:<target@example.com>\r\n"));
  assert.ok(t.includes("DATA\r\n"));
  assert.ok(t.includes("Subject: GeloTech-Tool account credentials\r\n"));
  assert.ok(t.includes("Your one-time password: abc123\r\n"));
  assert.ok(t.endsWith("\r\n.\r\nQUIT\r\n"));
});

test("port 465 uses implicit TLS (secureTransport on, no STARTTLS)", async () => {
  const connectOpts = [];
  const { io, sent } = fakeSocket({
    responses: [
      "220 smtp.gmail.com ESMTP\r\n",
      "250-smtp.gmail.com at your service\r\n250 OK\r\n",
      "334 VXNlcm5hbWU6\r\n",
      "334 UGFzc3dvcmQ6\r\n",
      "235 2.7.0 Accepted\r\n",
      "250 2.1.0 OK\r\n",
      "250 2.1.5 OK\r\n",
      "354 Go ahead\r\n",
      "250 2.0.0 OK\r\n",
      "221 2.0.0 closing connection\r\n",
    ],
    onConnect: (o) => connectOpts.push(o),
  });
  const result = await sendEmail({ ...env, SMTP_PORT: "465" }, buildEmail({
    to: "t@e.com",
    from: env.SMTP_FROM,
    subject: "s",
    body: "b",
  }), io);
  assert.deepEqual(result, { ok: true });
  assert.equal(connectOpts[0].secureTransport, "on");
  assert.ok(!transcript(sent).includes("STARTTLS"));
});

test("auth rejection returns ok:false with the SMTP response", async () => {
  const { io } = fakeSocket({
    responses: [
      "220 smtp.gmail.com ESMTP\r\n",
      "250-smtp.gmail.com at your service\r\n250 OK\r\n",
      "220 2.0.0 Ready to start TLS\r\n",
      "250-smtp.gmail.com at your service\r\n250 OK\r\n",
      "334 VXNlcm5hbWU6\r\n",
      "334 UGFzc3dvcmQ6\r\n",
      "535 5.7.8 Username and Password not accepted.\r\n",
    ],
  });
  const result = await sendEmail(env, buildEmail({
    to: "t@e.com",
    from: env.SMTP_FROM,
    subject: "s",
    body: "b",
  }), io);
  assert.equal(result.ok, false);
  assert.ok(result.error.includes("535"));
});

test("dot-stuffing on lines starting with a dot", async () => {
  const { io, sent } = fakeSocket({ responses: GMAIL_RESPONSES });
  await sendEmail(env, buildEmail({
    to: "t@e.com",
    from: env.SMTP_FROM,
    subject: "s",
    body: ".hidden line\nnormal",
  }), io);
  const t = transcript(sent);
  assert.ok(t.includes("..hidden line\r\n"));
  assert.ok(t.includes("normal\r\n"));
});