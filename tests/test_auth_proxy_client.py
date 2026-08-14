# -*- coding: utf-8 -*-
"""Tests for the auth-proxy Worker client in tech_reg: _worker_call,
_login_user, _request_password and _set_user_blocked must all talk to the
Worker and map its JSON contract onto the app's (ok, reason/message) shape.
"""
import requests

import tech_reg


def test_worker_call_post_sends_json(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return type("R", (), {"raise_for_status": lambda self: None,
                              "json": lambda self: {"ok": True}})()

    monkeypatch.setattr(requests, "post", fake_post)
    assert tech_reg._worker_call("login", {"email": "a@b.c", "password": "x"}) == {"ok": True}
    assert captured["url"].endswith("/login")
    assert captured["json"] == {"email": "a@b.c", "password": "x"}
    assert captured["timeout"] == 60


def test_worker_call_get_without_payload(monkeypatch):
    captured = {}

    def fake_get(url, timeout=None):
        captured["url"] = url
        return type("R", (), {"raise_for_status": lambda self: None,
                              "json": lambda self: {"users": {}}})()

    monkeypatch.setattr(requests, "get", fake_get)
    assert tech_reg._worker_call("accounts") == {"users": {}}
    assert captured["url"].endswith("/accounts")


def test_login_user_success(monkeypatch):
    def fake_call(path, payload=None):
        assert path == "login"
        assert payload == {"email": "a@b.c", "password": "pw"}
        return {"ok": True, "user": {"permissions": ["mirror"], "tabs": ["Home"], "blocked": False}}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    ok, reason, user = tech_reg._login_user("a@b.c", "pw")
    assert ok is True
    assert reason == ""
    assert user["permissions"] == ["mirror"]
    assert user["tabs"] == ["Home"]


def test_login_user_rejected(monkeypatch):
    def fake_call(path, payload=None):
        return {"ok": False, "reason": "blocked"}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    ok, reason, user = tech_reg._login_user("a@b.c", "pw")
    assert ok is False
    assert reason == "blocked"
    assert user is None


def test_login_user_server_unreachable(monkeypatch):
    def fake_call(path, payload=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    ok, reason, user = tech_reg._login_user("a@b.c", "pw")
    assert ok is False
    assert "boom" in reason
    assert user is None


def test_request_password_ok(monkeypatch):
    def fake_call(path, payload=None):
        assert path == "register"
        assert payload == {"email": "a@b.c"}
        return {"ok": True, "message": "Password sent to a@b.c."}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    ok, msg = tech_reg._request_password("a@b.c")
    assert ok is True
    assert "a@b.c" in msg


def test_request_password_rejected(monkeypatch):
    def fake_call(path, payload=None):
        return {"ok": False, "message": "Invalid email address."}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    ok, msg = tech_reg._request_password("bad")
    assert ok is False
    assert msg == "Invalid email address."


def test_set_user_blocked_sends_admin_phrase(monkeypatch):
    captured = {}

    def fake_call(path, payload=None):
        captured["path"] = path
        captured["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    err = tech_reg._set_user_blocked("a@b.c", True)
    assert err is None
    assert captured["path"] == "admin/block"
    assert captured["payload"]["email"] == "a@b.c"
    assert captured["payload"]["blocked"] is True
    assert captured["payload"]["phrase"] == tech_reg.ADMIN_SECRET_PHRASE


def test_set_user_blocked_error(monkeypatch):
    def fake_call(path, payload=None):
        return {"ok": False, "error": "Invalid admin credentials."}

    monkeypatch.setattr(tech_reg, "_worker_call", fake_call)
    err = tech_reg._set_user_blocked("a@b.c", False)
    assert err == "Invalid admin credentials."


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