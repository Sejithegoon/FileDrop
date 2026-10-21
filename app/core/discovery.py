"""Announces the LAN server on the Wi-Fi (mDNS / DNS-SD) so the WiFiDrop phone app finds it without typing.

Uses Windows' own DNS-SD service (dnsapi.dll, Windows 10 1809 and later), which already owns port 5353,
so there's no extra listener and no firewall prompt. The announcement carries no secrets: the app still
checks the PC's key against the QR code (or the code shown in the admin window) before trusting it.

Service type: _wifidrop._tcp. TXT: api (LAN API version), id (public server id), https (1/0),
ip and port (where the server listens; the PC's name may also resolve to other addresses).
"""

from __future__ import annotations

import ctypes
import logging
import socket
import sys
import threading
from ctypes import wintypes

log = logging.getLogger(__name__)

SERVICE_TYPE = "_wifidrop._tcp.local"
_DNS_QUERY_REQUEST_VERSION1 = 1
_DNS_REQUEST_PENDING = 9506


class _ServiceInstance(ctypes.Structure):
    _fields_ = [("pszInstanceName", wintypes.LPWSTR), ("pszHostName", wintypes.LPWSTR),
                ("ip4Address", ctypes.POINTER(ctypes.c_uint32)), ("ip6Address", ctypes.c_void_p),
                ("wPort", wintypes.WORD), ("wPriority", wintypes.WORD), ("wWeight", wintypes.WORD),
                ("dwPropertyCount", wintypes.DWORD), ("keys", ctypes.POINTER(wintypes.LPWSTR)),
                ("values", ctypes.POINTER(wintypes.LPWSTR)), ("dwInterfaceIndex", wintypes.DWORD)]


_Callback = ctypes.WINFUNCTYPE(None, wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(_ServiceInstance))


class _RegisterRequest(ctypes.Structure):
    _fields_ = [("Version", wintypes.ULONG), ("InterfaceIndex", wintypes.ULONG),
                ("pServiceInstance", ctypes.POINTER(_ServiceInstance)), ("pRegisterCompletionCallback", _Callback),
                ("pQueryContext", ctypes.c_void_p), ("hCredentials", wintypes.HANDLE), ("unicastEnabled", wintypes.BOOL)]


def _dnsapi():
    if sys.platform != "win32":
        return None
    try:
        api = ctypes.WinDLL("dnsapi.dll")
        api.DnsServiceConstructInstance.restype = ctypes.POINTER(_ServiceInstance)
        api.DnsServiceConstructInstance.argtypes = [
            wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p, wintypes.WORD,
            wintypes.WORD, wintypes.WORD, wintypes.DWORD, ctypes.POINTER(wintypes.LPCWSTR),
            ctypes.POINTER(wintypes.LPCWSTR)]
        api.DnsServiceRegister.restype = wintypes.DWORD
        api.DnsServiceRegister.argtypes = [ctypes.POINTER(_RegisterRequest), ctypes.c_void_p]
        api.DnsServiceDeRegister.restype = wintypes.DWORD
        api.DnsServiceDeRegister.argtypes = [ctypes.POINTER(_RegisterRequest), ctypes.c_void_p]
        api.DnsServiceFreeInstance.restype = None
        api.DnsServiceFreeInstance.argtypes = [ctypes.POINTER(_ServiceInstance)]
        return api
    except (OSError, AttributeError):  # older Windows: no announcement, the QR code still works
        return None


def instance_name(pc_name: str) -> str:
    # DNS labels are at most 63 bytes.
    label = f"WiFiDrop on {pc_name}".replace(".", "-").encode("utf-8")[:63].decode("utf-8", "ignore")
    return f"{label}.{SERVICE_TYPE}"


class Announcer:
    """One announcement at a time; start() replaces the previous one. Never raises: discovery is a convenience."""

    def __init__(self):
        self._api = _dnsapi()
        self._lock = threading.Lock()
        self._request: _RegisterRequest | None = None
        self._keep: list = []  # ctypes objects Windows points at while the announcement is up
        self._ours: set[int] = set()  # addresses of instances we built (freed by us, not the callback)
        self.name: str | None = None

    @property
    def available(self) -> bool:
        return self._api is not None

    def _done(self, status, _context, instance) -> None:
        if status:
            log.info("Network announcement finished with status %s", status)
        # Windows hands back its own copy to free; never free the one our request still points at.
        address = ctypes.addressof(instance.contents) if instance else 0
        if address and self._api and address not in self._ours:
            self._api.DnsServiceFreeInstance(instance)

    def start(self, ip: str, port: int, pc_name: str, txt: dict[str, str]) -> bool:
        self.stop()
        if not self._api:
            return False
        with self._lock:
            try:
                name = instance_name(pc_name)
                host = f"{socket.gethostname()}.local"
                ip4 = ctypes.c_uint32(int.from_bytes(socket.inet_aton(ip), "little"))  # network byte order in memory
                keys = (wintypes.LPCWSTR * len(txt))(*txt.keys())
                values = (wintypes.LPCWSTR * len(txt))(*txt.values())
                instance = self._api.DnsServiceConstructInstance(name, host, ctypes.byref(ip4), None, port, 0, 0,
                                                                 len(txt), keys, values)
                if not instance:
                    return False
                callback = _Callback(self._done)
                request = _RegisterRequest(Version=_DNS_QUERY_REQUEST_VERSION1, InterfaceIndex=0,
                                           pServiceInstance=instance, pRegisterCompletionCallback=callback)
                self._ours.add(ctypes.addressof(instance.contents))  # before Windows can call back
                status = self._api.DnsServiceRegister(ctypes.byref(request), None)
                if status != _DNS_REQUEST_PENDING:
                    self._ours.discard(ctypes.addressof(instance.contents))
                    self._api.DnsServiceFreeInstance(instance)
                    log.info("Could not announce WiFiDrop on the network (status %s)", status)
                    return False
                self._request, self._keep, self.name = request, [instance, callback, ip4, keys, values], name
                log.info("Announcing %s at %s:%s", name, ip, port)
                return True
            except Exception as exc:  # pragma: no cover - depends on the Windows build
                log.info("Could not announce WiFiDrop on the network: %s", exc)
                return False

    def stop(self) -> None:
        with self._lock:
            if not self._request or not self._api:
                return
            try:
                self._api.DnsServiceDeRegister(ctypes.byref(self._request), None)
            except Exception as exc:  # pragma: no cover
                log.info("Could not withdraw the network announcement: %s", exc)
            # Windows finishes withdrawing in the background and calls back; free our copy after that.
            old = self._keep
            timer = threading.Timer(10, self._release, args=(old,))
            timer.daemon = True  # never holds up quitting
            timer.start()
            self._request, self._keep, self.name = None, [], None

    def _release(self, kept: list) -> None:
        instance = kept[0]
        self._api.DnsServiceFreeInstance(instance)
        self._ours.discard(ctypes.addressof(instance.contents))
        kept.clear()
