"""Preview thumbnails: small JPEGs for the file lists.

The PC makes them itself for the picture formats Pillow reads. iPhone photos (HEIC) and videos need codecs
WiFiDrop doesn't ship, so the phone app makes those on the phone and sends them along after the upload.
Thumbnails sit next to the blobs (storage/thumbs/) and are deleted with them. A ".none" marker remembers
files that can't be previewed, so they aren't tried on every listing.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from app.core.errors import ApiError
from app.core.storage import Storage

log = logging.getLogger(__name__)

SIZE = 400  # longest side, in pixels: sharp on phones at list size
QUALITY = 78
MAX_SOURCE_BYTES = 80 * 1024 * 1024  # bigger pictures aren't worth decoding for a thumbnail
MAX_UPLOADED_BYTES = 512 * 1024
MAX_PIXELS = 120_000_000  # refuse "decompression bombs"

SERVER_MADE = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
PHONE_MADE = {".heic", ".heif", ".mov", ".mp4", ".m4v", ".3gp", ".avi", ".mkv", ".webm", ".dng"}

# Types safe to show inside the page (inline). Never SVG or HTML: those can run scripts.
INLINE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp",
                "video/mp4", "video/quicktime", "video/webm", "audio/mpeg", "audio/mp4", "audio/x-m4a", "audio/wav"}


def kind_of(name: str) -> str | None:
    ext = Path(name).suffix.lower()
    if ext in SERVER_MADE:
        return "server"
    if ext in PHONE_MADE:
        return "phone"
    return None


def _encode(img) -> bytes:
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(img)
    img.thumbnail((SIZE, SIZE), Image.LANCZOS)
    if img.mode not in ("RGB", "L"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    return out.getvalue()


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def get(storage: Storage, item) -> Path | None:
    """The thumbnail for a file, making it now if the PC can; None when there's no preview."""
    if item["kind"] != "file" or not item["blob_id"]:
        return None
    path = storage.thumb_path(item["blob_id"])
    if path.exists():
        return path
    if kind_of(item["name"]) != "server" or path.with_suffix(".none").exists():
        return None
    source = storage.blob_path(item["blob_id"])
    try:
        if not source.exists() or source.stat().st_size > MAX_SOURCE_BYTES:
            return None
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = MAX_PIXELS
        with Image.open(source) as img:
            img.seek(0)  # first frame of a GIF
            _write(path, _encode(img))
        return path
    except Exception as exc:  # unreadable or unusual picture: remember, show the icon
        log.info("No preview for %s: %s", item["id"], exc)
        try:
            _write(path.with_suffix(".none"), b"")
        except OSError:
            pass
        return None


def save_from_phone(storage: Storage, item, data: bytes) -> None:
    """A thumbnail the phone app made (HEIC photos, videos). Re-encoded here, so only a plain JPEG is kept."""
    if item["kind"] != "file" or not item["blob_id"]:
        raise ApiError(400, "NOT_A_FILE", "Only files have previews.")
    if kind_of(item["name"]) is None:
        raise ApiError(400, "NO_PREVIEW", "This kind of file doesn't have a preview.")
    if not data or len(data) > MAX_UPLOADED_BYTES:
        raise ApiError(413, "PREVIEW_TOO_LARGE", "The preview is too large.")
    try:
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = 20_000_000
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError(img.format)
            encoded = _encode(img)
    except ApiError:
        raise
    except Exception:
        raise ApiError(400, "BAD_PREVIEW", "That preview isn't a picture.")
    path = storage.thumb_path(item["blob_id"])
    _write(path, encoded)
    path.with_suffix(".none").unlink(missing_ok=True)
