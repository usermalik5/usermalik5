# -*- coding: utf-8 -*-
"""Registration + server-source fetching for GeloTech Tool.

Split out of tech_settings.py so that no single module exceeds the
PyArmor trial license's per-script obfuscation limit, and to keep the
self-service account flow self-contained. Depends only on tech_common.

The client NEVER talks to GitHub directly and contains NO credentials:
every operation goes through the auth proxy Worker (AUTH_WORKER_URL),
which holds the repo read/write token, the SMTP sender and the
session-signing key as server-side secrets.

Account operations (login, password request, block/unblock, password
changes) go through the Worker. Admin operations require a short-lived
signed session token (Authorization: Bearer <session>) issued by the
Worker on successful login of the admin account; the client stores it ONLY
in memory. Admin login is two-factor server-side: the admin password AND
the admin secret phrase, which exists only as a Worker secret and is never
embedded anywhere in the client.

The package-database manifest flow (version.json + Ed25519 signature +
sha256-pinned gelotech_database_v3.json) also goes through the Worker's
GET /files/<name> endpoints: integrity is still verified client-side
with the embedded public key.
"""
import os
import re
import json
import base64
import hashlib
import requests

from tech_common import (get_session_database_path, AUTH_WORKER_URL,
                         UPDATE_SIGN_PUBLIC_KEY)


def _worker_base():
    base = AUTH_WORKER_URL.strip().rstrip("/")
    if not base.startswith("http"):
        raise RuntimeError("Auth proxy is not configured on this build.")
    return base


def _worker_call(path, payload=None, session=None):
    """Call the auth proxy Worker. GET when payload is None, else POST JSON.
    When session is given, it is sent as `Authorization: Bearer <session>`
    (the Worker verifies its signature and expiry server-side). Returns the
    parsed JSON response; raises on transport/HTTP errors."""
    url = f"{_worker_base()}/{path.lstrip('/')}"
    headers = {}
    if session:
        headers["Authorization"] = f"Bearer {session}"
    if payload is None:
        resp = requests.get(url, headers=headers, timeout=60)
    else:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _worker_fetch(path):
    """Fetch raw bytes from the Worker (GET /files/<name>). The Worker holds
    the repo read token, so the client needs no GitHub credentials at all."""
    url = f"{_worker_base()}/{path.lstrip('/')}"
    resp = requests.get(url, timeout=120)
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
    """Fetch the signed manifest and the package database through the
    Worker's /files endpoints (the Worker owns the GitHub read token). The
    manifest signature and the database's sha256 (pinned in the signed
    manifest) are verified client-side. Returns db_bytes or None if the
    server is unreachable or verification fails. NEVER writes anything to
    disk — the result exists only in memory."""
    try:
        manifest_bytes = _worker_fetch("files/version.json")
        sig_bytes = _worker_fetch("files/version.json.sig")
        if not _verify_manifest_sig(manifest_bytes, sig_bytes.decode("utf-8")):
            return None
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        sha_map = manifest.get("sha256")
        expected_db = sha_map.get("gelotech_database_v3.json") if isinstance(sha_map, dict) else None
        if not expected_db:
            return None
        db_bytes = _worker_fetch("files/gelotech_database_v3.json")
        if hashlib.sha256(db_bytes).hexdigest() != expected_db:
            return None
        return db_bytes
    except Exception:
        return None


def _fetch_verified_users(session):
    """Return the SANITIZED account list from the Worker's admin-only
    /accounts endpoint (requires a valid admin session; password hashes are
    never returned). Returns (users, error) — error is None on success."""
    try:
        resp = _worker_call("accounts", session=session)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (401, 403):
            return None, "Admin session expired or not authorized. Sign out and sign back in."
        return None, f"Could not reach the auth server: {type(e).__name__}: {e}"
    except Exception as e:
        return None, f"Could not reach the auth server: {type(e).__name__}: {e}"
    if not resp.get("ok"):
        return None, resp.get("error") or "Could not load accounts."
    users = resp.get("users")
    if not isinstance(users, dict):
        return None, "Auth server returned an invalid account list."
    return users, None


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


# ----------------------------------------------------
# EMAIL-BASED ACCOUNTS (auth proxy Worker)
# ----------------------------------------------------
def _is_valid_email(email):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""))


def _login_user(name, pw, phrase=None):
    """Verify credentials against the auth proxy Worker, which checks the
    PBKDF2 hash and the blocked flag server-side. Returns
    (ok: bool, reason: str, user: dict|None, session: str|None).
    user carries the server-issued role/permissions/tabs (no hash is ever
    sent back); session is a short-lived signed token the Worker issues on
    success and that the client keeps ONLY in memory.
    The admin account additionally requires the admin secret phrase, which
    the Worker validates server-side (it lives only as a Worker secret, so
    the client merely forwards what the maintainer types)."""
    payload = {"email": name, "password": pw}
    if phrase:
        payload["phrase"] = phrase
    try:
        resp = _worker_call("login", payload)
    except Exception as e:
        return False, f"Could not reach the auth server: {type(e).__name__}: {e}", None, None
    if not resp.get("ok"):
        reason = resp.get("reason") or resp.get("error") or "Login failed."
        return False, reason, None, None
    return True, "", resp.get("user") or {}, resp.get("session")


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


def _set_user_blocked(email, blocked, session):
    """Block (or unblock) an account through the auth proxy Worker, which
    requires a valid admin session (Bearer) before writing secret.json. No
    secret phrase is ever sent. Returns None on success or an error string."""
    try:
        resp = _worker_call("admin/block", {"email": email, "blocked": blocked}, session=session)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (401, 403):
            return "Admin session expired or not authorized. Sign out and sign back in."
        return f"Could not reach the auth server: {type(e).__name__}: {e}"
    except Exception as e:
        return f"Could not reach the auth server: {type(e).__name__}: {e}"
    if not resp.get("ok"):
        return resp.get("error") or "Block/unblock failed."
    return None


def _admin_set_role(email, role, session):
    """Set the role for an account (maintainer action, admin session required).
    The Worker validates the role and writes it into secret.json server-side.
    Returns None on success or an error string."""
    try:
        resp = _worker_call("admin/role", {"email": email, "role": role}, session=session)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (401, 403):
            return "Admin session expired or not authorized. Sign out and sign back in."
        return f"Could not reach the auth server: {type(e).__name__}: {e}"
    except Exception as e:
        return f"Could not reach the auth server: {type(e).__name__}: {e}"
    if not resp.get("ok"):
        return resp.get("error") or "Role change failed."
    return None


def _admin_set_password(email, new_password, session):
    """Set a new password for an account (maintainer action, admin session
    required). The Worker hashes it server-side; the client only sends the
    value over HTTPS and never persists it. Returns None on success or an
    error string."""
    try:
        resp = _worker_call("admin/password", {"email": email, "password": new_password}, session=session)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (401, 403):
            return "Admin session expired or not authorized. Sign out and sign back in."
        return f"Could not reach the auth server: {type(e).__name__}: {e}"
    except Exception as e:
        return f"Could not reach the auth server: {type(e).__name__}: {e}"
    if not resp.get("ok"):
        return resp.get("error") or "Password change failed."
    return None