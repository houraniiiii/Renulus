"""Windows user-bound, profile-bound DPAPI records; no plaintext credential file."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import secrets
from typing import Protocol
from uuid import uuid4

from renulus.contracts import ApiError


class Protector(Protocol):
    def protect(self, data: bytes, entropy: bytes) -> bytes: ...
    def unprotect(self, data: bytes, entropy: bytes) -> bytes: ...


class _Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


class WindowsDPAPI:
    def _apply(self, data: bytes, entropy: bytes, *, decrypt: bool) -> bytes:
        if os.name != "nt":
            raise ApiError("protected_storage_unavailable", "Renulus connection storage requires Windows.", 503)
        crypt = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        buffer = ctypes.create_string_buffer(data)
        salt = ctypes.create_string_buffer(entropy)
        source = _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        extra = _Blob(len(entropy), ctypes.cast(salt, ctypes.POINTER(ctypes.c_ubyte)))
        output = _Blob()
        function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
        function.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p,
                            ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                            wintypes.DWORD, ctypes.POINTER(_Blob)]
        function.restype = wintypes.BOOL
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        # CRYPTPROTECT_UI_FORBIDDEN; no machine-wide flag.
        if not function(ctypes.byref(source), None, ctypes.byref(extra), None,
                        None, 1, ctypes.byref(output)):
            raise ApiError("protected_storage_failed", "Windows could not access this profile's protected connection. Reconnect it.", 503, True)
        try:
            return ctypes.string_at(output.data, output.size)
        finally:
            kernel.LocalFree(output.data)

    def protect(self, data: bytes, entropy: bytes) -> bytes:
        return self._apply(data, entropy, decrypt=False)

    def unprotect(self, data: bytes, entropy: bytes) -> bytes:
        return self._apply(data, entropy, decrypt=True)


class ConnectionStore:
    def __init__(self, profile: Path, state: Path, protector: Protector | None = None):
        if not profile.is_absolute() or not state.resolve().is_relative_to(profile.resolve()):
            raise ApiError("invalid_profile", "An explicit isolated runtime profile is required.")
        self.profile = profile.resolve()
        self.path = state / "runtime" / "connections.dpapi"
        self.entropy = hashlib.sha256(("Renulus.connections.v1:" + str(self.profile)).encode()).digest()
        self.protector = protector or WindowsDPAPI()

    def load(self) -> dict:
        if not self.path.exists():
            return {"version": 1, "host_id": uuid4().urn, "selected_provider": None, "connections": {}}
        try:
            payload = json.loads(self.protector.unprotect(self.path.read_bytes(), self.entropy))
            if payload.get("version") != 1 or not isinstance(payload.get("connections"), dict):
                raise ValueError("schema")
            return payload
        except ApiError:
            raise
        except Exception:
            raise ApiError("connection_record_invalid", "Reconnect this profile's subscription.", 503, True) from None

    def save(self, payload: dict) -> None:
        ciphertext = self.protector.protect(json.dumps(payload, separators=(",", ":")).encode(), self.entropy)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.parent.resolve().is_relative_to(self.profile):
            raise ApiError("invalid_profile", "Connection storage leaves the app profile.")
        temporary = self.path.with_name("connections." + secrets.token_hex(8) + ".tmp")
        try:
            with temporary.open("xb") as output:
                output.write(ciphertext)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
