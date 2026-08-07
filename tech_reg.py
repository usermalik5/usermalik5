# -*- coding: utf-8 -*-
"""Registration + server-source fetching for GeloTech Tool.

Split out of tech_settings.py so that no single module exceeds the
PyArmor trial license's per-script obfuscation limit, and to keep the
self-service account flow self-contained. Depends only on tech_common.
"""
import os
import re
import json
import base64
import time
import hashlib
import secrets
import smtplib
import requests
from email.message import EmailMessage
from email.utils import formataddr

from tech_common import (get_session_database_path, EMBEDDED_UPDATE_URL,
                         EMBEDDED_UPDATE_TOKEN, EMBEDDED_UPDATE_WRITE_TOKEN,
                         SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
                         SMTP_FROM, UPDATE_SIGN_PUBLIC_KEY)


def _parse_repo(base):
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?(?:\?|$|/tree/([^/]+))", base)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    branch = m.group(3) or "main"
    return owner, repo, branch


def _api_fetch(owner, repo, branch, fname, headers):
    """Fetch a file's exact committed bytes from GitHub over TLS. Uses the
    contents API to resolve the blob sha, then the git blobs API to download
    the bytes (the contents API returns EMPTY content for files larger than
    1 MB, so the blobs API is the reliable path). Falls back to
    raw.githubusercontent.com for public repos when no token is set."""
    if headers:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{fname}?ref={branch}"
        resp = requests.get(url, headers={**headers, "Accept": "application/vnd.github+json"}, timeout=60)
        resp.raise_for_status()
        meta = resp.json()
        content = meta.get("content") or ""
        if content:
            return base64.b64decode(content)
        sha = meta.get("sha")
        if not sha:
            raise RuntimeError(f"no blob sha returned for {fname}")
        blob_url = f"https://api.github.com/repos/{owner}/{repo}/git/blobs/{sha}"
        resp2 = requests.get(blob_url, headers={**headers, "Accept": "application/vnd.github+json"}, timeout=120)
        resp2.raise_for_status()
        return base64.b64decode(resp2.json()["content"])
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{fname}"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def _verify_manifest_sig(manifest_bytes, sig_b64):
    """Verify the Ed25519 signature over version.json with the embedded
    public key. Returns True only for a valid signature."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        pub = ed25519.Ed25519PublicKey.from_public_bytes(
            base64.b64decode(UPDATE_SIGN_PUBLIC_KEY))
        pub.verify(base64.b64decode(sig_b64.strip()), manifest_bytes)
        return True
    except Exception:
        return False


def _fetch_verified_sources():
    """Fetch the signed manifest once from the pinned update server, then
    fetch the accounts list (secret.json) and the package database
    (gelotech_database_v3.json). The manifest signature and the database's
    sha256 are verified; secret.json is the LIVE accounts file (maintained
    by the app itself via the write token), so it is fetched as-is from
    GitHub over TLS. Returns (users_dict, db_bytes) or (None, None) if the
    server is unreachable or verification fails. NEVER writes anything to
    disk — the results exist only in memory."""
    base = EMBEDDED_UPDATE_URL.strip().rstrip("/")
    tok = EMBEDDED_UPDATE_TOKEN.strip()
    parsed = _parse_repo(base)
    if not parsed:
        return None, None
    owner, repo, branch = parsed
    headers = {"Authorization": f"Bearer {tok}"} if tok else {}
    try:
        manifest_bytes = _api_fetch(owner, repo, branch, "version.json", headers)
        sig_bytes = _api_fetch(owner, repo, branch, "version.json.sig", headers)
        if not _verify_manifest_sig(manifest_bytes, sig_bytes.decode("utf-8")):
            return None, None
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        sha_map = manifest.get("sha256")
        if not isinstance(sha_map, dict):
            return None, None
        users_bytes = _api_fetch(owner, repo, branch, "secret.json", headers)
        parsed = json.loads(users_bytes.decode("utf-8"))
        users = parsed.get("users")
        if not isinstance(users, dict):
            return None, None
        expected_db = sha_map.get("gelotech_database_v3.json")
        if not expected_db:
            return None, None
        db_bytes = _api_fetch(owner, repo, branch, "gelotech_database_v3.json", headers)
        if hashlib.sha256(db_bytes).hexdigest() != expected_db:
            return None, None
        return users, db_bytes
    except Exception:
        return None, None


def _fetch_verified_users():
    """Return just the signed users list from the update server (used by the
    read-only admin panel), or None on failure. Never writes to disk."""
    users, _ = _fetch_verified_sources()
    return users


def _purge_session_database():
    """Delete the per-login database copy. Called before each login's fetch
    and on app close, so the database is never left on disk between sessions
    and the next login always pulls the latest version."""
    try:
        path = get_session_database_path()
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass


def hash_password(pw):
    """PBKDF2-SHA256 hash: '<iters>$<salt_hex>$<digest_hex>'."""
    salt = os.urandom(16).hex()
    iters = 100_000
    digest = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), iters).hex()
    return f"{iters}${salt}${digest}"


def verify_password(pw, stored):
    """Constant-time-ish PBKDF2 check; also accepts legacy SHA-256 hashes."""
    if not stored:
        return False
    if stored.count("$") == 2:
        iters, salt, digest = stored.split("$")
        try:
            calc = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), int(iters)).hex()
        except Exception:
            return False
        return calc == digest
    return hashlib.sha256(pw.encode("utf-8")).hexdigest() == stored


# ----------------------------------------------------
# EMAIL-BASED ACCOUNTS (self-registration / password reset)
# ----------------------------------------------------
def _is_valid_email(email):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""))


def _generate_password():
    """Random 14-character alphanumeric password (secrets module)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(14))


def _send_password_email(email, password):
    """Email the generated password to the user via the embedded SMTP
    sender. Returns None on success or an error string."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
        return "Password email service is not configured on this build."
    try:
        msg = EmailMessage()
        msg["Subject"] = "GeloTech Tool - Your Access Password"
        msg["From"] = formataddr(("GeloTech Tool", SMTP_FROM or SMTP_USER))
        msg["To"] = email
        msg.set_content(
            "Hello,\n\n"
            "Here is your GeloTech Tool access password:\n\n"
            f"    {password}\n\n"
            "Use it together with your email address to log in.\n"
            "If you didn't request this, you can safely ignore this email.\n"
            "\n"
            "GeloTech Tool"
        )
        if int(SMTP_PORT) == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, int(SMTP_PORT), timeout=60)
        else:
            server = smtplib.SMTP(SMTP_HOST, int(SMTP_PORT), timeout=60)
            server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return None
    except Exception as e:
        return f"Email delivery failed: {type(e).__name__}: {e}"


def _mutate_secret(mutator, commit_msg):
    """Fetch the repo's secret.json, let mutator(dict) modify it in place,
    then PUT it back with the embedded write token. Returns None on success
    or an error string. Retries on concurrent-write conflicts (422)."""
    tok = EMBEDDED_UPDATE_WRITE_TOKEN.strip()
    if not tok:
        return "Account registry is not configured on this build."
    parsed = _parse_repo(EMBEDDED_UPDATE_URL.strip().rstrip("/"))
    if not parsed:
        return "Embedded update URL is not a GitHub repo URL."
    owner, repo, branch = parsed
    headers = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    path = f"https://api.github.com/repos/{owner}/{repo}/contents/secret.json"
    for attempt in range(4):
        try:
            r = requests.get(f"{path}?ref={branch}", headers=headers, timeout=60)
            r.raise_for_status()
            meta = r.json()
            current = json.loads(base64.b64decode(meta["content"]).decode("utf-8"))
            mutator(current)
            body = json.dumps(current, indent=2, ensure_ascii=False)
            r2 = requests.put(path, headers=headers, timeout=60, json={
                "message": commit_msg,
                "content": base64.b64encode(body.encode("utf-8")).decode("ascii"),
                "sha": meta["sha"],
                "branch": branch,
            })
            if r2.status_code == 422 and attempt < 3:
                time.sleep(1.5)
                continue
            r2.raise_for_status()
            return None
        except Exception as e:
            if attempt < 3:
                time.sleep(1.5)
                continue
            return f"Account registry write failed: {type(e).__name__}: {e}"
    return "Account registry write failed."


def _write_user_to_repo(email, pw_hash):
    """Persist a user account (email + PBKDF2 hash) into the repo's
    secret.json. Preserves any existing flags (e.g. blocked) on the record.
    Returns None on success or an error string."""
    def _apply(current):
        users = current.get("users") if isinstance(current.get("users"), dict) else {}
        rec = dict(users.get(email) or {})
        rec.update({"hash": pw_hash, "permissions": rec.get("permissions") or {}})
        users[email] = rec
        current["users"] = users
    return _mutate_secret(_apply, f"Account update for {email} (self-service)")


def _set_user_blocked(email, blocked):
    """Block (or unblock) an account in the repo's secret.json. Blocked
    accounts cannot log in nor request a new password. Returns None on
    success or an error string."""
    def _apply(current):
        users = current.get("users") if isinstance(current.get("users"), dict) else {}
        rec = dict(users.get(email) or {})
        if blocked:
            rec["blocked"] = True
        else:
            rec.pop("blocked", None)
        users[email] = rec
        current["users"] = users
    action = "block" if blocked else "unblock"
    return _mutate_secret(_apply, f"Account {action} for {email} (maintainer)")


def _request_password(email):
    """Full password request flow (new account or reset): fetch+verify the
    server, generate a password, write the PBKDF2 hash to the repo, email it.
    Returns (ok: bool, message: str)."""
    users, _ = _fetch_verified_sources()
    if users is None:
        return False, "Could not reach/verify the update server. Check your internet connection and try again."
    if (users.get(email) or {}).get("blocked"):
        return False, "This email address has been blocked by the maintainer and cannot receive a password."
    password = _generate_password()
    pw_hash = hash_password(password)
    err = _write_user_to_repo(email, pw_hash)
    if err:
        return False, err
    err = _send_password_email(email, password)
    if err:
        return False, err
    return True, (f"Password sent to {email}. Please check your inbox and spam folder, then log in below.")
