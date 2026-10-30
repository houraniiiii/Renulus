"""Explicit Windows credential entry. Never called at import/startup/metadata.

The native password field hands the Go key directly to Python. No clipboard,
Node/JSON handoff, Credential Manager persistence, subprocess or log is used.
Microsoft CredUI's generic prompt cannot use the secure-desktop flag; this is
the native generic credential dialog, not Windows account authentication.
API/flags: https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-creduipromptforwindowscredentialsw
"""
from __future__ import annotations


def read_go_secret() -> str:
    import sys
    if sys.platform != "win32":
        raise RuntimeError("credential_dialog_unavailable")
    import ctypes
    from ctypes import wintypes as w

    class Info(ctypes.Structure):
        _fields_ = [("cbSize", w.DWORD), ("hwndParent", w.HWND),
            ("pszMessageText", w.LPCWSTR), ("pszCaptionText", w.LPCWSTR), ("hbmBanner", w.HBITMAP)]

    ui = ctypes.WinDLL("credui", use_last_error=True)
    ole = ctypes.WinDLL("ole32", use_last_error=True)
    prompt = ui.CredUIPromptForWindowsCredentialsW
    prompt.argtypes = [ctypes.POINTER(Info), w.DWORD, ctypes.POINTER(w.ULONG),
        w.LPCVOID, w.ULONG, ctypes.POINTER(w.LPVOID), ctypes.POINTER(w.ULONG),
        ctypes.POINTER(w.BOOL), w.DWORD]
    prompt.restype = w.DWORD
    unpack = ui.CredUnPackAuthenticationBufferW
    unpack.argtypes = [w.DWORD, w.LPVOID, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD),
        w.LPWSTR, ctypes.POINTER(w.DWORD), w.LPWSTR, ctypes.POINTER(w.DWORD)]
    unpack.restype = w.BOOL
    ole.CoTaskMemFree.argtypes = [w.LPVOID]
    ole.CoTaskMemFree.restype = None
    info = Info(ctypes.sizeof(Info), None,
        "Connect OpenCode Go to Renulus. Enter any user name and paste your Go subscription key in Password.",
        "Renulus — Connect OpenCode Go", None)
    package, size, blob = w.ULONG(), w.ULONG(), w.LPVOID()
    buffers = []
    try:
        # CREDUIWIN_GENERIC only: omit CHECKBOX, hence no native persistence.
        result = prompt(ctypes.byref(info), 0, ctypes.byref(package), None, 0,
            ctypes.byref(blob), ctypes.byref(size), None, 0x1)
        if result != 0:
            raise RuntimeError("credential_dialog_cancelled" if result == 1223 else "credential_dialog_failed")
        lengths = [w.DWORD(), w.DWORD(), w.DWORD()]
        unpack(0, blob, size, None, ctypes.byref(lengths[0]), None,
            ctypes.byref(lengths[1]), None, ctypes.byref(lengths[2]))
        if ctypes.get_last_error() != 122 or any(n.value > 8193 for n in lengths):
            raise RuntimeError("credential_dialog_failed")
        buffers = [ctypes.create_unicode_buffer(max(1, n.value)) for n in lengths]
        if not unpack(0, blob, size, buffers[0], ctypes.byref(lengths[0]), buffers[1],
                ctypes.byref(lengths[1]), buffers[2], ctypes.byref(lengths[2])):
            raise RuntimeError("credential_dialog_failed")
        secret = buffers[2].value
        if not secret or len(secret) > 8192:
            raise RuntimeError("credential_dialog_failed")
        return secret
    finally:
        for buffer in buffers:
            ctypes.memset(ctypes.addressof(buffer), 0, ctypes.sizeof(buffer))
        if blob:
            ctypes.memset(blob, 0, size.value)
            ole.CoTaskMemFree(blob)
