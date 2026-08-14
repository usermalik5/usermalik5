# -*- coding: utf-8 -*-
"""Tests for the auth-proxy Worker client in tech_reg: _worker_call,
_login_user, _request_password, _set_user_blocked and _fetch_verified_users
must all talk to the Worker, send admin sessions as Bearer tokens, and map
its JSON contract onto the app's (ok, reason/message) shape.
"""
import base64
import hashlib
import json

import requests

import tech_reg


def test_worker_call_post_sends_json(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return type("R", (), {"raise_for_status": lambda self: None,
                              "json": lambda self: {"ok": True}})()

    monkeypatch.setattr(requests, "post", fake_post)
    assert tech_reg._worker_call("login", {"email": "a@b.c", "password": "x"}) == {"ok": True}
    assert captured["url"].endswith("/login")
    assert captured["json"] == {"email": "a@b.c", "password": "x"}
    assert captured["headers"] in ({}, None)
    assert captured["timeout"] == 60


def test_worker_call_get_without_payload(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return type("R", (), {"raise_for_status": lambda self: None,
                              "json": lambda self: {"users": {}}})()

    monkeypatch.setattr(requests, "get", fake_get)
    assert tech_reg._worker_call("accounts") == {"users": {}}
    assert captured["url"].endswith("/accounts")


def test_worker_call_sends_bearer_session(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["headers"] = headers
        return type("R", (), {"raise_for_status": lambda self: None,
                              "json": lambda self: {"ok": True}})()

    monkeypatch.setattr(requests, "get", fake_get)
    tech_reg._worker_call("accounts", session="tok123")
    assert captured["headers"]["Authorization"] == "Bearer tok123"


def test_login_user_success(monkeypatch):
    def fake_call(path, payload=None, session=None):
        assert path == "login"
        assert payload == {"email": "a@b.c", "password": "pw"}
        assert session is None
        return {"ok": True,
                "user": {"role": "user", "permissions": ["mirror"], "tabs": ["Home"], "blocked": False},
                "session": "sess-abc"}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    ok, reason, user, session = tech_reg._login_user("a@b.c", "pw")
    assert ok is True
    assert reason == ""
    assert user["permissions"] == ["mirror"]
    assert user["role"] == "user"
    assert session == "sess-abc"


def test_login_user_admin_role_from_server(monkeypatch):
    def fake_call(path, payload=None, session=None):
        return {"ok": True, "user": {"role": "admin"}, "session": "sess-x"}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    ok, reason, user, session = tech_reg._login_user("admin", "pw")
    assert ok is True
    assert user["role"] == "admin"
    assert session == "sess-x"
    assert "hash" not in user, "login response must never carry the hash"


def test_login_user_rejected(monkeypatch):
    def fake_call(path, payload=None, session=None):
        return {"ok": False, "reason": "blocked"}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    ok, reason, user, session = tech_reg._login_user("a@b.c", "pw")
    assert ok is False
    assert reason == "blocked"
    assert user is None
    assert session is None


def test_login_user_server_unreachable(monkeypatch):
    def fake_call(path, payload=None, session=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    ok, reason, user, session = tech_reg._login_user("a@b.c", "pw")
    assert ok is False
    assert "boom" in reason
    assert user is None


def test_request_password_ok(monkeypatch):
    def fake_call(path, payload=None, session=None):
        assert path == "register"
        assert payload == {"email": "a@b.c"}
        return {"ok": True, "message": "Password sent to a@b.c."}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    ok, msg = tech_reg._request_password("a@b.c")
    assert ok is True
    assert "a@b.c" in msg


def test_request_password_rejected(monkeypatch):
    def fake_call(path, payload=None, session=None):
        return {"ok": False, "message": "Invalid email address."}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    ok, msg = tech_reg._request_password("bad")
    assert ok is False
    assert msg == "Invalid email address."


def test_set_user_blocked_sends_session_not_phrase(monkeypatch):
    captured = {}

    def fake_call(path, payload=None, session=None):
        captured["path"] = path
        captured["payload"] = payload
        captured["session"] = session
        return {"ok": True}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    err = tech_reg._set_user_blocked("a@b.c", True, "sess-tok")
    assert err is None
    assert captured["path"] == "admin/block"
    assert captured["payload"] == {"email": "a@b.c", "blocked": True}
    assert "phrase" not in captured["payload"]
    assert captured["session"] == "sess-tok"
    assert not hasattr(tech_reg, "ADMIN_SECRET_PHRASE"), "admin phrase must not exist client-side"


def test_set_user_blocked_401_maps_to_session_message(monkeypatch):
    err = requests.HTTPError("401")
    err.response = type("R", (), {"status_code": 401})()
    monkeypatch.setattr(tech_reg, "_worker_call", lambda *a, **k: (_ for _ in ()).throw(err))
    result = tech_reg._set_user_blocked("a@b.c", True, "expired")
    assert "session" in result.lower()


def test_set_user_blocked_error(monkeypatch):
    def fake_call(path, payload=None, session=None):
        return {"ok": False, "error": "Admin access required."}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    err = tech_reg._set_user_blocked("a@b.c", False, "s")
    assert err == "Admin access required."


def test_fetch_verified_users_requires_session(monkeypatch):
    captured = {}

    def fake_call(path, payload=None, session=None):
        captured["path"] = path
        captured["session"] = session
        return {"ok": True, "users": {"a@b.c": {"permissions": [], "tabs": [], "blocked": False}}}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    users, err = tech_reg._fetch_verified_users("sess-admin")
    assert err is None
    assert users["a@b.c"]["blocked"] is False
    assert captured["path"] == "accounts"
    assert captured["session"] == "sess-admin"


def test_fetch_verified_users_401(monkeypatch):
    err = requests.HTTPError("401")
    err.response = type("R", (), {"status_code": 401})()
    monkeypatch.setattr(tech_reg, "_worker_call", lambda *a, **k: (_ for _ in ()).throw(err))
    users, err_msg = tech_reg._fetch_verified_users("stale")
    assert users is None
    assert "session" in err_msg.lower()


def test_worker_fetch_hits_files_endpoint(monkeypatch):
    captured = {}

    def fake_get(url, timeout=None):
        captured["url"] = url
        return type("R", (), {"raise_for_status": lambda self: None,
                              "content": b"bytes"})()

    monkeypatch.setattr(requests, "get", fake_get)
    assert tech_reg._worker_fetch("files/version.json") == b"bytes"
    assert captured["url"].endswith("/files/version.json")


def test_fetch_verified_sources_verifies_signature_and_sha(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import ed25519

    key = ed25519.Ed25519PrivateKey.generate()
    db_bytes = b'{"packages": {}}'
    manifest = {"database": 1, "banking": 1,
                "sha256": {"gelotech_database_v3.json": hashlib.sha256(db_bytes).hexdigest()}}
    manifest_bytes = json.dumps(manifest).encode()
    sig = base64.b64encode(key.sign(manifest_bytes)).decode()

    calls = {"files/version.json": manifest_bytes,
             "files/version.json.sig": sig.encode(),
             "files/gelotech_database_v3.json": db_bytes}

    def fake_fetch(path):
        assert path.startswith("files/")
        assert calls[path] is not None
        return calls[path]

    monkeypatch.setattr(tech_reg, "_worker_fetch", fake_fetch)
    monkeypatch.setattr(tech_reg, "UPDATE_SIGN_PUBLIC_KEY",
                        base64.b64encode(key.public_key().public_bytes_raw()).decode())
    assert tech_reg._fetch_verified_sources() == db_bytes


def test_fetch_verified_sources_rejects_bad_sha(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import ed25519

    key = ed25519.Ed25519PrivateKey.generate()
    manifest = {"database": 1, "banking": 1,
                "sha256": {"gelotech_database_v3.json": "ff" * 32}}
    manifest_bytes = json.dumps(manifest).encode()
    sig = base64.b64encode(key.sign(manifest_bytes)).decode()

    calls = {"files/version.json": manifest_bytes,
             "files/version.json.sig": sig.encode(),
             "files/gelotech_database_v3.json": b'{"packages": {}}'}

    def fake_fetch(path):
        return calls[path]

    monkeypatch.setattr(tech_reg, "_worker_fetch", fake_fetch)
    monkeypatch.setattr(tech_reg, "UPDATE_SIGN_PUBLIC_KEY",
                        base64.b64encode(key.public_key().public_bytes_raw()).decode())
    assert tech_reg._fetch_verified_sources() is None


def test_fetch_verified_sources_rejects_bad_signature(monkeypatch):
    calls = {"files/version.json": b'{"database": 1}',
             "files/version.json.sig": b"not-a-valid-signature",
             "files/gelotech_database_v3.json": b"{}"}

    def fake_fetch(path):
        return calls[path]

    monkeypatch.setattr(tech_reg, "_worker_fetch", fake_fetch)
    assert tech_reg._fetch_verified_sources() is None


def test_fetch_verified_sources_rejects_no_accounts_call(monkeypatch):
    """The client must no longer fetch the accounts list for every login:
    it comes from the login response only (admin reads use the session)."""
    from cryptography.hazmat.primitives.asymmetric import ed25519

    key = ed25519.Ed25519PrivateKey.generate()
    db_bytes = b'{"packages": {}}'
    manifest = {"database": 1, "banking": 1,
                "sha256": {"gelotech_database_v3.json": hashlib.sha256(db_bytes).hexdigest()}}
    manifest_bytes = json.dumps(manifest).encode()
    sig = base64.b64encode(key.sign(manifest_bytes)).decode()

    calls = {"files/version.json": manifest_bytes,
             "files/version.json.sig": sig.encode(),
             "files/gelotech_database_v3.json": db_bytes}

    def fake_fetch(path):
        assert path.startswith("files/"), "client must fetch only /files endpoints"
        return calls[path]

    monkeypatch.setattr(tech_reg, "_worker_fetch", fake_fetch)
    monkeypatch.setattr(tech_reg, "UPDATE_SIGN_PUBLIC_KEY",
                        base64.b64encode(key.public_key().public_bytes_raw()).decode())
    monkeypatch.setattr(tech_reg, "_worker_call", lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected /accounts call")))
    assert tech_reg._fetch_verified_sources() == db_bytes


def test_worker_call_unconfigured():
    original = tech_reg.AUTH_WORKER_URL
    try:
        tech_reg.AUTH_WORKER_URL = ""
        try:
            tech_reg._worker_call("accounts")
        except RuntimeError as e:
            assert "not configured" in str(e)
        else:
            raise AssertionError("expected RuntimeError")
    finally:
        tech_reg.AUTH_WORKER_URL = original