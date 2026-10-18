"""Opening, checking, backing up and migrating the SQLite database.

open_database() is the only way the app gets a migrated database. It refuses
to touch a database written by a newer WiFiDrop, backs up before every
migration, and runs each migration in its own transaction.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .ids import new_id, now_ms
from .migrations import MIGRATIONS, Migration

log = logging.getLogger(__name__)

LATEST_SCHEMA = MIGRATIONS[-1].version
DEFAULT_KEEP_BACKUPS = 10

# Created outside the numbered migrations so migration 1 can be recorded.
# Never change this statement.
_BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version      INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    checksum     TEXT NOT NULL,
    applied_at   INTEGER NOT NULL,
    app_version  TEXT NOT NULL
) STRICT
"""


class DatabaseError(RuntimeError):
    """The database can't be used. The message is shown to the admin."""


class DatabaseTooNewError(DatabaseError):
    def __init__(self, found: int, supported: int):
        super().__init__(
            f"This data was written by a newer WiFiDrop (schema {found}); this version supports up to "
            f"schema {supported}. Install the newer WiFiDrop again, or restore a backup."
        )
        self.found, self.supported = found, supported


class MigrationChecksumError(DatabaseError):
    pass


class MigrationFailedError(DatabaseError):
    def __init__(self, version: int, backup: Path | None, cause: Exception):
        where = f" Your data is unchanged; a backup is at {backup}." if backup else " Your data is unchanged."
        super().__init__(f"Upgrading the database to schema {version} failed: {cause}.{where}")
        self.version, self.backup = version, backup


class DatabaseCorruptError(DatabaseError):
    pass


@dataclass
class OpenReport:
    from_version: int
    to_version: int
    backup: Path | None
    created: bool


def connect(path: Path) -> sqlite3.Connection:
    """A connection with WiFiDrop's settings. Autocommit mode: use explicit BEGIN/COMMIT."""
    conn = sqlite3.connect(path, isolation_level=None, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = FULL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    """BEGIN IMMEDIATE ... COMMIT, rolled back on any error."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def split_sql(script: str) -> list[str]:
    statements, buf = [], ""
    for line in script.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip():
                statements.append(buf.strip())
            buf = ""
    if buf.strip() and not all(l.strip().startswith("--") or not l.strip() for l in buf.splitlines()):
        raise ValueError("migration ends with an incomplete SQL statement")
    return statements


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def backup_database(conn: sqlite3.Connection, backup_dir: Path, label: str, keep: int = DEFAULT_KEEP_BACKUPS) -> Path:
    """Consistent online copy via SQLite's backup API, then prune old copies."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    final = backup_dir / f"wifidrop-{stamp}-{label}.db"
    tmp = final.with_suffix(".db.partial")
    dest = sqlite3.connect(tmp)
    try:
        conn.backup(dest)
    finally:
        dest.close()
    tmp.replace(final)
    for old in sorted(backup_dir.glob("wifidrop-*.db"))[:-keep]:
        old.unlink(missing_ok=True)
    log.info("Database backed up to %s", final)
    return final


def _check_integrity(conn: sqlite3.Connection) -> None:
    rows = [r[0] for r in conn.execute("PRAGMA quick_check").fetchall()]
    if rows != ["ok"]:
        raise DatabaseCorruptError("The database failed its integrity check: " + "; ".join(rows[:5]))


def _verify_applied(conn: sqlite3.Connection, current: int) -> None:
    known = {m.version: m for m in MIGRATIONS}
    applied = {r["version"]: r for r in conn.execute("SELECT version, name, checksum FROM schema_migrations")}
    for version in range(1, current + 1):
        row = applied.get(version)
        if row is None:
            raise DatabaseCorruptError(f"Schema {current} is recorded but migration {version} is missing.")
        if row["checksum"] != known[version].checksum:
            raise MigrationChecksumError(
                f"Migration {version} ({row['name']}) differs from the one that ran on this database. "
                "Released migrations must never be edited."
            )


def _apply(conn: sqlite3.Connection, m: Migration, app_version: str) -> None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        for statement in split_sql(m.sql):
            conn.execute(statement)
        problems = conn.execute("PRAGMA foreign_key_check").fetchall()
        if problems:
            raise DatabaseError(f"foreign key check failed in table {problems[0][0]}")
        conn.execute(
            "INSERT INTO schema_migrations (version, name, checksum, applied_at, app_version) VALUES (?, ?, ?, ?, ?)",
            (m.version, m.name, m.checksum, now_ms(), app_version),
        )
        conn.execute(f"PRAGMA user_version = {int(m.version)}")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def _record_meta(conn: sqlite3.Connection, app_version: str) -> None:
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('install_id', ?)", (new_id(),))
    conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('first_app_version', ?)", (app_version,))
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('last_app_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (app_version,),
    )
    conn.execute("COMMIT")


def open_database(
    path: Path,
    app_version: str,
    backup_dir: Path,
    keep_backups: int = DEFAULT_KEEP_BACKUPS,
) -> tuple[sqlite3.Connection, OpenReport]:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists() and path.stat().st_size > 0
    conn = connect(path)
    try:
        if existed:
            _check_integrity(conn)
        current = schema_version(conn)
        if current > LATEST_SCHEMA:
            raise DatabaseTooNewError(current, LATEST_SCHEMA)
        if current == 0 and existed:
            tables = conn.execute("SELECT count(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND name != 'schema_migrations'").fetchone()[0]
            if tables:
                raise DatabaseError(f"{path} is not a WiFiDrop database.")

        conn.execute(_BOOTSTRAP)
        _verify_applied(conn, current)

        pending = [m for m in MIGRATIONS if m.version > current]
        backup = None
        if pending and current > 0:
            backup = backup_database(conn, backup_dir, f"schema{current}", keep_backups)
        for m in pending:
            log.info("Applying migration %s (%s)", m.version, m.name)
            try:
                _apply(conn, m, app_version)
            except Exception as exc:
                raise MigrationFailedError(m.version, backup, exc) from exc

        _record_meta(conn, app_version)
        return conn, OpenReport(current, schema_version(conn), backup, created=not existed)
    except BaseException:
        conn.close()
        raise
