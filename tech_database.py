# -*- coding: utf-8 -*-
"""Central package-database access with safe in-process caching."""

import os
import threading


class DatabaseService:
    def __init__(self, path, loader=None):
        self.path = path
        if loader is None:
            from tech_common import load_package_database
            loader = load_package_database
        self._loader = loader
        self._lock = threading.RLock()
        self._cache = None
        self._mtime_ns = None

    def load(self, force=False):
        with self._lock:
            try:
                mtime_ns = os.stat(self.path).st_mtime_ns
            except OSError:
                mtime_ns = None

            if not force and self._cache is not None and mtime_ns == self._mtime_ns:
                return self._cache

            data = self._loader(self.path) or {}
            self._cache = data
            self._mtime_ns = mtime_ns
            return data

    def refresh(self):
        return self.load(force=True)

    def clear(self):
        with self._lock:
            self._cache = None
            self._mtime_ns = None

    def set_path(self, path):
        """Point the service at a new database location and drop any cached
        data. Used after login when the verified per-session database replaces
        the startup/live path."""
        with self._lock:
            self.path = path
            self._cache = None
            self._mtime_ns = None

    def get(self, package_id, default=None):
        return self.load().get(package_id, default)

    def all(self):
        return self.load()
