from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from app.config import BASE_DIR

_LOCK = threading.Lock()
_CACHE_DB = BASE_DIR / 'data' / 'baidu_api_cache.db'


def _connect() -> sqlite3.Connection:
    _CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_CACHE_DB, timeout=10)
    con.execute('''
        CREATE TABLE IF NOT EXISTS api_cache (
            cache_key TEXT PRIMARY KEY,
            expires_at REAL NOT NULL,
            payload_json TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    ''')
    con.execute('CREATE INDEX IF NOT EXISTS idx_api_cache_expires ON api_cache(expires_at)')
    return con


def get_cached(cache_key: str) -> dict[str, Any] | None:
    now = time.time()
    with _LOCK, _connect() as con:
        row = con.execute(
            'SELECT payload_json, expires_at FROM api_cache WHERE cache_key=?',
            (cache_key,),
        ).fetchone()
        if not row:
            return None
        payload_json, expires_at = row
        if float(expires_at) <= now:
            con.execute('DELETE FROM api_cache WHERE cache_key=?', (cache_key,))
            con.commit()
            return None
    try:
        data = json.loads(payload_json)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def set_cached(cache_key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return
    now = time.time()
    expires = now + ttl_seconds
    blob = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    with _LOCK, _connect() as con:
        con.execute(
            '''INSERT INTO api_cache(cache_key, expires_at, payload_json, created_at)
               VALUES(?,?,?,?)
               ON CONFLICT(cache_key) DO UPDATE SET
                 expires_at=excluded.expires_at,
                 payload_json=excluded.payload_json,
                 created_at=excluded.created_at''',
            (cache_key, expires, blob, now),
        )
        con.execute('DELETE FROM api_cache WHERE expires_at <= ?', (now,))
        con.commit()


def cache_status() -> dict[str, int]:
    now = time.time()
    with _LOCK, _connect() as con:
        total = con.execute('SELECT COUNT(*) FROM api_cache').fetchone()[0]
        valid = con.execute('SELECT COUNT(*) FROM api_cache WHERE expires_at > ?', (now,)).fetchone()[0]
    return {'entries_total': int(total), 'entries_valid': int(valid)}
