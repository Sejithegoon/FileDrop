"""ID-based file store: blobs/ab/cd/<blob id>, uploads staged in staging/."""

from __future__ import annotations

import logging
import secrets
import shutil
from pathlib import Path

log = logging.getLogger(__name__)


class Storage:
    def __init__(self, root: Path):
        self.root = root
        self.blobs = root / "blobs"
        self.staging = root / "staging"

    def ensure(self) -> None:
        self.blobs.mkdir(parents=True, exist_ok=True)
        self.staging.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_blob_id() -> str:
        return secrets.token_hex(16)

    def blob_path(self, blob_id: str) -> Path:
        return self.blobs / blob_id[:2] / blob_id[2:4] / blob_id

    def staging_path(self, upload_id: str) -> Path:
        return self.staging / f"{upload_id}.part"

    def delete_blobs(self, blob_ids) -> None:
        for bid in blob_ids:
            try:
                self.blob_path(bid).unlink(missing_ok=True)
            except OSError as exc:  # file in use; the nightly check will retry
                log.warning("Could not delete blob %s: %s", bid, exc)

    def disk(self) -> dict:
        u = shutil.disk_usage(self.root)
        return {"total": u.total, "free": u.free, "used": u.used}
