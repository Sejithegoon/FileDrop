"""Self-signed HTTPS certificate for the LAN web server.

The private key is created once and kept. The certificate is reused until it
nears expiry or the PC's LAN address changes, so phones only show the
"not private" warning again when they really have to.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import logging
import socket
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

log = logging.getLogger(__name__)

VALID_DAYS = 397
RENEW_BEFORE_DAYS = 30


@dataclass
class CertInfo:
    cert_path: Path
    key_path: Path
    fingerprint: str  # SHA-256, "AB:CD:..."


def _load_or_create_key(path: Path) -> ec.EllipticCurvePrivateKey:
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    key = ec.generate_private_key(ec.SECP256R1())
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
    return key


def _fingerprint(cert: x509.Certificate) -> str:
    return cert.fingerprint(hashes.SHA256()).hex(":").upper()


def _still_good(cert: x509.Certificate, ip: str) -> bool:
    if cert.not_valid_after_utc - dt.timedelta(days=RENEW_BEFORE_DAYS) < dt.datetime.now(dt.timezone.utc):
        return False
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return False
    return ipaddress.ip_address(ip) in san.get_values_for_type(x509.IPAddress)


def ensure_certificate(directory: Path, ip: str) -> CertInfo:
    directory.mkdir(parents=True, exist_ok=True)
    key_path, cert_path = directory / "key.pem", directory / "cert.pem"
    key = _load_or_create_key(key_path)
    if cert_path.exists():
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        if _still_good(cert, ip):
            return CertInfo(cert_path, key_path, _fingerprint(cert))

    host = socket.gethostname()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"FileDrop on {host}"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "FileDrop")])
    now = dt.datetime.now(dt.timezone.utc)
    alt = [x509.IPAddress(ipaddress.ip_address(ip)), x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
           x509.DNSName("localhost")]
    if host and host.replace("-", "").isalnum():
        alt.append(x509.DNSName(host))
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=VALID_DAYS))
            .add_extension(x509.SubjectAlternativeName(alt), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    log.info("Created HTTPS certificate for %s (SHA-256 %s)", ip, _fingerprint(cert))
    return CertInfo(cert_path, key_path, _fingerprint(cert))
