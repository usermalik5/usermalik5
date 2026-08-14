// Short-lived signed session tokens, issued and verified server-side only.
//
// Token shape: <base64url(payload)>.<base64url(HMAC-SHA256 over payload)>
// Payload: { sub, role, iat, exp, jti } — subject, role, timestamps and a
// random session id. No passwords, no hashes, no reusable secrets inside.
// Signed with the SESSION_SECRET Worker secret (wrangler secret put), so
// the client cannot forge or tamper with sessions, and expiry is enforced
// on every verification.

import { bytesToHex, constantTimeEqual } from "./crypto.js";

const enc = new TextEncoder();
const dec = new TextDecoder();

function b64u(bytes) {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function unb64u(text) {
  const b64 = text.replace(/-/g, "+").replace(/_/g, "/");
  const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
}

async function hmacKey(secret) {
  return crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
}

const DEFAULT_TTL_MS = 12 * 60 * 60 * 1000; // 12 hours

export async function signSession(secret, { sub, role }, ttlMs = DEFAULT_TTL_MS) {
  const now = Date.now();
  const payload = {
    sub,
    role,
    iat: now,
    exp: now + ttlMs,
    jti: bytesToHex(crypto.getRandomValues(new Uint8Array(16))),
  };
  const body = b64u(enc.encode(JSON.stringify(payload)));
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", await hmacKey(secret), enc.encode(body)));
  return `${body}.${b64u(sig)}`;
}

// Returns the validated payload, or null for missing/malformed/tampered/
// expired tokens. Always fail-closed (null) when the secret is unset.
export async function verifySession(secret, token) {
  if (!secret || typeof token !== "string") return null;
  const dot = token.indexOf(".");
  if (dot <= 0 || dot === token.length - 1) return null;
  if (token.indexOf(".", dot + 1) !== -1) return null;
  const body = token.slice(0, dot);
  const sigPart = token.slice(dot + 1);
  try {
    const expected = new Uint8Array(await crypto.subtle.sign("HMAC", await hmacKey(secret), enc.encode(body)));
    if (!constantTimeEqual(bytesToHex(expected), bytesToHex(unb64u(sigPart)))) return null;
    const payload = JSON.parse(dec.decode(unb64u(body)));
    if (!payload || typeof payload !== "object") return null;
    if (typeof payload.exp !== "number" || payload.exp <= Date.now()) return null;
    if (typeof payload.sub !== "string" || !payload.sub || payload.sub.length > 254) return null;
    if (payload.role !== "admin" && payload.role !== "user") return null;
    return payload;
  } catch {
    return null;
  }
}
