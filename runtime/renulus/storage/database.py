"""Canonical SQLite authority, with explicit atomic writes and checked migrations."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from typing import Iterable

SUPPORTED_SCHEMA = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > SUPPORTED_SCHEMA:
                raise RuntimeError("This profile needs a newer Renulus version; downgrade refused")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS migration_ledger(
                    name TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS preferences(
                    key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS deletion_ledger(
                    entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, deleted_at TEXT NOT NULL,
                    PRIMARY KEY(entity_type, entity_id));
                CREATE TABLE IF NOT EXISTS learning_evidence(
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, topic_id TEXT, entity_id TEXT,
                    payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
            """)
            conn.execute(f"PRAGMA user_version={SUPPORTED_SCHEMA}")

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA secure_delete=ON")
        return conn

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def fetch_one(self, sql: str, parameters: Iterable = ()) -> dict | None:
        conn = self.connect()
        try:
            row = conn.execute(sql, tuple(parameters)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def fetch_all(self, sql: str, parameters: Iterable = ()) -> list[dict]:
        conn = self.connect()
        try:
            return [dict(row) for row in conn.execute(sql, tuple(parameters)).fetchall()]
        finally:
            conn.close()

    def execute(self, sql: str, parameters: Iterable = ()) -> int:
        with self.transaction() as conn:
            return conn.execute(sql, tuple(parameters)).rowcount

    def apply_migration(self, name: str, script: str):
        checksum = hashlib.sha256(script.encode()).hexdigest()
        with self.transaction() as conn:
            previous = conn.execute("SELECT checksum FROM migration_ledger WHERE name=?",
                                    (name,)).fetchone()
            if previous:
                if previous[0] != checksum:
                    raise RuntimeError(f"Applied migration changed: {name}; add a new migration")
                return
            # executescript commits implicitly; split complete SQLite statements to keep atomicity.
            statement = ""
            for line in script.splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    conn.execute(statement)
                    statement = ""
            if statement.strip():
                raise RuntimeError(f"Incomplete migration: {name}")
            conn.execute("INSERT INTO migration_ledger VALUES(?,?,?)", (name, checksum, utc_now()))

    def mark_deleted(self, entity_type: str, entity_id: str, conn=None):
        sql = "INSERT OR REPLACE INTO deletion_ledger VALUES(?,?,?)"
        params = (entity_type, entity_id, utc_now())
        if conn is not None:
            conn.execute(sql, params)
        else:
            self.execute(sql, params)

    def is_deleted(self, entity_type: str, entity_id: str) -> bool:
        return self.fetch_one("SELECT 1 FROM deletion_ledger WHERE entity_type=? AND entity_id=?",
                              (entity_type, entity_id)) is not None
