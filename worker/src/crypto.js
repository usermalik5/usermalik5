// Password hashing / verification shared by the auth proxy.
// Format-compatible with tech_reg.py: "<iters>$<salt_hex>$<digest_hex>"
// (PBKDF2-SHA256) plus the legacy plain SHA-256 form.

export function hexToBytes(hex) {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(hex.substr(i * 2, 2), 16);
  }
  return out;
}

export function bytesToHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return bytesToHex(new Uint8Array(digest));
}

export async function pbkdf2Hex(password, saltHex, iterations) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"]
  );
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt: hexToBytes(saltHex), iterations },
    key,
    256
  );
  return bytesToHex(new Uint8Array(bits));
}

export async function hashPassword(password) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const digest = await pbkdf2Hex(password, bytesToHex(salt), 100000);
  return `100000$${bytesToHex(salt)}$${digest}`;
}

export async function verifyPassword(password, stored) {
  if (!stored) return false;
  const parts = stored.split("$");
  if (parts.length === 3) {
    const [iters, salt, digest] = parts;
    try {
      const calc = await pbkdf2Hex(password, salt, parseInt(iters, 10));
      return calc === digest.toLowerCase();
    } catch {
      return false;
    }
  }
  const hex = await sha256Hex(password);
  return hex === stored.toLowerCase();
}

const PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";

export function generatePassword(length = 14) {
  const rnd = crypto.getRandomValues(new Uint8Array(length));
  let out = "";
  for (let i = 0; i < length; i++) {
    out += PASSWORD_ALPHABET[rnd[i] % PASSWORD_ALPHABET.length];
  }
  return out;
}

export function isValidEmail(email) {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email || "");
}

export function constantTimeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}