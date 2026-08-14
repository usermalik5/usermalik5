import { test } from "node:test";
import assert from "node:assert/strict";
import { handleRequest } from "./handlers.js";
import { hashPassword } from "./crypto.js";
import { signSession } from "./session.js";

// ---------------------------------------------------------------- fixtures

const env = {
  REPO_OWNER: "usermalik5",
  REPO_NAME: "GeloTech-Tool",
  REPO_BRANCH: "main",
  GITHUB_TOKEN: "REDACTED",
  SMTP_HOST: "smtp.test",
  SMTP_PORT: "587",
  SMTP_USER: "sender@test",
  SMTP_FROM: "sender@test",
  SESSION_SECRET: "test-session-secret-0123456789",
  ENABLE_RATE_LIMIT: "false",
};

async function makeState() {
  const adminHash = await hashPassword("adminpw");
  const userHash = await hashPassword("userpw");
  const blockedHash = await hashPassword("blockedpw");
  return {
    secretJson: {
      users: {
        admin: { hash: adminHash },
        "a@b.c": { hash: userHash, permissions: { mirror: true }, tabs: ["Home"] },
        "blocked@x.c": { hash: blockedHash, blocked: true },
      },
    },
    files: {
      "version.json": new TextEncoder().encode('{"database": 1, "banking": 1, "sha256": {"gelotech_database_v3.json": "abc"}}'),
      "version.json.sig": new TextEncoder().encode("c2lnbmF0dXJl"), // base64 "signature"
      "gelotech_database_v3.json": new TextEncoder().encode('{"packages": {}}'),
      "banking_apps.json": new TextEncoder().encode('{"com.example.bank": "Bank"}'),
    },
    puts: [],
  };
}

const okJson = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });

function ghFetch(state) {
  const calls = [];
  const impl = async (url, opts = {}) => {
    calls.push({ url, opts });
    if (opts.method === "PUT") {
      if (!url.includes("/contents/secret.json")) return okJson({}, 404);
      state.puts.push(JSON.parse(opts.body));
      return okJson({});
    }
    const contentsMatch = /\/contents\/([^?]+)\?ref=/.exec(url);
    if (contentsMatch) {
      const name = contentsMatch[1];
      if (name === "secret.json") {
        const content = JSON.stringify(state.secretJson, null, 2);
        return okJson({ content: btoa(content), sha: "sha-secret" });
      }
      if (state.files[name] !== undefined) {
        return okJson({ content: btoa(String.fromCharCode(...state.files[name])), sha: `sha-${name}` });
      }
    }
    const blobMatch = /\/git\/blobs\/([^/]+)/.exec(url);
    if (blobMatch && state.blobs && state.blobs[blobMatch[1]]) {
      return okJson({ content: state.blobs[blobMatch[1]] });
    }
    return okJson({ message: "not found" }, 404);
  };
  return { impl, calls };
}

// Fake SMTP server that answers a full successful conversation.
class FakeSocket {
  constructor() {
    this.responses = [
      "220 smtp.test ESMTP",
      "250 smtp.test at your service",
      "220 2.0.0 Ready to start TLS",
      "250 smtp.test at your service",
      "334 VXNlcm5hbWU6",
      "334 UGFzc3dvcmQ6",
      "235 2.7.0 Authentication successful",
      "250 2.1.0 Ok",
      "250 2.1.5 Ok",
      "354 End data with <CR><LF>.<CR><LF>",
      "250 2.0.0 Ok: queued",
      "221 2.0.0 Bye",
    ];
    this.written = [];
    this.writer = {
      getWriter: () => ({
        write: async (u8) => { this.written.push(new TextDecoder().decode(u8)); },
        close: async () => {},
      }),
    };
    this.reader = {
      getReader: () => ({
        read: async () => {
          if (!this.responses.length) return { value: new Uint8Array(), done: true };
          return { value: new TextEncoder().encode(this.responses.shift() + "\r\n"), done: false };
        },
      }),
    };
    this.closed = Promise.resolve();
  }
}

function makeIo() {
  const sockets = [];
  return {
    io: { connect: () => { const s = new FakeSocket(); sockets.push(s); return s; } },
    sockets,
  };
}

function deps(state) {
  const gh = ghFetch(state);
  const ioWrap = makeIo();
  return { fetchImpl: gh.impl, io: ioWrap.io, calls: gh.calls, sockets: ioWrap.sockets };
}

function req(path, { method = "GET", headers = {}, body, ip = "1.2.3.4" } = {}) {
  const init = { method, headers: { "CF-Connecting-IP": ip, ...headers } };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
    if (!Object.keys(init.headers).some((h) => h.toLowerCase() === "content-type")) {
      init.headers["Content-Type"] = "application/json";
    }
  }
  return new Request(`https://gelotech-auth-proxy.test${path}`, init);
}

const jsonBody = async (r) => JSON.parse(await r.text());

async function adminSession(envFor = env) {
  return signSession(envFor.SESSION_SECRET, { sub: "admin", role: "admin" });
}

async function userSession(envFor = env) {
  return signSession(envFor.SESSION_SECRET, { sub: "a@b.c", role: "user" });
}

// ---------------------------------------------------------------- health

test("health returns ok", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/health"), env, deps(state));
  assert.equal(r.status, 200);
  assert.equal((await jsonBody(r)).ok, true);
});

// ---------------------------------------------------------------- /accounts

test("GET /accounts without session -> 401", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/accounts"), env, deps(state));
  assert.equal(r.status, 401);
});

test("GET /accounts with malformed bearer -> 401", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/accounts", { headers: { Authorization: "Bearer garbage" } }), env, deps(state));
  assert.equal(r.status, 401);
});

test("GET /accounts with expired session -> 401", async () => {
  const state = await makeState();
  const token = await signSession(env.SESSION_SECRET, { sub: "admin", role: "admin" }, -1000);
  const r = await handleRequest(req("/accounts", { headers: { Authorization: `Bearer ${token}` } }), env, deps(state));
  assert.equal(r.status, 401);
});

test("GET /accounts with tampered session -> 401", async () => {
  const state = await makeState();
  const token = await adminSession();
  const [body, sig] = token.split(".");
  const flipped = sig.slice(0, -1) + (sig.endsWith("A") ? "B" : "A");
  const r = await handleRequest(req("/accounts", { headers: { Authorization: `Bearer ${body}.${flipped}` } }), env, deps(state));
  assert.equal(r.status, 401);
});

test("GET /accounts with normal-user session -> 403", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/accounts", { headers: { Authorization: `Bearer ${await userSession()}` } }), env, deps(state));
  assert.equal(r.status, 403);
});

test("GET /accounts with admin session -> 200, sanitized (no hashes)", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/accounts", { headers: { Authorization: `Bearer ${await adminSession()}` } }), env, deps(state));
  assert.equal(r.status, 200);
  const text = await r.text();
  const body = JSON.parse(text);
  assert.ok(body.ok);
  const admin = body.users.admin;
  assert.deepEqual(admin.permissions, []);
  assert.deepEqual(admin.tabs, []);
  assert.equal(admin.blocked, false);
  assert.deepEqual(body.users["a@b.c"].permissions, { mirror: true });
  assert.deepEqual(body.users["a@b.c"].tabs, ["Home"]);
  assert.equal(body.users["blocked@x.c"].blocked, true);
  assert.ok(!text.includes("hash"), "sanitized /accounts must not contain hashes");
  assert.ok(!text.includes(env.GITHUB_TOKEN), "must not leak GITHUB_TOKEN");
});

test("POST /accounts -> 405", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/accounts", { method: "POST", body: {} }), env, deps(state));
  assert.equal(r.status, 405);
});

// ---------------------------------------------------------------- /admin/block

test("POST /admin/block without session -> 401", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/admin/block", { method: "POST", body: { email: "a@b.c", blocked: true } }), env, deps(state));
  assert.equal(r.status, 401);
});

test("POST /admin/block with normal-user session -> 403", async () => {
  const state = await makeState();
  const r = await handleRequest(
    req("/admin/block", { method: "POST", body: { email: "a@b.c", blocked: true }, headers: { Authorization: `Bearer ${await userSession()}` } }),
    env, deps(state));
  assert.equal(r.status, 403);
});

test("POST /admin/block with admin session -> 200, writes secret.json", async () => {
  const state = await makeState();
  const d = deps(state);
  const r = await handleRequest(
    req("/admin/block", { method: "POST", body: { email: "a@b.c", blocked: true }, headers: { Authorization: `Bearer ${await adminSession()}` } }),
    env, d);
  assert.equal(r.status, 200);
  assert.equal((await jsonBody(r)).ok, true);
  assert.equal(state.puts.length, 1);
  assert.equal(state.puts[0].message, "Account block for a@b.c (maintainer)");
  assert.ok(!JSON.stringify(state.puts[0]).includes("phrase"), "no phrase in block request");
});

test("POST /admin/block validation: missing email -> 400, non-boolean blocked -> 400", async () => {
  const state = await makeState();
  const auth = { Authorization: `Bearer ${await adminSession()}` };
  const r1 = await handleRequest(req("/admin/block", { method: "POST", body: { blocked: true }, headers: auth }), env, deps(state));
  assert.equal(r1.status, 400);
  const r2 = await handleRequest(req("/admin/block", { method: "POST", body: { email: "a@b.c", blocked: "yes" }, headers: auth }), env, deps(state));
  assert.equal(r2.status, 400);
});

// ---------------------------------------------------------------- /login

test("login: valid admin password -> ok, role admin, session issued, no hash", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/login", { method: "POST", body: { email: "admin", password: "adminpw" } }), env, deps(state));
  assert.equal(r.status, 200);
  const body = await jsonBody(r);
  assert.equal(body.ok, true);
  assert.equal(body.user.role, "admin");
  assert.ok(body.session && body.session.includes("."));
  assert.ok(!JSON.stringify(body).includes("hash"));
});

test("login: valid normal user -> ok, role user, session issued", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/login", { method: "POST", body: { email: "a@b.c", password: "userpw" } }), env, deps(state));
  const body = await jsonBody(r);
  assert.equal(body.ok, true);
  assert.equal(body.user.role, "user");
  assert.ok(body.session);
  assert.equal(body.user.blocked, false);
});

test("login: wrong password -> generic invalid-credentials, no session", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/login", { method: "POST", body: { email: "a@b.c", password: "nope" } }), env, deps(state));
  const body = await jsonBody(r);
  assert.equal(body.ok, false);
  assert.equal(body.reason, "invalid-credentials");
  assert.equal(body.session, undefined);
});

test("login: unknown account -> generic invalid-credentials (no enumeration)", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/login", { method: "POST", body: { email: "nobody@x.c", password: "whatever" } }), env, deps(state));
  const body = await jsonBody(r);
  assert.equal(body.ok, false);
  assert.equal(body.reason, "invalid-credentials");
});

test("login: blocked account -> blocked", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/login", { method: "POST", body: { email: "blocked@x.c", password: "blockedpw" } }), env, deps(state));
  const body = await jsonBody(r);
  assert.equal(body.ok, false);
  assert.equal(body.reason, "blocked");
});

test("login: malformed request -> 400", async () => {
  const state = await makeState();
  const r1 = await handleRequest(req("/login", { method: "POST", body: { email: "a@b.c" } }), env, deps(state));
  assert.equal(r1.status, 400);
  const r2 = await handleRequest(req("/login", { method: "POST", body: { password: "x" } }), env, deps(state));
  assert.equal(r2.status, 400);
});

test("login: non-JSON content type -> 400", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/login", { method: "POST", headers: { "Content-Type": "text/plain" }, body: { email: "a@b.c", password: "x" } }), env, deps(state));
  assert.equal(r.status, 400);
});

test("login: oversized body -> 413", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/login", { method: "POST", body: { email: "a@b.c", password: "x".repeat(20000) } }), env, deps(state));
  assert.equal(r.status, 413);
});

test("login: missing SESSION_SECRET fails closed -> 503", async () => {
  const state = await makeState();
  const noSecret = { ...env, SESSION_SECRET: undefined };
  const r = await handleRequest(req("/login", { method: "POST", body: { email: "admin", password: "adminpw" } }), noSecret, deps(state));
  assert.equal(r.status, 503);
});

test("login: user-role session cannot access admin endpoints even with admin sub", async () => {
  const state = await makeState();
  const forged = await signSession(env.SESSION_SECRET, { sub: "admin", role: "user" });
  const r = await handleRequest(req("/accounts", { headers: { Authorization: `Bearer ${forged}` } }), env, deps(state));
  assert.equal(r.status, 403);
});

// ---------------------------------------------------------------- /register

test("register: invalid email rejected", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/register", { method: "POST", body: { email: "not-an-email" } }), env, deps(state));
  const body = await jsonBody(r);
  assert.equal(body.ok, false);
  assert.ok(body.message.includes("Invalid email"));
});

test("register: success emails the password, stores a hash only, no plaintext in commit", async () => {
  const state = await makeState();
  const d = deps(state);
  const r = await handleRequest(req("/register", { method: "POST", body: { email: "new@b.c" } }), env, d);
  assert.equal(r.status, 200);
  const body = await jsonBody(r);
  assert.equal(body.ok, true);
  assert.equal(state.puts.length, 1);
  const written = JSON.parse(Buffer.from(state.puts[0].content, "base64").toString());
  const stored = written.users["new@b.c"];
  assert.ok(stored && /^\d+\$[0-9a-f]{32}\$[0-9a-f]{64}$/.test(stored.hash), "stored hash must be PBKDF2 format");
  assert.ok(!("password" in stored), "no plaintext password persisted");
  assert.equal(state.puts[0].message, "Account update for new@b.c (self-service)");
  const socket = d.sockets[0];
  assert.ok(socket, "SMTP conversation happened");
  const mail = socket.written.join("");
  assert.ok(mail.includes("Your one-time password:"), "password goes only to the user's email");
  assert.ok(!mail.includes(stored.hash), "hash never leaves the Worker");
  const gitTraffic = JSON.stringify(d.calls.map((c) => ({ url: c.url, body: c.opts.body })));
  assert.ok(!gitTraffic.includes(stored.hash), "hash never sent to GitHub");
});

test("register: rate limited per IP -> 429", async () => {
  const state = await makeState();
  const rlEnv = { ...env, ENABLE_RATE_LIMIT: "true", REGISTER_IP_RATE_LIMIT: "2" };
  for (let i = 0; i < 2; i++) {
    const r = await handleRequest(req("/register", { method: "POST", body: { email: `ip${i}@b.c` } }), rlEnv, deps(state));
    assert.notEqual(r.status, 429);
  }
  const r = await handleRequest(req("/register", { method: "POST", body: { email: "ip3@b.c" } }), rlEnv, deps(state));
  assert.equal(r.status, 429);
});

test("register: rate limited per email -> 429", async () => {
  const state = await makeState();
  const rlEnv = { ...env, ENABLE_RATE_LIMIT: "true", REGISTER_EMAIL_RATE_LIMIT: "1" };
  const first = await handleRequest(req("/register", { method: "POST", body: { email: "same@b.c" } }), rlEnv, deps(state));
  assert.notEqual(first.status, 429);
  const second = await handleRequest(req("/register", { method: "POST", body: { email: "same@b.c" } }), rlEnv, deps(state));
  assert.equal(second.status, 429);
});

test("login: rate limited -> 429", async () => {
  const state = await makeState();
  const rlEnv = { ...env, ENABLE_RATE_LIMIT: "true", LOGIN_RATE_LIMIT: "2" };
  for (let i = 0; i < 2; i++) {
    const r = await handleRequest(req("/login", { method: "POST", body: { email: "a@b.c", password: "userpw" } }), rlEnv, deps(state));
    assert.notEqual(r.status, 429);
  }
  const r = await handleRequest(req("/login", { method: "POST", body: { email: "a@b.c", password: "userpw" } }), rlEnv, deps(state));
  assert.equal(r.status, 429);
});

// ---------------------------------------------------------------- /files

test("GET /files serves allowlisted files", async () => {
  const state = await makeState();
  const d = deps(state);
  const r = await handleRequest(req("/files/version.json"), env, d);
  assert.equal(r.status, 200);
  const bytes = new Uint8Array(await r.arrayBuffer());
  assert.deepEqual(bytes, state.files["version.json"]);
  const r2 = await handleRequest(req("/files/banking_apps.json"), env, d);
  assert.equal(r2.status, 200);
});

test("GET /files rejects non-allowlisted names -> 404", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/files/secret.json"), env, deps(state));
  assert.equal(r.status, 404);
  const r2 = await handleRequest(req("/files/../secret.json"), env, deps(state));
  assert.equal(r2.status, 404);
});

test("POST /files -> 405", async () => {
  const state = await makeState();
  const r = await handleRequest(req("/files/version.json", { method: "POST", body: {} }), env, deps(state));
  assert.equal(r.status, 405);
});

// ---------------------------------------------------------------- misc

test("GET /login -> 405, unknown path -> 404", async () => {
  const state = await makeState();
  const r1 = await handleRequest(req("/login"), env, deps(state));
  assert.equal(r1.status, 405);
  const r2 = await handleRequest(req("/nope"), env, deps(state));
  assert.equal(r2.status, 404);
});

test("no internal details or tokens leak in any error response", async () => {
  const state = await makeState();
  const d = deps(state);
  d.fetchImpl = async () => ({ ok: false, status: 500, json: async () => ({ message: "boom" }) });
  const r = await handleRequest(req("/login", { method: "POST", body: { email: "a@b.c", password: "userpw" } }), env, d);
  const text = await r.text();
  assert.ok(!text.includes(env.GITHUB_TOKEN), "GITHUB_TOKEN must never leak");
  assert.ok(!text.includes("github"), "no GitHub API details in client responses");
});