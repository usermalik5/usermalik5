# -*- coding: utf-8 -*-
"""Functional proof of the post-login database flow:

    login -> verified DB downloaded -> session DB selected -> DatabaseService
    loads non-empty data

Two legs:

* Production leg (no mocks): uses the REAL AUTH_WORKER_URL and the REAL
  embedded UPDATE_SIGN_PUBLIC_KEY against the deployed Worker. Proves the
  client's signature + sha256 verification succeeds on the live manifest
  and that the fresh per-login database is selected and loaded.

* Mock-Worker leg: a local HTTP server standing in for the Worker contract
  (POST /login -> session; GET /files/* -> signed manifest + DB), through
  which _login_user + _fetch_verified_sources + the exact finish_login
  wiring (purge -> write session path -> set_path(get_live_database_path()))
  produce a non-empty DatabaseService load with the freshly downloaded
  content.
"""
import base64
import hashlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from cryptography.hazmat.primitives.asymmetric import ed25519

import tech_reg
from tech_common import (get_bundle_dir, get_live_database_path,
                         get_session_database_path, load_package_database)
from tech_database import DatabaseService

TEST_DB = {
    "packages": {
        "com.example.testsuite": {
            "label": "Test Suite",
            "name": "Test Suite",
            "removal": "Recommended",
            "gelotech": {"debloated": True},
        },
        "com.example.other": {"label": "Other", "removal": "Advanced"},
    }
}
TEST_DB_BYTES = json.dumps(TEST_DB, separators=(",", ":")).encode()


def _sign(key, payload: bytes) -> str:
    return base64.b64encode(key.sign(payload)).decode()


class _MockWorkerHandler(BaseHTTPRequestHandler):
    key = None
    manifest_bytes = None
    sig = None

    def log_message(self, *args):
        pass

    def do_POST(self):
        if self.path.rstrip("/") != "/login":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if body.get("email") != "a@b.c" or body.get("password") != "pw":
            self._json({"ok": False, "reason": "invalid-credentials"}, 401)
            return
        self._json({"ok": True,
                    "user": {"role": "user", "permissions": ["mirror"],
                             "tabs": ["Home"], "blocked": False},
                    "session": "test-session-token"})

    def do_GET(self):
        path = self.path.rstrip("/")
        if path == "/files/version.json":
            self._raw(self.manifest_bytes)
        elif path == "/files/version.json.sig":
            self._raw(self.sig.encode())
        elif path == "/files/gelotech_database_v3.json":
            self._raw(TEST_DB_BYTES)
        else:
            self.send_error(404)

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _raw(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module")
def mock_worker():
    key = ed25519.Ed25519PrivateKey.generate()
    manifest = {"database": 1, "banking": 1,
                "sha256": {"gelotech_database_v3.json":
                           hashlib.sha256(TEST_DB_BYTES).hexdigest()}}
    manifest_bytes = json.dumps(manifest, separators=(",", ":")).encode()
    _MockWorkerHandler.key = key
    _MockWorkerHandler.manifest_bytes = manifest_bytes
    _MockWorkerHandler.sig = _sign(key, manifest_bytes)

    server = HTTPServer(("127.0.0.1", 0), _MockWorkerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def _purge():
    tech_reg._purge_session_database()
    assert not os.path.isfile(get_session_database_path())


def _session_db_loads():
    """Exactly what finish_login does after writing db_bytes: point the
    DatabaseService at get_live_database_path() (a DIRECTORY, not the JSON
    file) and load through the real loader."""
    assert os.path.isfile(get_session_database_path())
    live_dir = get_live_database_path()
    assert os.path.isdir(live_dir), "live path must be a directory"
    assert os.path.dirname(get_session_database_path()) == live_dir, \
        "live path must resolve to the session DB directory"
    svc = DatabaseService(live_dir)
    data = svc.load()
    assert isinstance(data, dict) and data, "package database must load non-empty"
    return svc, data


def test_production_login_db_flow_against_deployed_worker():
    """Real end-to-end: AUTH_WORKER_URL + embedded public key + live signed
    manifest -> verified DB bytes -> session file -> DatabaseService loads
    real package records."""
    _purge()
    try:
        db_bytes = tech_reg._fetch_verified_sources()
        assert db_bytes is not None, "production fetch/verify failed"
        assert len(db_bytes) > 1_000_000, "live DB is suspiciously small"
        with open(get_session_database_path(), "wb") as f:
            f.write(db_bytes)
        svc, data = _session_db_loads()
        assert len(data) > 1000, "production DB should hold thousands of packages"
        assert all(isinstance(v, dict) and v.get("id") == k for k, v in list(data.items())[:50]), \
            "records must be normalized with their id"
    finally:
        _purge()


def test_mock_worker_login_to_session_db(mock_worker, monkeypatch):
    """Login leg through the real client code with a Worker-shaped server:
    _login_user -> verified DB -> session DB selected -> non-empty load of
    the freshly downloaded content."""
    _purge()
    monkeypatch.setattr(tech_reg, "AUTH_WORKER_URL", mock_worker)
    monkeypatch.setattr(tech_reg, "UPDATE_SIGN_PUBLIC_KEY",
                        base64.b64encode(
                            _MockWorkerHandler.key.public_key().public_bytes_raw()).decode())
    try:
        ok, reason, user, session = tech_reg._login_user("a@b.c", "pw")
        assert ok, reason
        assert user["role"] == "user"
        assert session == "test-session-token"
        assert "hash" not in user

        db_bytes = tech_reg._fetch_verified_sources()
        assert db_bytes == TEST_DB_BYTES

        with open(get_session_database_path(), "wb") as f:
            f.write(db_bytes)
        svc, data = _session_db_loads()

        record = data["com.example.testsuite"]
        assert record["removal"] == "Recommended"
        assert record["debloated"] is True
        assert "com.example.testsuite" not in load_package_database(get_bundle_dir()), \
            "fresh per-login DB must actually replace the bundled/startup database"

        svc.set_path(get_live_database_path())
        svc.clear()
        assert svc.load()["com.example.other"]["removal"] == "Advanced"
    finally:
        _purge()


def test_live_path_falls_back_to_bundle_when_no_session_db():
    _purge()
    try:
        assert get_live_database_path() == get_bundle_dir()
    finally:
        _purge()