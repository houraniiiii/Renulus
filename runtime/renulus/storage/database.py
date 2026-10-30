"""Canonical SQLite authority, with explicit atomic writes and checked migrations."""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from threading import Lock
from typing import Iterable

from .publication import check_publication

SUPPORTED_SCHEMA = 2
BACKEND_SELECTOR = ".renulus-backend-selector.json"


def require_python_authority(path: Path):
    """Python is the canonical writer only while its profile has no backend selector.

    After the profile-wide handoff the selector names the TypeScript writer; the
    original profile and every generation beneath it are then refused here, so
    no Python process (server or worker) can open a second canonical writer.
    """
    profile = path.parent.parent
    roots = [profile]
    if profile.parent.name == "generations":
        roots.append(profile.parent.parent)
    if any((root / BACKEND_SELECTOR).exists() for root in roots):
        raise RuntimeError("backend_canonical_authority_ts")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Database:
    def __init__(self, path: str | Path, *, migration_inventory: dict[str, str] | None = None):
        self.path = Path(path).resolve()
        require_python_authority(self.path)
        self._writer_state = Lock()
        self._active_writers = 0
        self._writers_paused = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > SUPPORTED_SCHEMA:
                raise RuntimeError("This profile needs a newer Renulus version; downgrade refused")
            if migration_inventory is not None and conn.execute("SELECT 1 FROM sqlite_master WHERE name='migration_ledger' AND type='table'").fetchone():
                self.check_migration_inventory(migration_inventory)
            conn.execute("PRAGMA journal_mode=WAL")
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
        # Rechecked per connection: a Database built before the handoff cannot keep writing after it.
        require_python_authority(self.path)
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA secure_delete=ON")
        return conn

    @contextmanager
    def writer_admission(self):
        """Logical ownership shared by normal and fixed interruption writers."""
        with self._writer_state:
            if self._writers_paused:
                raise RuntimeError("Canonical writer quiescence is active")
            self._active_writers += 1
        try:
            yield
        finally:
            with self._writer_state:
                self._active_writers -= 1

    @contextmanager
    def transaction(self):
        with self.writer_admission():
            conn = self.connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                check_publication(self, conn)
                yield conn
                check_publication(self, conn)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()

    @contextmanager
    def quiesce_writes(self):
        """Seal canonical admission without holding a physical lock across IPC.

        Initial harness activation uses this after module assembly and before
        producers start. An admitted transaction must settle before retrying;
        this method never waits on an active writer or acquires a SQLite lock.
        """
        with self._writer_state:
            if self._writers_paused or self._active_writers:
                raise RuntimeError("Canonical writer quiescence requires settled writers")
            self._writers_paused = True
        try:
            yield
        finally:
            with self._writer_state:
                self._writers_paused = False

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
            for character in script:
                statement += character
                if character == ";" and sqlite3.complete_statement(statement):
                    conn.execute(statement)
                    statement = ""
            # A trailing SQL comment has no executable statement.
            import re
            remainder = re.sub(r"/\*.*?\*/|--[^\n]*", "", statement, flags=re.S)
            if remainder.strip():
                raise RuntimeError(f"Incomplete migration: {name}")
            conn.execute("INSERT INTO migration_ledger VALUES(?,?,?)", (name, checksum, utc_now()))

    def check_migration_inventory(self, inventory: dict[str, str]):
        """Refuse unknown or changed applied migrations before module writes."""
        for row in self.fetch_all("SELECT name,checksum FROM migration_ledger"):
            script = inventory.get(row["name"])
            if script is None:
                raise RuntimeError("This profile has migrations unknown to this app; downgrade refused")
            if hashlib.sha256(script.encode()).hexdigest() != row["checksum"]:
                raise RuntimeError(f"Applied migration changed: {row['name']}; add a new migration")

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
