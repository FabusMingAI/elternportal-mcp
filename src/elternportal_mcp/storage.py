"""Local SQLite snapshots, extracted documents and user-managed tasks."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Store:
    def __init__(self, directory: Path):
        directory = directory.expanduser()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / "state.sqlite3"
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        if os.name == "posix":
            path.chmod(0o600)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA busy_timeout = 5000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS snapshots (school TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS documents (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS item_states (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            PRAGMA user_version = 1;
        """)

    def close(self):
        self.db.close()

    def get(self, table: str, key: str) -> dict[str, Any] | None:
        column = self._column(table)
        row = self.db.execute(f"SELECT payload FROM {table} WHERE {column} = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def _column(table: str) -> str:
        columns = {"snapshots": "school", "documents": "key", "tasks": "id", "item_states": "id"}
        if table not in columns:
            raise ValueError("Unknown storage table")
        return columns[table]

    def put(self, table: str, key: str, value: dict[str, Any]):
        column = self._column(table)
        with self.db:
            self.db.execute(
                f"INSERT OR REPLACE INTO {table} ({column},payload) VALUES (?,?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )

    def tasks(self, child_id: str | None = None) -> list[dict]:
        rows = [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM tasks ORDER BY id")]
        return sorted(
            [r for r in rows if child_id is None or r["child_id"] == child_id],
            key=lambda r: (r.get("due") or "9999", r["created_at"]),
        )

    def add_task(self, child_id: str, title: str, **fields) -> dict:
        task = {
            "id": str(uuid.uuid4()),
            "child_id": child_id,
            "title": title,
            "status": "open",
            "created_at": now(),
            "updated_at": now(),
            "local_only": True,
            **fields,
        }
        self.put("tasks", task["id"], task)
        return task
