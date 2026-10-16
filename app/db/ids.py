"""Identifiers and timestamps shared by every table.

IDs are UUIDv7-style: 48 bits of millisecond time + 80 random bits, as 32 hex
characters. They sort by creation time and never collide across installs.
Timestamps are integer UTC milliseconds.
"""

from __future__ import annotations

import secrets
import time


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def new_id() -> str:
    ts = now_ms() & ((1 << 48) - 1)
    rand = secrets.randbits(80)
    value = (ts << 80) | rand
    # Set version (7) and variant (10xx) bits so the value is a valid UUIDv7.
    value = (value & ~(0xF << 76)) | (0x7 << 76)
    value = (value & ~(0x3 << 62)) | (0x2 << 62)
    return f"{value:032x}"
