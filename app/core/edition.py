"""Free and Pro editions.

A Pro licence is a JSON payload signed with an Ed25519 key that exists only on the
licence server. The app checks the signature with the public keys below, so editing
the database or a settings file can't turn Pro on.

The licence server can also send a signed status for this PC (active, revoked, or
"limit" when the licence is on too many PCs). Being offline, or the server being
down, never turns Pro off: only a signed "revoked" or "limit" answer does.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import asdict, dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app import BUILD_DATE

FREE_MAX_USERS = 5

# Raw 32-byte Ed25519 public keys, base64. New keys are added to the front; old ones
# stay so licences issued before a key change keep working.
PUBLIC_KEYS: list[str] = [
    "8Cgb3LhmrkK3Fdu9BsJlxuf4B9zgXrc0Yok5kRRAVuA=",
]

BEGIN, END = "-----BEGIN WIFIDROP LICENCE-----", "-----END WIFIDROP LICENCE-----"
# Any BEGIN/END armour line, including licences issued as "FILEDROP LICENCE" before the rename.
ARMOUR = re.compile(r"-----(?:BEGIN|END) [A-Z]+ LICENCE-----")


class LicenceError(ValueError):
    pass


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _verify(blob: str, keys: list[str] | None = None) -> dict:
    """Checks "<payload>.<signature>" (base64url) and returns the payload."""
    try:
        payload_b64, sig_b64 = blob.split(".")
        payload, sig = _b64d(payload_b64), _b64d(sig_b64)
    except (ValueError, TypeError):
        raise LicenceError("This doesn't look like a WiFiDrop licence. Paste the whole text, including the BEGIN and END lines.")
    for key in keys if keys is not None else PUBLIC_KEYS:
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(key)).verify(sig, payload)
        except (InvalidSignature, ValueError):
            continue
        try:
            data = json.loads(payload)
        except ValueError:
            break
        if isinstance(data, dict):
            return data
        break
    raise LicenceError("This licence isn't valid. Check you copied all of it, or contact support.")


def parse_licence(text: str, keys: list[str] | None = None) -> dict:
    """Accepts the licence block as emailed (extra spaces and line breaks are fine)."""
    body = re.sub(r"\s+", "", ARMOUR.sub("", text))
    data = _verify(body, keys)
    if data.get("typ") != "licence" or data.get("v") != 1 or not data.get("lid") or data.get("ed") != "pro":
        raise LicenceError("This licence isn't valid for this version of WiFiDrop.")
    return data


def normalise(text: str) -> str:
    """The licence in its standard form, for storing and sending to the licence server."""
    body = re.sub(r"\s+", "", ARMOUR.sub("", text))
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return "\n".join([BEGIN, *lines, END])


def parse_status(blob: str, licence_id: str, install_id: str, keys: list[str] | None = None) -> dict | None:
    """A signed status from the licence server, or None if it's not for this licence and PC."""
    try:
        data = _verify(blob, keys)
    except LicenceError:
        return None
    if data.get("typ") != "status" or data.get("lid") != licence_id or data.get("iid") != install_id:
        return None
    if data.get("st") not in ("active", "inactive", "revoked", "limit"):
        return None
    return data


@dataclass
class Capabilities:
    edition: str = "free"  # "free" or "pro": what is unlocked right now
    state: str = "free"  # free, pro, revoked, limit, updates_ended, invalid
    message: str = ""
    licence_id: str | None = None
    licensee: str | None = None
    updates_until: str | None = None
    max_activations: int | None = None
    activated: bool = False  # the licence server has confirmed this PC
    checked_at: str | None = None  # time of the last signed status

    @property
    def pro(self) -> bool:
        return self.edition == "pro"

    @property
    def max_users(self) -> int | None:
        return None if self.pro else FREE_MAX_USERS

    @property
    def scheduled_backups(self) -> bool:
        return self.pro

    def to_json(self) -> dict:
        d = asdict(self)
        d.update(pro=self.pro, max_users=self.max_users, free_max_users=FREE_MAX_USERS,
                 features={"unlimited_users": self.pro, "scheduled_backups": self.scheduled_backups})
        return d


def compute(licence_text: str | None, status_blob: str | None, install_id: str,
            keys: list[str] | None = None, build_date: str = BUILD_DATE) -> Capabilities:
    if not licence_text:
        return Capabilities()
    try:
        lic = parse_licence(licence_text, keys)
    except LicenceError as exc:
        return Capabilities(state="invalid", message=str(exc))
    caps = Capabilities(edition="pro", state="pro", licence_id=lic["lid"], licensee=lic.get("to"),
                        updates_until=lic.get("upd"), max_activations=lic.get("max"))
    status = parse_status(status_blob, lic["lid"], install_id, keys) if status_blob else None
    if status:
        caps.checked_at = status.get("at")
        caps.activated = status["st"] == "active"
        if status["st"] == "revoked":
            caps.edition, caps.state = "free", "revoked"
            caps.message = ("This licence was cancelled (for example after a refund). Pro features are read-only; "
                            "your files, accounts and Free features keep working.")
        elif status["st"] == "limit":
            caps.edition, caps.state = "free", "limit"
            caps.message = (f"This licence is already active on {lic.get('max', 3)} PCs. Remove it from a PC you no "
                            "longer use, then press Check again.")
    if caps.pro and caps.updates_until and build_date > caps.updates_until:
        caps.edition, caps.state = "free", "updates_ended"
        caps.message = (f"Your licence covers versions released until {caps.updates_until}, and this version is newer. "
                        "Pro features are read-only. Reinstall an earlier version or renew your updates.")
    return caps
