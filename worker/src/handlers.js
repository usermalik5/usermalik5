// Route handlers + request plumbing for the auth proxy Worker.
//
// Deliberately free of `cloudflare:` imports so every route is unit-testable
// in plain Node: the fetch implementation and the sockets factory are passed
// in via `deps` from src/index.js (which owns the cloudflare imports).
//
// Security model (enforced HERE, not in the client):
//   - password verification is server-side only (PBKDF2, constant-time)
//   - admin identity comes from the user registry (role "admin"), never
//     from anything the client types besides the admin account credentials
//   - every privileged operation requires a valid signed admin session
//     (Authorization: Bearer), issued by POST /login and expiring
//   - GET /accounts returns a sanitized registry (no hashes, no secrets)
//   - POST /admin/block takes {email, blocked} and a session, never a phrase
//   - GET /files/<name> serves only a fixed allowlist of public update
//     files (the GITHUB_TOKEN never leaves this Worker)
//   - every error returned to clients is generic: no stack traces, no
//     GitHub API details, no secret material
//
// Secret bindings (wrangler secret put):
//   GITHUB_TOKEN        fine-grained PAT: Contents read/write, this repo only
//   SMTP_PASSWORD       SMTP app password
//   SESSION_SECRET      HMAC key for signing login sessions
// Plain vars (wrangler.jsonc):
//   REPO_OWNER, REPO_NAME, REPO_BRANCH, SMTP_HOST, SMTP_PORT, SMTP_USER,
//   SMTP_FROM, ENABLE_RATE_LIMIT

import {
  hashPassword,
  verifyPassword,
  generatePassword,
  isValidEmail,
} from "./crypto.js";
import { fetchSecret, mutateSecret, fetchFile, isPublicFile } from "./github.js";
import { buildEmail, sendEmail } from "./smtp.js";
import { signSession, verifySession } from "./session.js";

const VERSION = "2.0.0";
const MAX_BODY_BYTES = 16 * 1024; // login/register/block payloads are tiny
const MAX_EMAIL_LEN = 254;
const MAX_PASSWORD_LEN = 256;

// ---------------------------------------------------------------- rate limit
// In-memory sliding window (per isolate). This is a FIRST LINE of defense
// only: Workers isolates do not share state, so this cannot be a global
// counter. Cloudflare-native rate limiting must be configured on the
// Worker (see worker/README.md, "Rate limiting"): that is the hard
// guarantee. Do not claim the Map is global protection.
const buckets = new Map();

// Per-route limits can be tuned with Worker vars (e.g. LOGIN_RATE_LIMIT);
// defaults keep login/register/admin aggressive.
function lim(env, key, def) {
  const v = Number(env[key]);
  return Number.isFinite(v) && v >= 0 ? v : def;
}

export function rateLimit(env, key, limit, windowMs) {
  if (!env.ENABLE_RATE_LIMIT || env.ENABLE_RATE_LIMIT === "false") return { ok: true };
  const now = Date.now();
  const windowStart = now - windowMs;
  const entry = buckets.get(key);
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

function bearerToken(request) {
  const auth = request.headers.get("Authorization") || "";
  const m = /^Bearer\s+(.+)$/i.exec(auth.trim());
  return m ? m[1].trim() : "";
}

// Reads and parses a JSON body with a hard size cap. Returns
// { ok: true, body } or { ok: false, status, error }.
async function readJsonBody(request) {
  const contentType = (request.headers.get("Content-Type") || "").toLowerCase();
  if (!contentType.startsWith("application/json")) {
    return { ok: false, status: 400, error: "Content-Type must be application/json." };
  }
  let text;
  try {
    text = await request.text();
  } catch {
    return { ok: false, status: 400, error: "Unreadable request body." };
  }
  if (text.length > MAX_BODY_BYTES) {
    return { ok: false, status: 413, error: "Request body too large." };
  }
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    return { ok: false, status: 400, error: "Invalid JSON body." };
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { ok: false, status: 400, error: "Invalid JSON body." };
  }
  return { ok: true, body };
}

// Resolves the current session. Returns { ok: true, session } or
// { ok: false, response } with a generic 401/403 response.
async function requireAdminSession(env, request) {
  const session = await verifySession(env.SESSION_SECRET, bearerToken(request));
  if (!session) {
    return { ok: false, response: json({ ok: false, error: "Authentication required." }, 401) };
  }
  if (session.role !== "admin") {
    return { ok: false, response: json({ ok: false, error: "Admin access required." }, 403) };
  }
  return { ok: true, session };
}

function accountInfo(user) {
  return {
    permissions: user.permissions ?? [],
    tabs: user.tabs ?? [],
    blocked: Boolean(user.blocked),
  };
}

function sanitizedUsers(users) {
  const out = {};
  for (const [email, u] of Object.entries(users || {})) {
    if (!u || typeof u !== "object") continue;
    out[email] = accountInfo(u);
  }
  return out;
}

// ---------------------------------------------------------------- handlers

async function handleHealth() {
  return json({ ok: true, service: "gelotech-auth-proxy", version: VERSION });
}

async function handleFiles(env, request, deps, name) {
  const rl = rateLimit(env, `files|${clientIp(request)}`, lim(env, "FILES_RATE_LIMIT", 300), 60000);
  if (!rl.ok) return json({ ok: false, error: "Too many requests" }, 429);
  const decoded = decodeURIComponent(name);
  if (!isPublicFile(decoded)) return json({ ok: false, error: "Not found" }, 404);
  try {
    const bytes = await fetchFile(env, decoded, deps.fetchImpl);
    const contentType = decoded.endsWith(".sig") ? "text/plain; charset=utf-8" : "application/json; charset=utf-8";
    return new Response(bytes, {
      status: 200,
      headers: { "Content-Type": contentType, "Cache-Control": "public, max-age=60" },
    });
  } catch {
    return json({ ok: false, error: "File fetch failed." }, 502);
  }
}

async function handleLogin(env, body, request, deps) {
  const rl = rateLimit(env, `login|${clientIp(request)}`, lim(env, "LOGIN_RATE_LIMIT", 30), 60000);
  if (!rl.ok) return json({ ok: false, reason: "rate-limited" }, 429);
  const email = typeof body.email === "string" ? body.email.trim() : "";
  const password = typeof body.password === "string" ? body.password : "";
  if (!email || email.length > MAX_EMAIL_LEN || !password || password.length > MAX_PASSWORD_LEN) {
    return json({ ok: false, reason: "invalid-request" }, 400);
  }
  try {
    const { data } = await fetchSecret(env, deps.fetchImpl);
    const user = (data.users ?? {})[email];
    // Generic failure for unknown account vs wrong password: never reveal
    // whether an email is registered.
    if (!user) return json({ ok: false, reason: "invalid-credentials" }, 200);
    if (user.blocked) return json({ ok: false, reason: "blocked" }, 200);
    const good = await verifyPassword(password, user.hash);
    if (!good) return json({ ok: false, reason: "invalid-credentials" }, 200);
    const role = user.role === "admin" || email === "admin" ? "admin" : "user";
    if (!env.SESSION_SECRET) return json({ ok: false, reason: "server-error" }, 503);
    let session = null;
    try {
      session = await signSession(env.SESSION_SECRET, { sub: email, role });
    } catch {
      return json({ ok: false, reason: "server-error" }, 503);
    }
    return json({ ok: true, user: { role, ...accountInfo(user) }, session });
  } catch {
    return json({ ok: false, reason: "server-error" }, 502);
  }
}

async function handleRegister(env, body, request, deps) {
  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  if (!email || email.length > MAX_EMAIL_LEN || !isValidEmail(email)) {
    return json({ ok: false, message: "Invalid email address." });
  }
  const rlIp = rateLimit(env, `register|${clientIp(request)}`, lim(env, "REGISTER_IP_RATE_LIMIT", 5), 600000);
  if (!rlIp.ok) return json({ ok: false, message: "Too many registration attempts. Try again later." }, 429);
  const rlEmail = rateLimit(env, `register-email|${email}`, lim(env, "REGISTER_EMAIL_RATE_LIMIT", 3), 600000);
  if (!rlEmail.ok) return json({ ok: false, message: "Too many attempts for this email. Try again later." }, 429);

  // CSPRNG-generated password; hashed before it is persisted, emailed to the
  // user, and never logged or written to commit messages.
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
    `Account update for ${email} (self-service)`,
    deps.fetchImpl
  );
  if (!result.ok) return json({ ok: false, message: "Could not save account." }, 502);

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
  }), deps.io);
  if (!mailResult.ok) return json({ ok: false, message: "Account saved but the email could not be sent." }, 502);
  return json({ ok: true, message: "Password sent to your email. Check your inbox (and spam)." });
}

async function handleAccounts(env, request, deps) {
  const rl = rateLimit(env, `accounts|${clientIp(request)}`, lim(env, "ACCOUNTS_RATE_LIMIT", 120), 60000);
  if (!rl.ok) return json({ ok: false, error: "Too many requests" }, 429);
  const auth = await requireAdminSession(env, request);
  if (!auth.ok) return auth.response;
  try {
    const { data } = await fetchSecret(env, deps.fetchImpl);
    return json({ ok: true, users: sanitizedUsers(data.users) });
  } catch {
    return json({ ok: false, error: "Registry read failed." }, 502);
  }
}

async function handleAdminBlock(env, request, deps, body) {
  const rl = rateLimit(env, `admin-block|${clientIp(request)}`, lim(env, "ADMIN_BLOCK_RATE_LIMIT", 30), 60000);
  if (!rl.ok) return json({ ok: false, error: "Too many requests" }, 429);
  const auth = await requireAdminSession(env, request);
  if (!auth.ok) return auth.response;
  const email = typeof body.email === "string" ? body.email.trim() : "";
  if (!email || email.length > MAX_EMAIL_LEN) return json({ ok: false, error: "Missing email." }, 400);
  if (typeof body.blocked !== "boolean") return json({ ok: false, error: "blocked must be a boolean." }, 400);
  const action = body.blocked ? "block" : "unblock";
  const result = await mutateSecret(
    env,
    (data) => {
      const users = data.users ?? {};
      if (!users[email]) return data;
      users[email] = { ...users[email], blocked: body.blocked || undefined };
      data.users = users;
      return data;
    },
    `Account ${action} for ${email} (maintainer)`,
    deps.fetchImpl
  );
  if (!result.ok) return json({ ok: false, error: "Registry write failed." }, 502);
  return json({ ok: true });
}

// ---------------------------------------------------------------- router

export async function handleRequest(request, env, deps) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  try {
    if (path === "/health") {
      if (request.method !== "GET") return json({ ok: false, error: "Method not allowed" }, 405);
      return handleHealth();
    }
    if (path === "/accounts") {
      if (request.method !== "GET") return json({ ok: false, error: "Method not allowed" }, 405);
      return handleAccounts(env, request, deps);
    }
    if (path === "/login" || path === "/register" || path === "/admin/block") {
      if (request.method !== "POST") return json({ ok: false, error: "Method not allowed" }, 405);
      const parsed = await readJsonBody(request);
      if (!parsed.ok) return json({ ok: false, error: parsed.error }, parsed.status);
      if (path === "/login") return handleLogin(env, parsed.body, request, deps);
      if (path === "/register") return handleRegister(env, parsed.body, request, deps);
      return handleAdminBlock(env, request, deps, parsed.body);
    }
    const fileMatch = /^\/files\/([^/]+)$/.exec(path);
    if (fileMatch) {
      if (request.method !== "GET") return json({ ok: false, error: "Method not allowed" }, 405);
      return handleFiles(env, request, deps, fileMatch[1]);
    }
    return json({ ok: false, error: "Not found" }, 404);
  } catch {
    // Never leak stack traces / internal details to clients.
    return json({ ok: false, error: "Internal server error" }, 500);
  }
}
