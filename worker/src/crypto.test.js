import { test } from "node:test";
import assert from "node:assert/strict";
import {
  verifyPassword,
  hashPassword,
  generatePassword,
  isValidEmail,
  constantTimeEqual,
  pbkdf2Hex,
  sha256Hex,
} from "./crypto.js";

const PYTHON_VECTOR = "100000$557567e42cee4b69a5d062e5232504ee$6790e41f1ca715692d9252db619af39c6022cd56213647c3620f9c1d832f8507";
const PYTHON_LEGACY = "82031089b647d243277b3f7f898c0da58e5836bc0ee9b4cbde9fe416f31fae2b";
const ZERO_SALT_VECTOR = "100000$00000000000000000000000000000000$f8d59b2b78d9a4bd652514abcb74d3148b1ce24f400927b08cff47ca7e86e79f";

test("verifyPassword matches Python PBKDF2 vector", async () => {
  assert.equal(await verifyPassword("CorrectHorseBatteryStaple", PYTHON_VECTOR), true);
  assert.equal(await verifyPassword("wrong", PYTHON_VECTOR), false);
});

test("verifyPassword matches Python legacy SHA-256 vector", async () => {
  assert.equal(await verifyPassword("legacypw", PYTHON_LEGACY), true);
  assert.equal(await verifyPassword("other", PYTHON_LEGACY), false);
});

test("verifyPassword rejects malformed hashes", async () => {
  assert.equal(await verifyPassword("x", null), false);
  assert.equal(await verifyPassword("x", ""), false);
  assert.equal(await verifyPassword("x", "not-a-hash"), false);
  assert.equal(await verifyPassword("x", "100000$zz$$dd"), false);
});

test("hashPassword round-trips and matches Python algorithm exactly", async () => {
  const stored = await hashPassword("s3cret!");
  const parts = stored.split("$");
  assert.equal(parts.length, 3);
  assert.equal(parts[0], "100000");
  assert.equal(parts[1].length, 32);
  assert.equal(parts[2].length, 64);
  assert.equal(await verifyPassword("s3cret!", stored), true);
  assert.equal(await verifyPassword("nope", stored), false);
  const direct = await pbkdf2Hex("s3cret!", parts[1], 100000);
  assert.equal(direct, parts[2]);
  const legacy = await sha256Hex("s3cret!");
  assert.equal(legacy.length, 64);
});

test("generatePassword uses allowed alphabet only", () => {
  const ALPHABET = new Set("ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789");
  for (let i = 0; i < 50; i++) {
    const pw = generatePassword(14);
    assert.equal(pw.length, 14);
    for (const ch of pw) assert.ok(ALPHABET.has(ch), `unexpected char ${ch}`);
  }
});

test("isValidEmail", () => {
  assert.equal(isValidEmail("user@example.com"), true);
  assert.equal(isValidEmail("a.b+c@sub.domain.co"), true);
  assert.equal(isValidEmail("notanemail"), false);
  assert.equal(isValidEmail("a@b"), false);
  assert.equal(isValidEmail(""), false);
  assert.equal(isValidEmail(null), false);
});

test("constantTimeEqual", () => {
  assert.equal(constantTimeEqual("abc", "abc"), true);
  assert.equal(constantTimeEqual("abc", "abd"), false);
  assert.equal(constantTimeEqual("abc", "abcd"), false);
  assert.equal(constantTimeEqual("", ""), true);
  assert.equal(constantTimeEqual(1, "1"), false);
});

test("zero-salt PBKDF2 vector (deterministic, cross-checked)", async () => {
  const calc = await pbkdf2Hex("x", "00000000000000000000000000000000", 100000);
  assert.equal(calc, ZERO_SALT_VECTOR.split("$")[2]);
});