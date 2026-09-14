from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import BASE_DIR

DB_PATH = BASE_DIR / 'data' / 'lifecircle.db'
_LOCK = threading.Lock()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _LOCK, _connect() as con:
        con.execute('''
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                mode TEXT NOT NULL,
                center_name TEXT NOT NULL,
                city TEXT NOT NULL,
                health_score REAL,
                payload_json TEXT NOT NULL,
                result_json TEXT NOT NULL
            )
        ''')
        con.commit()


def save_analysis(payload: dict[str, Any], result: dict[str, Any]) -> int:
    created = datetime.now(timezone.utc).isoformat()
    with _LOCK, _connect() as con:
        cur = con.execute(
            'INSERT INTO analyses(created_at,mode,center_name,city,health_score,payload_json,result_json) VALUES(?,?,?,?,?,?,?)',
            (
                created, payload['mode'], payload['center_name'], payload['city'], result.get('health_score'),
                json.dumps(payload, ensure_ascii=False), json.dumps(result, ensure_ascii=False),
            ),
        )
        con.commit()
        return int(cur.lastrowid)


def get_analysis(analysis_id: int) -> dict[str, Any] | None:
    with _connect() as con:
        row = con.execute('SELECT * FROM analyses WHERE id=?', (analysis_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data['payload'] = json.loads(data.pop('payload_json'))
    data['result'] = json.loads(data.pop('result_json'))
    return data


def list_analyses(limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as con:
        rows = con.execute(
            'SELECT id,created_at,mode,center_name,city,health_score FROM analyses ORDER BY id DESC LIMIT ?',
            (min(100, max(1, limit)),),
        ).fetchall()
    return [dict(r) for r in rows]


def clear_db_for_tests() -> None:
    # Deleting an SQLite file is racy on Windows when a recently closed
    # TestClient still has a connection handle in teardown.  Clearing rows in
    # one transaction keeps the test helper deterministic without changing
    # the production schema or relying on Unix unlink semantics.
    init_db()
    with _LOCK, _connect() as con:
        con.execute('DELETE FROM analyses')
        con.execute("DELETE FROM sqlite_sequence WHERE name='analyses'")
        con.commit()
