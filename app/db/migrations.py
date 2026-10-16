"""Forward-only schema migrations.

Rules (see the spec's "Safe upgrades"):
- Append new migrations to MIGRATIONS. Never edit or reorder a released one;
  its checksum is stored in every database it has run on.
- Add first: new tables and columns now, drop old columns in a later release.
- No semicolons inside SQL comments (statements are split on them).
- The runner checks foreign keys after each migration, so a table rebuild
  must leave every reference valid.

The SQL lives in this module (not .sql files) so PyInstaller always bundles it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


_0001_INITIAL = """
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE users (
    id                    TEXT PRIMARY KEY,
    username              TEXT NOT NULL,
    username_key          TEXT NOT NULL UNIQUE,
    display_name          TEXT NOT NULL,
    password_hash         TEXT NOT NULL,
    role                  TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    status                TEXT NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active', 'suspended', 'pending_deletion')),
    must_change_password  INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0, 1)),
    failed_logins         INTEGER NOT NULL DEFAULT 0 CHECK (failed_logins >= 0),
    locked_until          INTEGER,
    password_changed_at   INTEGER NOT NULL,
    created_at            INTEGER NOT NULL,
    updated_at            INTEGER NOT NULL,
    purge_after           INTEGER,
    CHECK ((status = 'pending_deletion') = (purge_after IS NOT NULL))
) STRICT;

-- Usernames of purged accounts stay reserved for a while.
CREATE TABLE reserved_usernames (
    username_key    TEXT PRIMARY KEY,
    reserved_until  INTEGER NOT NULL
) STRICT;

-- A private space belongs to one user. Shared spaces are made by admins.
-- Quotas live here only: a private space's quota is its owner's quota.
CREATE TABLE spaces (
    id             TEXT PRIMARY KEY,
    kind           TEXT NOT NULL CHECK (kind IN ('private', 'shared')),
    name           TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 255),
    name_key       TEXT NOT NULL,
    owner_user_id  TEXT REFERENCES users(id) ON DELETE CASCADE,
    quota_bytes    INTEGER CHECK (quota_bytes IS NULL OR quota_bytes >= 0),
    status         TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending_deletion')),
    purge_after    INTEGER,
    created_at     INTEGER NOT NULL,
    created_by     TEXT REFERENCES users(id) ON DELETE SET NULL,
    CHECK ((kind = 'private') = (owner_user_id IS NOT NULL)),
    CHECK ((status = 'pending_deletion') = (purge_after IS NOT NULL))
) STRICT;

CREATE UNIQUE INDEX spaces_one_private_per_user ON spaces(owner_user_id) WHERE kind = 'private';
CREATE UNIQUE INDEX spaces_shared_name ON spaces(name_key) WHERE kind = 'shared';

CREATE TABLE space_members (
    space_id    TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    level       TEXT NOT NULL CHECK (level IN ('view', 'upload', 'manage')),
    granted_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
    granted_at  INTEGER NOT NULL,
    PRIMARY KEY (space_id, user_id)
) STRICT;

CREATE INDEX space_members_user ON space_members(user_id);

CREATE TRIGGER space_members_shared_only
BEFORE INSERT ON space_members
WHEN (SELECT kind FROM spaces WHERE id = NEW.space_id) IS NOT 'shared'
BEGIN
    SELECT RAISE(ABORT, 'members can only be added to shared spaces');
END;

-- Files and folders. File contents live on disk at blobs/<blob_id>.
-- Each space has exactly one root folder (parent_id NULL).
-- Trashing a folder sets trashed_at on that folder only, its children are hidden with it.
CREATE TABLE items (
    id               TEXT PRIMARY KEY,
    space_id         TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    parent_id        TEXT REFERENCES items(id) ON DELETE CASCADE,
    kind             TEXT NOT NULL CHECK (kind IN ('folder', 'file')),
    name             TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 255),
    name_key         TEXT NOT NULL,
    size_bytes       INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    blob_id          TEXT UNIQUE,
    sha256           TEXT,
    content_type     TEXT,
    state            TEXT NOT NULL DEFAULT 'ok' CHECK (state IN ('ok', 'missing')),
    created_by       TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_by_name  TEXT NOT NULL,
    created_at       INTEGER NOT NULL,
    modified_at      INTEGER NOT NULL,
    trashed_at       INTEGER,
    trashed_by       TEXT REFERENCES users(id) ON DELETE SET NULL,
    CHECK ((kind = 'file') = (blob_id IS NOT NULL)),
    CHECK (kind = 'file' OR size_bytes = 0),
    CHECK (parent_id IS NOT NULL OR (kind = 'folder' AND trashed_at IS NULL))
) STRICT;

CREATE UNIQUE INDEX items_one_root_per_space ON items(space_id) WHERE parent_id IS NULL;
CREATE UNIQUE INDEX items_unique_name ON items(parent_id, name_key)
    WHERE trashed_at IS NULL AND parent_id IS NOT NULL;
CREATE INDEX items_space ON items(space_id);
CREATE INDEX items_trash ON items(space_id, trashed_at) WHERE trashed_at IS NOT NULL;
CREATE INDEX items_created_by ON items(created_by);

CREATE TRIGGER items_parent_insert
BEFORE INSERT ON items
WHEN NEW.parent_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM items p WHERE p.id = NEW.parent_id AND p.kind = 'folder' AND p.space_id = NEW.space_id
)
BEGIN
    SELECT RAISE(ABORT, 'parent must be a folder in the same space');
END;

-- Cross-space moves update parent_id and space_id of the moved item together,
-- then space_id of its descendants (which does not fire this trigger).
CREATE TRIGGER items_parent_update
BEFORE UPDATE OF parent_id ON items
WHEN NEW.parent_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM items p WHERE p.id = NEW.parent_id AND p.kind = 'folder' AND p.space_id = NEW.space_id
)
BEGIN
    SELECT RAISE(ABORT, 'parent must be a folder in the same space');
END;

-- Only the hash of a session token is stored.
CREATE TABLE sessions (
    id             TEXT PRIMARY KEY,
    token_hash     TEXT NOT NULL UNIQUE,
    user_id        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at     INTEGER NOT NULL,
    last_seen_at   INTEGER NOT NULL,
    expires_at     INTEGER NOT NULL,
    ip             TEXT NOT NULL,
    user_agent     TEXT NOT NULL DEFAULT '',
    revoked_at     INTEGER,
    revoke_reason  TEXT
) STRICT;

CREATE INDEX sessions_user ON sessions(user_id);

CREATE TABLE uploads (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    space_id        TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    parent_id       TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    name            TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 255),
    size_bytes      INTEGER NOT NULL CHECK (size_bytes >= 0),
    chunk_size      INTEGER NOT NULL CHECK (chunk_size > 0),
    received_bytes  INTEGER NOT NULL DEFAULT 0 CHECK (received_bytes >= 0),
    sha256          TEXT,
    on_conflict     TEXT NOT NULL CHECK (on_conflict IN ('replace', 'keep_both', 'skip')),
    status          TEXT NOT NULL CHECK (status IN
                    ('queued', 'in_progress', 'interrupted', 'finalising', 'completed', 'cancelled', 'failed')),
    error_code      TEXT,
    item_id         TEXT REFERENCES items(id) ON DELETE SET NULL,
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL,
    expires_at      INTEGER NOT NULL
) STRICT;

CREATE INDEX uploads_user ON uploads(user_id);
CREATE INDEX uploads_status ON uploads(status);

-- Values are JSON. Unknown keys are kept, so older and newer versions share them.
CREATE TABLE settings (
    key         TEXT PRIMARY KEY,
    value_json  TEXT NOT NULL CHECK (json_valid(value_json)),
    updated_at  INTEGER NOT NULL,
    updated_by  TEXT REFERENCES users(id) ON DELETE SET NULL
) STRICT;

-- No foreign keys: entries outlive the accounts they mention.
CREATE TABLE audit_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    at             INTEGER NOT NULL,
    actor_user_id  TEXT,
    actor_name     TEXT NOT NULL,
    actor_ip       TEXT,
    action         TEXT NOT NULL,
    target_type    TEXT,
    target_id      TEXT,
    target_name    TEXT,
    details_json   TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(details_json)),
    result         TEXT NOT NULL CHECK (result IN ('ok', 'denied', 'error'))
) STRICT;

CREATE INDEX audit_at ON audit_log(at);
CREATE INDEX audit_actor ON audit_log(actor_user_id, at);

CREATE TRIGGER audit_log_append_only
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit log is append-only');
END;
"""

MIGRATIONS: list[Migration] = [
    Migration(1, "initial", _0001_INITIAL),
]
