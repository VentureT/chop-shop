"""Tiny SQLite TTL cache for eBay lookups (keeps the daily quota workable)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any

_lock = threading.Lock()


class TTLCache:
    def __init__(self, path: str, ttl_seconds: int) -> None:
        self.path = path
        self.ttl = ttl_seconds
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL, ts REAL NOT NULL)"
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, check_same_thread=False)

    def get(self, key: str) -> Any | None:
        with _lock, self._conn() as c:
            row = c.execute("SELECT v, ts FROM kv WHERE k = ?", (key,)).fetchone()
        if not row:
            return None
        v, ts = row
        if time.time() - ts > self.ttl:
            return None
        return json.loads(v)

    def set(self, key: str, value: Any) -> None:
        with _lock, self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO kv (k, v, ts) VALUES (?, ?, ?)",
                (key, json.dumps(value), time.time()),
            )

    def clear(self) -> None:
        with _lock, self._conn() as c:
            c.execute("DELETE FROM kv")
