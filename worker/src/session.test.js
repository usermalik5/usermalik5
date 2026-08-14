import { test } from "node:test";
import assert from "node:assert/strict";
import { signSession, verifySession } from "./session.js";

const SECRET = "test-session-secret-0123456789";

test("sign + verify roundtrip carries subject and role", async () => {
  const token = await signSession(SECRET, { sub: "admin", role: "admin" });
  const payload = await verifySession(SECRET, token);
  assert.equal(payload.sub, "admin");
  assert.equal(payload.role, "admin");
  assert.ok(payload.iat > 0);
  assert.ok(payload.exp > payload.iat);
  assert.ok(payload.jti);
  assert.notEqual(payload.jti, await verifySession(SECRET, await signSession(SECRET, { sub: "admin", role: "admin" })).then((p) => p.jti));
});

test("expired session is rejected", async () => {
  const token = await signSession(SECRET, { sub: "admin", role: "admin" }, -1000);
  assert.equal(await verifySession(SECRET, token), null);
});

test("tampered payload is rejected", async () => {
  const token = await signSession(SECRET, { sub: "admin", role: "admin" });
  const [body, sig] = token.split(".");
  const decoded = Buffer.from(body.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString();
  const payload = JSON.parse(decoded);
  payload.role = "user";
  payload.sub = "attacker@evil.test";
  const tampered = Buffer.from(JSON.stringify(payload)).toString("base64")
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  assert.equal(await verifySession(SECRET, `${tampered}.${sig}`), null);
});

test("tampered signature is rejected", async () => {
  const token = await signSession(SECRET, { sub: "admin", role: "admin" });
  const [body, sig] = token.split(".");
  const flipped = sig.slice(0, -1) + (sig.endsWith("A") ? "B" : "A");
  assert.equal(await verifySession(SECRET, `${body}.${flipped}`), null);
});

test("malformed tokens are rejected", async () => {
  assert.equal(await verifySession(SECRET, null), null);
  assert.equal(await verifySession(SECRET, ""), null);
  assert.equal(await verifySession(SECRET, "garbage"), null);
  assert.equal(await verifySession(SECRET, "abc.def.ghi"), null);
  assert.equal(await verifySession(SECRET, ".sigs"), null);
  assert.equal(await verifySession(SECRET, "body."), null);
});

test("sessions signed with a different secret are rejected", async () => {
  const token = await signSession("another-secret", { sub: "a@b.c", role: "user" });
  assert.equal(await verifySession(SECRET, token), null);
});

test("missing secret fails closed", async () => {
  const token = await signSession(SECRET, { sub: "a@b.c", role: "user" });
  assert.equal(await verifySession(undefined, token), null);
  assert.equal(await verifySession("", token), null);
});