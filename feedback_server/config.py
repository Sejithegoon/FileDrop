"""Feedback server settings, read from environment variables (see README.md)."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    data_dir: Path = Path("feedback-data")
    site_dir: Path | None = None           # serve the static website too (handy for small deployments)
    admin_password: str = ""               # required to use the admin page
    public_url: str = ""                   # e.g. https://example.ca, used in unsubscribe links
    trust_proxy: bool = False              # read the client IP from X-Forwarded-For (behind nginx)
    turnstile_secret: str = ""             # optional Cloudflare Turnstile secret key
    max_attachment_mb: int = 5
    retention_days: int = 730              # submissions older than this are deleted
    rate_limit: int = 5                    # submissions per IP per window, per form
    rate_window_s: int = 600
    min_fill_seconds: float = 2.0          # forms submitted faster than this are treated as bots
    smtp_host: str = ""                    # optional: email the owner about new submissions
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notify_to: str = ""
    notify_from: str = ""
    ip_salt: str = field(default_factory=lambda: secrets.token_hex(16))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "feedback.db"

    @property
    def attachment_dir(self) -> Path:
        return self.data_dir / "attachments"


def from_env() -> Config:
    e = os.environ
    c = Config()
    c.data_dir = Path(e.get("FEEDBACK_DATA_DIR", c.data_dir))
    if e.get("FEEDBACK_SITE_DIR"):
        c.site_dir = Path(e["FEEDBACK_SITE_DIR"])
    c.admin_password = e.get("FEEDBACK_ADMIN_PASSWORD", "")
    c.public_url = e.get("FEEDBACK_PUBLIC_URL", "").rstrip("/")
    c.trust_proxy = e.get("FEEDBACK_TRUST_PROXY") == "1"
    c.turnstile_secret = e.get("FEEDBACK_TURNSTILE_SECRET", "")
    c.max_attachment_mb = int(e.get("FEEDBACK_MAX_ATTACHMENT_MB", c.max_attachment_mb))
    c.retention_days = int(e.get("FEEDBACK_RETENTION_DAYS", c.retention_days))
    c.smtp_host = e.get("FEEDBACK_SMTP_HOST", "")
    c.smtp_port = int(e.get("FEEDBACK_SMTP_PORT", c.smtp_port))
    c.smtp_user = e.get("FEEDBACK_SMTP_USER", "")
    c.smtp_password = e.get("FEEDBACK_SMTP_PASSWORD", "")
    c.notify_to = e.get("FEEDBACK_NOTIFY_TO", "")
    c.notify_from = e.get("FEEDBACK_NOTIFY_FROM", c.smtp_user)
    if e.get("FEEDBACK_IP_SALT"):
        c.ip_salt = e["FEEDBACK_IP_SALT"]
    return c
