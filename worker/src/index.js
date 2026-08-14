// GeloTech-Tool auth proxy Worker.
//
// Secret bindings (wrangler secret put):
//   GITHUB_TOKEN        fine-grained PAT with Contents read/write on the repo
//   SMTP_PASSWORD       SMTP app password
//   ADMIN_SECRET_PHRASE admin unlock phrase (checked here, server-side)
// Plain vars (wrangler.jsonc):
//   REPO_OWNER, REPO_NAME, REPO_BRANCH, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_FROM
//
// Routes:
//   GET  /health                     liveness
//   GET  /accounts                   full user registry (parity with old client fetch)
//   POST /login        {email,password}   PBKDF2 verify, blocked check
//   POST /register     {email}            create/reset password, email it
//   POST /admin/block  {phrase,email,blocked}   maintainer block/unblock
//
// The Worker never exposes or returns the GITHUB_TOKEN. All writes are
// allowlisted to secret.json via mutateSecret.

import { connect } from "cloudflare:sockets";
import {
  hashPassword,
  verifyPassword,
  generatePassword,
  isValidEmail,
  constantTimeEqual,
} from "./crypto.js";
import { fetchSecret, mutateSecret } from "./github.js";
import { buildEmail, sendEmail } from "./smtp.js";

const VERSION = "1.0.0";

// ---------------------------------------------------------------- rate limit
// In-memory sliding window (per isolate). Good enough as a first line of
// defense; add Cloudflare dashboard rate-limiting rules for hard guarantees.
const buckets = new Map();

function rateLimit(env, key, limit, windowMs) {
  if (!env.ENABLE_RATE_LIMIT || env.ENABLE_RATE_LIMIT === "false") return { ok: true };
  const now = Date.now();
  const entry = buckets.get(key);
  const windowStart = now - windowMs;
  const hits = entry ? entry.filter((t) => t > windowStart) : [];
  hits.push(now);
  buckets.set(key, hits);
  if (buckets.size > 10000) {
    for (const [k, v] of buckets) {
      if (v[v.length - 1] < windowStart) buckets.delete(k);
    }
  }
  if (hits.length > limit) return { ok: false, retryIn: windowMs };
  return { ok: true };
}

// ---------------------------------------------------------------- helpers

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

function clientIp(request) {
  return request.headers.get("CF-Connecting-IP") || "unknown";
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    return null;
  }
}

function accountInfo(user) {
  return {
    permissions: user.permissions ?? [],
    tabs: user.tabs ?? [],
    blocked: Boolean(user.blocked),
  };
}

// ---------------------------------------------------------------- handlers

async function handleHealth() {
  return json({ ok: true, service: "gelotech-auth-proxy", version: VERSION });
}

async function handleAccounts(env, request, fetchImpl) {
  const rl = rateLimit(env, `accounts|${clientIp(request)}`, 120, 60000);
  if (!rl.ok) return json({ ok: false, error: "Too many requests" }, 429);
  try {
    const { data } = await fetchSecret(env, fetchImpl);
    return json({ ok: true, users: data.users ?? {} });
  } catch (e) {
    return json({ ok: false, error: e.message || String(e) }, 502);
  }
}

async function handleLogin(env, body, request) {
  const rl = rateLimit(env, `login|${clientIp(request)}`, 30, 60000);
  if (!rl.ok) return json({ ok: false, reason: "rate-limited" }, 429);
  const email = (body?.email || "").trim();
  const password = body?.password || "";
  if (!email || !password) return json({ ok: false, reason: "invalid-request" }, 400);
  try {
    const { data } = await fetchSecret(env);
    const user = (data.users ?? {})[email];
    if (!user) return json({ ok: false, reason: "invalid-credentials" }, 200);
    if (user.blocked) return json({ ok: false, reason: "blocked" }, 200);
    const good = await verifyPassword(password, user.hash);
    if (!good) return json({ ok: false, reason: "invalid-credentials" }, 200);
    return json({ ok: true, user: accountInfo(user) });
  } catch (e) {
    return json({ ok: false, reason: "server-error", error: e.message || String(e) }, 502);
  }
}

async function handleRegister(env, body, request) {
  const email = (body?.email || "").trim().toLowerCase();
  if (!isValidEmail(email)) return json({ ok: false, message: "Invalid email address." });
  const rlIp = rateLimit(env, `register|${clientIp(request)}`, 5, 600000);
  if (!rlIp.ok) return json({ ok: false, message: "Too many registration attempts. Try again later." }, 429);
  const rlEmail = rateLimit(env, `register-email|${email}`, 3, 600000);
  if (!rlEmail.ok) return json({ ok: false, message: "Too many attempts for this email. Try again later." }, 429);

  const password = generatePassword(14);
  const hash = await hashPassword(password);
  const result = await mutateSecret(
    env,
    (data) => {
      const users = data.users ?? {};
      users[email] = { ...(users[email] || {}), hash };
      data.users = users;
      return data;
    },
    `Account update for ${email} (self-service)`
  );
  if (!result.ok) return json({ ok: false, message: result.error || "Could not save account." }, 502);

  const mailResult = await sendEmail(env, buildEmail({
    to: email,
    from: env.SMTP_FROM || env.SMTP_USER,
    subject: "GeloTech-Tool account credentials",
    body:
      `Hello,\n\n` +
      `Your GeloTech-Tool sign-in email: ${email}\n` +
      `Your one-time password: ${password}\n\n` +
      `You can change it anytime via the Sign-up / Password reset dialog.\n\n` +
      `GeloTech-Tool support`,
  }), { connect });
  if (!mailResult.ok) return json({ ok: false, message: "Account saved but the email could not be sent." }, 502);
  return json({ ok: true, message: "Password sent to your email. Check your inbox (and spam)." });
}

async function handleAdminBlock(env, body) {
  const phrase = body?.phrase || "";
  if (!env.ADMIN_SECRET_PHRASE || !constantTimeEqual(phrase, env.ADMIN_SECRET_PHRASE)) {
    return json({ ok: false, error: "Invalid admin credentials." }, 403);
  }
  const email = (body?.email || "").trim();
  const blocked = Boolean(body?.blocked);
  if (!email) return json({ ok: false, error: "Missing email." }, 400);
  const action = blocked ? "block" : "unblock";
  const result = await mutateSecret(
    env,
    (data) => {
      const users = data.users ?? {};
      if (!users[email]) return data;
      users[email] = { ...users[email], blocked: blocked || undefined };
      data.users = users;
      return data;
    },
    `Account ${action} for ${email} (maintainer)`
  );
  if (!result.ok) return json({ ok: false, error: result.error || "Write failed." }, 502);
  return json({ ok: true });
}

// ---------------------------------------------------------------- router

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    try {
      if (request.method === "GET" && path === "/health") return handleHealth();
      if (request.method === "GET" && path === "/accounts") return handleAccounts(env, request);
      if (request.method === "POST" && path === "/login") {
        const body = await readJson(request);
        if (!body) return json({ ok: false, reason: "invalid-request" }, 400);
        return handleLogin(env, body, request);
      }
      if (request.method === "POST" && path === "/register") {
        const body = await readJson(request);
        if (!body) return json({ ok: false, message: "invalid-request" }, 400);
        return handleRegister(env, body, request);
      }
      if (request.method === "POST" && path === "/admin/block") {
        const body = await readJson(request);
        if (!body) return json({ ok: false, error: "invalid-request" }, 400);
        return handleAdminBlock(env, body);
      }
      return json({ ok: false, error: "Not found" }, 404);
    } catch (e) {
      return json({ ok: false, error: e.message || String(e) }, 500);
    }
  },
};