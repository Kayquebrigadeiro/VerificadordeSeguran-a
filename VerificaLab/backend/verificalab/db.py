"""SQLite com migrações explícitas.

Uma única conexão por processo, protegida por lock (worker + threads HTTP).
WAL para leituras concorrentes. Todos os caminhos são gerados pelo backend.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import config

_SQL_PART1 = """
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS environments (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        scheme TEXT NOT NULL,
        host TEXT NOT NULL,
        port INTEGER NOT NULL,
        kind TEXT NOT NULL DEFAULT 'lab',
        secret_header_name TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(project_id, name)
    );

    CREATE TABLE IF NOT EXISTS tools (
        id TEXT PRIMARY KEY,
        slug TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        upstream_path TEXT NOT NULL,
        language TEXT NOT NULL DEFAULT '',
        license TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'cataloged',
        capabilities_json TEXT NOT NULL DEFAULT '[]',
        import_formats_json TEXT NOT NULL DEFAULT '[]',
        notes TEXT NOT NULL DEFAULT '',
        cataloged_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS test_profiles (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('http','load','suite')),
        config_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(project_id, name)
    );

    CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        environment_id TEXT NOT NULL REFERENCES environments(id),
        profile_id TEXT NOT NULL REFERENCES test_profiles(id),
        kind TEXT NOT NULL,
        state TEXT NOT NULL,
        queued_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        cancel_requested INTEGER NOT NULL DEFAULT 0,
        exit_code INTEGER,
        tool_version TEXT,
        config_json TEXT NOT NULL,
        summary TEXT NOT NULL DEFAULT '',
        error_detail TEXT,
        progress REAL NOT NULL DEFAULT 0,
        interrupted_reason TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_runs_state ON runs(state);

    CREATE TABLE IF NOT EXISTS run_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
        ts TEXT NOT NULL,
        level TEXT NOT NULL,
        message TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS check_results (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
        seq INTEGER NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pass','fail','skip','error','unknown')),
        expected TEXT,
        observed TEXT,
        message TEXT NOT NULL DEFAULT '',
        evidence_json TEXT NOT NULL DEFAULT '{}',
        duration_ms REAL
    );
"""
_SQL_PART2 = """
    CREATE TABLE IF NOT EXISTS metrics (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        value REAL,
        value_text TEXT,
        unit TEXT,
        origin TEXT NOT NULL,
        samples INTEGER,
        population TEXT,
        discarded INTEGER NOT NULL DEFAULT 0,
        details_json TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS findings (
        id TEXT PRIMARY KEY,
        run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
        environment_id TEXT REFERENCES environments(id) ON DELETE CASCADE,
        severity TEXT NOT NULL CHECK(severity IN ('info','hypothesis','fail','error')),
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        hypothesis INTEGER NOT NULL DEFAULT 0,
        evidence_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS artifacts (
        id TEXT PRIMARY KEY,
        run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        filename TEXT NOT NULL,
        rel_path TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        size INTEGER NOT NULL,
        preview TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        action TEXT NOT NULL,
        entity TEXT NOT NULL,
        entity_id TEXT,
        detail_json TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS log_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        environment_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
        filename TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        line_no INTEGER NOT NULL,
        ts_raw TEXT,
        ts_epoch REAL,
        tz TEXT,
        level TEXT,
        source TEXT,
        message TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_logs_env ON log_entries(environment_id, ts_epoch);

    CREATE TABLE IF NOT EXISTS imports (
        id TEXT PRIMARY KEY,
        run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
        format TEXT NOT NULL,
        source_name TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        size INTEGER NOT NULL,
        records INTEGER NOT NULL DEFAULT 0,
        warnings_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL
    );
"""

_SQL_PART3 = """
    ALTER TABLE runs ADD COLUMN tool_id TEXT;
    ALTER TABLE runs ADD COLUMN target TEXT;
    ALTER TABLE runs ADD COLUMN ended_at TEXT;
    ALTER TABLE runs ADD COLUMN returncode INTEGER;
    ALTER TABLE runs ADD COLUMN ok INTEGER CHECK(ok IN (0,1));
    ALTER TABLE runs ADD COLUMN orchestrator_id TEXT;
    CREATE INDEX IF NOT EXISTS idx_runs_orchestrator ON runs(orchestrator_id);
"""

MIGRATIONS: list[str] = [_SQL_PART1 + _SQL_PART2, _SQL_PART3]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Database:
    def __init__(self, path: Path | None = None) -> None:
        config.ensure_dirs()
        self.path = Path(path) if path else config.DB_PATH
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.path), check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
        self.migrate()

    def migrate(self) -> None:
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            cur = self._conn.execute("SELECT MAX(version) AS v FROM schema_migrations")
            current = cur.fetchone()["v"] or 0
            for idx, script in enumerate(MIGRATIONS, start=1):
                if idx <= current:
                    continue
                self._conn.executescript(script)
                self._conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?,?)",
                    (idx, utcnow()),
                )

    @property
    def schema_version(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT MAX(version) AS v FROM schema_migrations")
            return int(cur.fetchone()["v"] or 0)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _norm_params(params: Iterable[Any]) -> tuple:
        """Normaliza parâmetros: string vira tupla de 1 (evita (x) sem vírgula)."""
        if params is None:
            return ()
        if isinstance(params, (str, bytes)):
            return (params,)
        return tuple(params)

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, self._norm_params(params))

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, self._norm_params(params)).fetchall()

    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, self._norm_params(params)).fetchone()

    def insert(self, table: str, values: dict[str, Any]) -> None:
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        self.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", values.values())

    def update(self, table: str, values: dict[str, Any], where: str,
               params: Iterable[Any]) -> None:
        sets = ", ".join(f"{k} = ?" for k in values)
        all_params = list(values.values()) + list(params)
        self.execute(f"UPDATE {table} SET {sets} WHERE {where}", all_params)

    def audit(self, action: str, entity: str, entity_id: str | None = None,
              detail: dict[str, Any] | None = None) -> None:
        self.insert("audit_events", {
            "ts": utcnow(), "action": action, "entity": entity,
            "entity_id": entity_id,
            "detail_json": json.dumps(detail or {}, ensure_ascii=False),
        })

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_db: Database | None = None
_db_lock = threading.Lock()


def get_db() -> Database:
    """Instância única do banco para o processo."""
    global _db
    with _db_lock:
        if _db is None:
            _db = Database()
        return _db
