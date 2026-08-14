# -*- coding: utf-8 -*-
"""Registration + server-source fetching for GeloTech Tool.

Split out of tech_settings.py so that no single module exceeds the
PyArmor trial license's per-script obfuscation limit, and to keep the
self-service account flow self-contained. Depends only on tech_common.

Account operations (login, password request, block/unblock) go through
the auth proxy Worker (AUTH_WORKER_URL), which holds the repo write
token, the SMTP sender and the admin phrase as server-side secrets.
The package-database manifest flow (version.json + Ed25519 signature +
sha256-pinned gelotech_database_v3.json) still uses GitHub directly.
"""
import os
import re
import json
import base64
import hashlib
import requests

from tech_common import (get_session_database_path, EMBEDDED_UPDATE_URL,
                         EMBEDDED_UPDATE_TOKEN, AUTH_WORKER_URL,
                         ADMIN_SECRET_PHRASE, UPDATE_SIGN_PUBLIC_KEY)


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


def _worker_call(path, payload=None):
    """Call the auth proxy Worker. GET when payload is None, else POST JSON.
    Returns the parsed JSON response; raises on transport/HTTP errors."""
    base = AUTH_WORKER_URL.strip().rstrip("/")
    if not base.startswith("http"):
        raise RuntimeError("Auth proxy is not configured on this build.")
    url = f"{base}/{path.lstrip('/')}"
    if payload is None:
        resp = requests.get(url, timeout=60)
    else:
        resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _fetch_verified_sources():
    """Fetch the signed manifest once from the pinned update server, then
    fetch the package database (gelotech_database_v3.json) from GitHub and
    the accounts list from the auth proxy Worker. The manifest signature and
    the database's sha256 are verified; the accounts list comes from the
    Worker over TLS. Returns (users_dict, db_bytes) or (None, None) if the
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
        accounts = _worker_call("accounts")
        users = accounts.get("users")
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
    """Return just the users list from the auth proxy Worker (used by the
    read-only account list in the admin dialog), or None on failure. Never
    writes to disk."""
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
# EMAIL-BASED ACCOUNTS (auth proxy Worker)
# ----------------------------------------------------
def _is_valid_email(email):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""))


def _login_user(name, pw):
    """Verify credentials against the auth proxy Worker, which checks the
    PBKDF2 hash and the blocked flag server-side. Returns
    (ok: bool, reason: str, user: dict|None) where user carries the
    permissions/tabs the server grants (no hash is ever sent back)."""
    try:
        resp = _worker_call("login", {"email": name, "password": pw})
    except Exception as e:
        return False, f"Could not reach the auth server: {type(e).__name__}: {e}", None
    if not resp.get("ok"):
        reason = resp.get("reason") or resp.get("error") or "Login failed."
        return False, reason, None
    return True, "", resp.get("user") or {}


def _request_password(email):
    """Request a generated password for a new or existing account. The auth
    proxy Worker validates the email, generates and hashes the password,
    writes it into secret.json and emails it to the user. Returns
    (ok: bool, message: str)."""
    try:
        resp = _worker_call("register", {"email": email})
    except Exception as e:
        return False, f"Could not reach the auth server: {type(e).__name__}: {e}"
    if not resp.get("ok"):
        return False, resp.get("message") or resp.get("error") or "Password request failed."
    return True, resp.get("message") or "Password sent to your email."


def _set_user_blocked(email, blocked):
    """Block (or unblock) an account through the auth proxy Worker, which
    checks the admin phrase server-side before writing secret.json. Returns
    None on success or an error string."""
    try:
        resp = _worker_call("admin/block", {
            "phrase": ADMIN_SECRET_PHRASE, "email": email, "blocked": blocked,
        })
    except Exception as e:
        return f"Could not reach the auth server: {type(e).__name__}: {e}"
    if not resp.get("ok"):
        return resp.get("error") or "Block/unblock failed."
    return None