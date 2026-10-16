"""File, folder, space and username rules.

name_key() decides which names count as "the same" (unique per folder). It is
stored in the database, so changing it later needs a migration that recomputes
every key. Treat it as frozen.
"""

from __future__ import annotations

import re
import unicodedata

MAX_NAME_LENGTH = 255
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{1,31}$")


class InvalidName(ValueError):
    pass


def name_key(name: str) -> str:
    """Case- and normalization-insensitive key: "Photo.JPG" and "photo.jpg" collide."""
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", name).casefold())


def clean_name(name: str) -> str:
    """Validate a file or folder name and return it NFC-normalized.

    Names never touch the disk (ID-based storage), so Windows-reserved
    characters and names are allowed. Only "/" and "\\" (path separators in
    the UI and ZIP files), control characters, and "." / ".." are refused.
    """
    name = unicodedata.normalize("NFC", name).strip()
    if not name:
        raise InvalidName("Name can't be empty.")
    if len(name) > MAX_NAME_LENGTH:
        raise InvalidName(f"Name can't be longer than {MAX_NAME_LENGTH} characters.")
    if name in (".", ".."):
        raise InvalidName("Name can't be '.' or '..'.")
    if "/" in name or "\\" in name:
        raise InvalidName("Name can't contain / or \\.")
    if _CONTROL.search(name):
        raise InvalidName("Name can't contain control characters.")
    return name


def username_key(username: str) -> str:
    return username.strip().lower()


def clean_username(username: str) -> str:
    """2-32 characters: a-z, 0-9, dot, dash, underscore; starts with a letter or digit."""
    key = username_key(username)
    if not _USERNAME.match(key):
        raise InvalidName("Username must be 2-32 characters: letters, digits, '.', '-' or '_'.")
    return key
