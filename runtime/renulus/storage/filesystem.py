"""Windows ownership primitives, independent of the development ledger.

No path resolution through reparse points; identities are volume + FILE_ID_128.
Handles, not hashes/read-only flags, protect aliases. Guards are cooperative,
process-local resources: keep them until native work actually joins. They are
not profile job assignment and cannot protect against an administrator.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes as c
from ctypes import wintypes as w
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import sys


def _native_audit(operation, path, info=None, *, retained=False):
    """Allow audit callbacks to refuse cooperating native I/O BEFORE its call.

    The exact lexical target and retained FILE_ID_128 identity are observations,
    never a grant of root ownership, all-stream authority or arbitrary ctypes.
    """
    sys.audit("renulus.storage.native", operation, str(exact_path(path)),
              info.identity if info is not None else None, retained)


def _handle_path(handle):
    """Bind relative native creation to its retained parent's exact DOS target."""
    buffer = c.create_unicode_buffer(32768)
    length = k.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
    if not length or length >= len(buffer) or not buffer.value.startswith("\\\\?\\"):
        raise FilesystemError("path_denied", "Retained parent has no exact DOS target")
    return exact_path(buffer.value[4:])


class FilesystemError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class FileIdentity:
    volume: str
    file_id: str


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    creation_filetime: int
    executable: str


@dataclass(frozen=True)
class FileInfo:
    identity: FileIdentity
    logical_bytes: int
    allocated_bytes: int
    links: int
    directory: bool


@dataclass(frozen=True)
class DataInfo:
    info: FileInfo
    streams: tuple[tuple[str, int, int], ...]
    logical_bytes: int
    allocated_bytes: int


@dataclass(frozen=True)
class Measurement:
    logical_bytes: int
    allocated_bytes: int
    reclaimable_bytes: int
    by_volume: dict[str, int]
    identities: tuple[FileIdentity, ...]


if os.name == "nt":
    k = c.WinDLL("kernel32", use_last_error=True)
    a = c.WinDLL("advapi32", use_last_error=True)
    n = c.WinDLL("ntdll")

    class UNICODE_STRING(c.Structure):
        _fields_ = [("Length", w.USHORT), ("MaximumLength", w.USHORT), ("Buffer", w.LPWSTR)]

    class OBJECT_ATTRIBUTES(c.Structure):
        _fields_ = [("Length", w.ULONG), ("RootDirectory", w.HANDLE),
                    ("ObjectName", c.POINTER(UNICODE_STRING)), ("Attributes", w.ULONG),
                    ("SecurityDescriptor", c.c_void_p), ("SecurityQualityOfService", c.c_void_p)]

    class IO_STATUS_BLOCK(c.Structure):
        _fields_ = [("Status", c.c_void_p), ("Information", c.c_size_t)]

    class ID_INFO(c.Structure):
        _fields_ = [("VolumeSerialNumber", c.c_ulonglong), ("FileId", c.c_ubyte * 16)]

    class STANDARD_INFO(c.Structure):
        _fields_ = [("AllocationSize", c.c_longlong), ("EndOfFile", c.c_longlong),
                    ("NumberOfLinks", w.DWORD), ("DeletePending", w.BOOLEAN),
                    ("Directory", w.BOOLEAN)]

    class ATTRIBUTE_INFO(c.Structure):
        _fields_ = [("FileAttributes", w.DWORD), ("ReparseTag", w.DWORD)]

    class COMPRESSION_INFO(c.Structure):
        _fields_ = [("CompressedFileSize", c.c_longlong), ("CompressionFormat", w.WORD),
                    ("CompressionUnitShift", c.c_ubyte), ("ChunkShift", c.c_ubyte),
                    ("ClusterShift", c.c_ubyte), ("Reserved", c.c_ubyte * 3)]

    class TRUSTEE(c.Structure):
        pass
    TRUSTEE._fields_ = [("pMultipleTrustee", c.POINTER(TRUSTEE)),
                       ("MultipleTrusteeOperation", c.c_int), ("TrusteeForm", c.c_int),
                       ("TrusteeType", c.c_int), ("ptstrName", c.c_void_p)]

    class EXPLICIT_ACCESS(c.Structure):
        _fields_ = [("grfAccessPermissions", w.DWORD), ("grfAccessMode", c.c_int),
                    ("grfInheritance", w.DWORD), ("Trustee", TRUSTEE)]

    def _signature(lib, name, restype, *args):
        function = getattr(lib, name)
        function.restype, function.argtypes = restype, args
        return function

    _signature(k, "CreateFileW", w.HANDLE, w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p,
               w.DWORD, w.DWORD, w.HANDLE)
    _signature(k, "CloseHandle", w.BOOL, w.HANDLE)
    _signature(k, "WriteFile", w.BOOL, w.HANDLE, c.c_void_p, w.DWORD,
               c.POINTER(w.DWORD), c.c_void_p)
    _signature(k, "FlushFileBuffers", w.BOOL, w.HANDLE)
    _signature(k, "ReadFile", w.BOOL, w.HANDLE, c.c_void_p, w.DWORD,
               c.POINTER(w.DWORD), c.c_void_p)
    _signature(k, "SetFilePointerEx", w.BOOL, w.HANDLE, c.c_longlong,
               c.POINTER(c.c_longlong), w.DWORD)
    _signature(k, "SetEndOfFile", w.BOOL, w.HANDLE)
    _signature(k, "SetFileInformationByHandle", w.BOOL, w.HANDLE, c.c_int,
               c.c_void_p, w.DWORD)
    _signature(n, "NtCreateFile", w.LONG, c.POINTER(w.HANDLE), w.DWORD,
               c.POINTER(OBJECT_ATTRIBUTES), c.POINTER(IO_STATUS_BLOCK),
               c.c_void_p, w.ULONG, w.ULONG, w.ULONG, w.ULONG, c.c_void_p, w.ULONG)
    _signature(n, "RtlNtStatusToDosError", w.ULONG, w.LONG)
    _signature(k, "CreateSemaphoreW", w.HANDLE, c.c_void_p, w.LONG, w.LONG, w.LPCWSTR)
    _signature(k, "WaitForSingleObject", w.DWORD, w.HANDLE, w.DWORD)
    _signature(k, "ReleaseSemaphore", w.BOOL, w.HANDLE, w.LONG, c.c_void_p)
    _signature(k, "GetFileInformationByHandleEx", w.BOOL, w.HANDLE, c.c_int,
               c.c_void_p, w.DWORD)
    _signature(k, "GetFinalPathNameByHandleW", w.DWORD, w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD)
    _signature(k, "GetDiskFreeSpaceExW", w.BOOL, w.LPCWSTR, c.POINTER(c.c_ulonglong),
               c.POINTER(c.c_ulonglong), c.POINTER(c.c_ulonglong))
    _signature(k, "GetDiskFreeSpaceW", w.BOOL, w.LPCWSTR, c.POINTER(w.DWORD),
               c.POINTER(w.DWORD), c.POINTER(w.DWORD), c.POINTER(w.DWORD))
    _signature(k, "OpenProcess", w.HANDLE, w.DWORD, w.BOOL, w.DWORD)
    _signature(k, "GetProcessTimes", w.BOOL, w.HANDLE, c.POINTER(w.FILETIME),
               c.POINTER(w.FILETIME), c.POINTER(w.FILETIME), c.POINTER(w.FILETIME))
    _signature(k, "QueryFullProcessImageNameW", w.BOOL, w.HANDLE, w.DWORD,
               w.LPWSTR, c.POINTER(w.DWORD))
    _signature(k, "LocalFree", c.c_void_p, c.c_void_p)
    _signature(a, "GetSecurityInfo", w.DWORD, w.HANDLE, c.c_int, w.DWORD,
               c.c_void_p, c.c_void_p, c.POINTER(c.c_void_p), c.c_void_p,
               c.POINTER(c.c_void_p))
    _signature(a, "SetSecurityInfo", w.DWORD, w.HANDLE, c.c_int, w.DWORD,
               c.c_void_p, c.c_void_p, c.c_void_p, c.c_void_p)
    _signature(a, "SetEntriesInAclW", w.DWORD, w.ULONG, c.POINTER(EXPLICIT_ACCESS),
               c.c_void_p, c.POINTER(c.c_void_p))
    _signature(a, "CreateWellKnownSid", w.BOOL, c.c_int, c.c_void_p, c.c_void_p,
               c.POINTER(w.DWORD))
    _signature(a, "GetSecurityDescriptorControl", w.BOOL, c.c_void_p,
               c.POINTER(w.WORD), c.POINTER(w.DWORD))


def _windows():
    if os.name != "nt":
        raise FilesystemError("platform_unsupported", "Windows handle enforcement is required")


def exact_path(path) -> Path:
    """Lexical local absolute path only; reject ADS, device paths, aliases and traversal."""
    _windows()
    text = os.fspath(path)
    if not isinstance(text, str) or not text or len(text) > 32000 or "\0" in text:
        raise FilesystemError("path_denied", "Invalid bounded path")
    text = text.replace("/", "\\")
    if text.startswith("\\") or len(text) < 3 or text[1:3] != ":\\" or not text[0].isalpha():
        raise FilesystemError("path_denied", "Use an absolute local drive path, not a device/UNC alias")
    parts = text[3:].split("\\") if text[3:] else []
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    if any(not p or p in {".", ".."} or p.endswith((".", " ")) or
           any(ch in p for ch in ':*?<>|') or any(ord(ch) < 32 for ch in p) or
           p.split(".")[0].upper() in reserved for p in parts):
        raise FilesystemError("path_denied", "Noncanonical path component")
    return Path(text)


def _extended(path):
    return "\\\\?\\" + str(path)


def _open(path, *, share=3, access=0x80000000):
    # File-specific, standard, system-security/maximum-allowed and generic rights.
    # Validate before DWORD coercion: bool, negative, oversized and unknown refuse.
    known = 0x1FF | 0x1F0000 | 0x03000000 | 0xF0000000
    if type(access) is not int or not 0 <= access <= 0xFFFFFFFF or access & ~known:
        raise FilesystemError("access_denied", "Unknown or out-of-range native file access mask")
    # WRITE_DATA/APPEND_DATA/WRITE_EA/DELETE_CHILD/WRITE_ATTRIBUTES, DELETE,
    # WRITE_DAC/WRITE_OWNER, GENERIC_WRITE/ALL, MAXIMUM_ALLOWED and SYSTEM_SECURITY.
    mutation = 0x2 | 0x4 | 0x10 | 0x40 | 0x100 | 0x10000 | 0x40000 | 0x80000 | 0x40000000 | 0x10000000 | 0x03000000
    # OPEN_REPARSE_POINT + BACKUP_SEMANTICS, OPEN_EXISTING. No delete sharing.
    _native_audit("open-write" if access & mutation else "read", path)
    handle = k.CreateFileW(_extended(path), access, share, None, 3, 0x02200000, None)
    if handle == c.c_void_p(-1).value:
        raise c.WinError(c.get_last_error())
    return handle


def _get(handle, kind, structure):
    info = structure()
    if not k.GetFileInformationByHandleEx(handle, kind, c.byref(info), c.sizeof(info)):
        raise c.WinError(c.get_last_error())
    return info


def _info(handle):
    attrs = _get(handle, 9, ATTRIBUTE_INFO)
    if attrs.FileAttributes & 0x400:
        raise FilesystemError("reparse_denied", "Reparse points/junctions are not owned paths")
    standard, identifier = _get(handle, 1, STANDARD_INFO), _get(handle, 18, ID_INFO)
    allocated = 0
    if not standard.Directory:
        allocated = standard.AllocationSize
        # Sparse/compressed physical bytes, queried through the same retained handle.
        if attrs.FileAttributes & (0x200 | 0x800):
            allocated = _get(handle, 8, COMPRESSION_INFO).CompressedFileSize
    buffer = c.create_unicode_buffer(32768)
    length = k.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 1)  # VOLUME_NAME_GUID
    if not length or length >= len(buffer):
        raise c.WinError(c.get_last_error())
    final = buffer.value
    if not final.casefold().startswith(chr(92) * 2 + "?" + chr(92) + "volume{") or "}" not in final:
        raise FilesystemError("volume_unknown", "An exact local volume GUID is required")
    volume = final[:final.index("}") + 1].casefold()
    identity = FileIdentity(f"{volume}:{identifier.VolumeSerialNumber:016x}", bytes(identifier.FileId).hex())
    return FileInfo(identity, 0 if standard.Directory else standard.EndOfFile,
                    allocated, standard.NumberOfLinks, bool(standard.Directory))


def _chain(path):
    return [*reversed(path.parents), path]


@contextmanager
def _guarded_roots(paths, *, access):
    handles = []
    seen = set()
    try:
        for path in paths:
            for component in _chain(exact_path(path)):
                key = str(component).casefold()
                if key in seen:
                    continue
                seen.add(key)
                handle = _open(component, access=access)
                handles.append(handle)
                _info(handle)
        yield
    finally:
        for handle in reversed(handles):
            k.CloseHandle(handle)


def guarded_roots(paths):
    """Retain full read/no-delete handles for each component; refuse reparses."""
    return _guarded_roots(paths, access=0x80000000)


def file_info(path) -> FileInfo:
    path = exact_path(path)
    with guarded_roots([path.parent]):
        handle = _open(path)
        try:
            return _info(handle)
        finally:
            k.CloseHandle(handle)


def path_exists(path) -> bool:
    """Lexical existence includes broken reparses; never silently adopts their target."""
    try:
        os.lstat(_extended(exact_path(path)))
        return True
    except FileNotFoundError:
        return False


def directory_names(path):
    path = exact_path(path)
    with guarded_roots([path]):
        return os.listdir(_extended(path))


def canonical_path(path, *, allow_missing=False) -> Path:
    """Normalize long/8.3 spellings through no-follow handles, never Path.resolve."""
    path = exact_path(path)
    with guarded_roots([path.parent]):
        missing = allow_missing and not path_exists(path)
        handle = _open(path.parent if missing else path)
        try:
            _info(handle)
            buffer = c.create_unicode_buffer(32768)
            length = k.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
            if not length or length >= len(buffer):
                raise c.WinError(c.get_last_error())
            final = buffer.value
            if not final.startswith("\\\\?\\"):
                raise FilesystemError("path_denied", "An exact local DOS path is required")
            canonical = exact_path(final[4:])
            return canonical / path.name if missing else canonical
        finally:
            k.CloseHandle(handle)


def path_identities(path) -> tuple[FileIdentity, ...]:
    """Existing no-reparse ancestor/object identities, retained for this lookup."""
    path = exact_path(path)
    with guarded_roots([path]):
        return tuple(file_info(component).identity for component in _chain(path))


def _create_directory(parent_handle, name):
    # NtCreateFile FILE_CREATE returns the newly created directory's handle in
    # the same native operation. CreateDirectoryW/mkdir + reopen cannot do this.
    _native_audit("mkdir", _handle_path(parent_handle) / name, _info(parent_handle), retained=True)
    buffer = c.create_unicode_buffer(name)
    size = len(name.encode("utf-16-le"))
    text = UNICODE_STRING(size, size + 2, c.cast(buffer, w.LPWSTR))
    attrs = OBJECT_ATTRIBUTES(c.sizeof(OBJECT_ATTRIBUTES), parent_handle,
                              c.pointer(text), 0x40, None, None)  # OBJ_CASE_INSENSITIVE
    handle, status = w.HANDLE(), IO_STATUS_BLOCK()
    result = n.NtCreateFile(c.byref(handle), 0x100081, c.byref(attrs), c.byref(status),
                            None, 0x10, 3, 2, 0x200021, None, 0)
    # READ_DATA/LIST_DIRECTORY + READ_ATTRIBUTES + SYNCHRONIZE; share read/write
    # only; FILE_CREATE; DIRECTORY + SYNCHRONOUS_IO_NONALERT + OPEN_REPARSE_POINT.
    if result < 0:
        raise c.WinError(n.RtlNtStatusToDosError(result))
    return handle.value


@contextmanager
def created_directory(path):
    """Atomically create no-replace and hold that identity until context exit."""
    path = exact_path(path)
    with guarded_roots([path.parent]):
        parent = _open(path.parent)
        handle = None
        try:
            if not _info(parent).directory:
                raise FilesystemError("path_denied", "Directory parent required")
            handle = _create_directory(parent, path.name)
            info = _info(handle)
            if not info.directory:
                raise FilesystemError("identity_changed", "Native directory creation returned a non-directory")
            yield info
        finally:
            if handle is not None:
                k.CloseHandle(handle)
            k.CloseHandle(parent)


def mkdir_exact(path) -> FileInfo:
    """Single atomic no-replace creation; use created_directory to retain ownership."""
    with created_directory(path) as info:
        return info


def _create_file(parent_handle, name, *, deletable=False):
    """FILE_CREATE claims a regular file with writer/delete exclusion atomically."""
    _native_audit("create", _handle_path(parent_handle) / name, _info(parent_handle), retained=True)
    buffer = c.create_unicode_buffer(name)
    size = len(name.encode("utf-16-le"))
    text = UNICODE_STRING(size, size + 2, c.cast(buffer, w.LPWSTR))
    attrs = OBJECT_ATTRIBUTES(c.sizeof(OBJECT_ATTRIBUTES), parent_handle,
                              c.pointer(text), 0x40, None, None)
    handle, status = w.HANDLE(), IO_STATUS_BLOCK()
    # The legacy argument is compatible, not all-stream destructive authority.
    access = 0xC0100000
    result = n.NtCreateFile(c.byref(handle), access, c.byref(attrs), c.byref(status),
                            None, 0x80, 1, 2, 0x200060, None, 0)
    # GENERIC_READ/WRITE + SYNCHRONIZE; share READ only; FILE_CREATE;
    # Writer/delete-exclusive; READ sharing permits a full no-delete publication
    # pin before releasing I/O. Zero-access handles do NOT enforce share denial.
    # NON_DIRECTORY + SYNCHRONOUS_IO_NONALERT + OPEN_REPARSE_POINT.
    if result < 0:
        raise c.WinError(n.RtlNtStatusToDosError(result))
    return handle.value


def _seek_start(handle):
    if not k.SetFilePointerEx(handle, 0, None, 0):
        raise c.WinError(c.get_last_error())


class OpenedFile:
    """Retained exact single-link file; no write/delete sharing, no path I/O reopen.

    publish is an in-place durable write, NOT an atomic commit. Its caller must
    flush a protected preimage first and keep it on any error/crash.
    """
    def __init__(self, handle, info, *, writable=False):
        self._handle, self.info, self.writable = handle, info, writable

    def _audit(self, operation):
        # Contexts retain their exact lexical target, including hardlink spelling.
        # Direct construction remains compatible: metadata lookup only at I/O.
        target = getattr(self, "_audit_target", None)
        if target is None:
            target = _handle_path(self._handle)
        _native_audit(operation, target, self.info, retained=True)

    def check(self):
        if self._handle is None:
            raise FilesystemError("publication_denied", "Native file context is closed")
        info = _info(self._handle)
        if info.directory or info.identity != self.info.identity or info.links != 1:
            raise FilesystemError("identity_changed", "Retained file identity/alias changed")
        return info

    def data_info(self):
        """Retained all-stream observation, not cross-stream mutation authority."""
        self.check()
        return _data_info(self._handle)

    def check_streams(self):
        from .streams import refuse_named_streams
        self.check()
        return refuse_named_streams(self._handle)

    def read(self, *, limit=32 * 1024 ** 2):
        self.check_streams()
        size = self.check().logical_bytes
        if type(limit) is not int or not 0 < limit <= 32 * 1024 ** 2 or not 0 < size <= limit:
            raise FilesystemError("publication_denied", "Retained file exceeds bounded nonempty format")
        self._audit("seek")
        _seek_start(self._handle)
        buffer, count = c.create_string_buffer(size), w.DWORD()
        self._audit("read")
        if not k.ReadFile(self._handle, buffer, size, c.byref(count), None):
            raise c.WinError(c.get_last_error())
        if count.value != size:
            raise FilesystemError("publication_incomplete", "Incomplete retained read; preserve for recovery")
        self.check_streams()
        return buffer.raw

    def truncate(self, size):
        """Invalidate a retained default-stream trailer, then synchronously flush."""
        if not self.writable or type(size) is not int or not 0 < size <= self.check().logical_bytes:
            raise FilesystemError("publication_denied", "Bounded retained default-stream truncation required")
        self.check_streams()
        self._audit("seek")
        if not k.SetFilePointerEx(self._handle, size, None, 0):
            raise c.WinError(c.get_last_error())
        self._audit("truncate")
        if not k.SetEndOfFile(self._handle):
            raise c.WinError(c.get_last_error())
        self._audit("flush")
        if not k.FlushFileBuffers(self._handle):
            raise c.WinError(c.get_last_error())
        self.check_streams()
        if self.check().logical_bytes != size:
            raise FilesystemError("publication_incomplete", "Trailer invalidation is incomplete; preserve for recovery")

    def append(self, data, *, expected_size):
        """Append only to the exact retained default-stream length, then flush."""
        if not self.writable or not isinstance(data, bytes) or not 0 < len(data) <= 4096 or \
                type(expected_size) is not int or not 0 < expected_size <= 32 * 1024 ** 2 - len(data):
            raise FilesystemError("publication_denied", "Bounded retained default-stream append required")
        self.check_streams()
        if self.check().logical_bytes != expected_size:
            raise FilesystemError("publication_incomplete", "Prepared length changed; preserve for recovery")
        self._audit("seek")
        if not k.SetFilePointerEx(self._handle, expected_size, None, 0):
            raise c.WinError(c.get_last_error())
        buffer, written = c.create_string_buffer(data), w.DWORD()
        self._audit("write")
        if not k.WriteFile(self._handle, buffer, len(data), c.byref(written), None):
            raise c.WinError(c.get_last_error())
        if written.value != len(data):
            raise FilesystemError("publication_incomplete", "Incomplete finalized trailer; preserve for recovery")
        self._audit("flush")
        if not k.FlushFileBuffers(self._handle):
            raise c.WinError(c.get_last_error())
        self.check_streams()
        if self.check().logical_bytes != expected_size + len(data):
            raise FilesystemError("publication_incomplete", "Finalized length changed; preserve for recovery")

    def publish(self, data):
        if not self.writable or not isinstance(data, bytes) or not 0 < len(data) <= 32 * 1024 ** 2:
            raise FilesystemError("publication_denied", "Bounded native writer required")
        self.check_streams()
        self._audit("seek")
        _seek_start(self._handle)
        buffer, written = c.create_string_buffer(data), w.DWORD()
        self._audit("write")
        if not k.WriteFile(self._handle, buffer, len(data), c.byref(written), None):
            raise c.WinError(c.get_last_error())
        if written.value != len(data):
            raise FilesystemError("publication_incomplete", "Incomplete native publication; retain preimage for recovery")
        self._audit("truncate")
        if not k.SetEndOfFile(self._handle):
            raise c.WinError(c.get_last_error())
        self._audit("flush")
        if not k.FlushFileBuffers(self._handle):
            raise c.WinError(c.get_last_error())
        self.check_streams()


class OpenedDirectory:
    """Retained recorder-directory identity and all-stream observations only."""
    def __init__(self, handle, info):
        self._handle, self.info = handle, info

    def check(self):
        if self._handle is None:
            raise FilesystemError('publication_denied', 'Native directory context is closed')
        info = _info(self._handle)
        if not info.directory or info.links != 1 or info.identity != self.info.identity:
            raise FilesystemError('identity_changed', 'Retained recorder directory changed')
        return info

    def data_info(self):
        self.check()
        return _data_info(self._handle)

    def check_streams(self):
        from .streams import refuse_named_streams
        self.check()
        return refuse_named_streams(self._handle)


@contextmanager
def opened_directory(path):
    """Pin an exact single-link no-reparse directory, without modifying it."""
    path = exact_path(path)
    with guarded_roots([path.parent]):
        handle = _open(path, access=0x80000000, share=3)
        try:
            info = _info(handle)
            resource = OpenedDirectory(handle, info)
            resource.check()
            try:
                yield resource
            finally:
                resource._handle = None
        finally:
            k.CloseHandle(handle)


@contextmanager
def opened_file(path, *, writable=False):
    """Read/write existing exact bytes through one retained writer/delete exclusion."""
    path = exact_path(path)
    with guarded_roots([path.parent]):
        handle = _open(path, share=1, access=0xC0000000 if writable else 0x80000000)
        try:
            info = _info(handle)
            if info.directory or info.links != 1:
                raise FilesystemError("identity_changed", "Expected an existing single-link regular file")
            resource = OpenedFile(handle, info, writable=writable)
            resource._audit_target = path
            try:
                yield resource
            finally:
                resource._handle = None
        finally:
            k.CloseHandle(handle)


class CreatedFile(OpenedFile):
    """No-replace native claim kept writer/delete exclusive until context exit.

    Exact identity is not authority to delete every stream. The legacy remove
    API always holds; failures and process death preserve newly claimed bytes.
    """
    def __init__(self, handle, info, *, deletable=False):
        super().__init__(handle, info, writable=True)
        self._published, self._deletable = False, deletable

    def publish(self, data):
        if self._published:
            raise FilesystemError("publication_denied", "Publish a newly claimed file once")
        # Failed partial publication is not retryable/adoptable under this claim.
        self._published = True
        super().publish(data)

    def remove(self):
        raise FilesystemError('cross_stream_fence_unavailable',
                              'Whole-object disposition requires an unavailable cross-stream fence; preserve all streams')


@contextmanager
def created_file(path, *, deletable=False):
    """Atomic no-replace writer-exclusive claim, held until complete context exit."""
    path = exact_path(path)
    with guarded_roots([path.parent]):
        parent, handle = _open(path.parent), None
        try:
            if not _info(parent).directory:
                raise FilesystemError("path_denied", "File parent must be a directory")
            handle = _create_file(parent, path.name, deletable=True) if deletable else _create_file(parent, path.name)
            info = _info(handle)
            if info.directory or info.links != 1:
                raise FilesystemError("identity_changed", "Expected a newly claimed single-link file")
            resource = CreatedFile(handle, info, deletable=deletable)
            resource._audit_target = path
            try:
                yield resource
            finally:
                resource._handle = None
        finally:
            if handle is not None:
                k.CloseHandle(handle)
            k.CloseHandle(parent)


def volume_identity(path) -> str:
    return file_info(path).identity.volume


def allocation_unit(path) -> int:
    """Exact local volume cluster bytes for conservative file-data rounding."""
    path = exact_path(path)
    with guarded_roots([path]):
        # Identity is GUID + serial; the Win32 query accepts the GUID root only.
        volume = file_info(path).identity.volume.rsplit(":", 1)[0] + "\\"
        sectors, sector_bytes, free, total = (w.DWORD() for _ in range(4))
        if not k.GetDiskFreeSpaceW(volume, c.byref(sectors), c.byref(sector_bytes),
                                 c.byref(free), c.byref(total)):
            raise c.WinError(c.get_last_error())
        unit = sectors.value * sector_bytes.value
        if not unit:
            raise FilesystemError("volume_unknown", "Positive allocation geometry is required")
        return unit


def available_bytes(path) -> int:
    path = exact_path(path)
    with guarded_roots([path]):
        available, total, free = c.c_ulonglong(), c.c_ulonglong(), c.c_ulonglong()
        if not k.GetDiskFreeSpaceExW(_extended(path), c.byref(available), c.byref(total), c.byref(free)):
            raise c.WinError(c.get_last_error())
        return available.value


def process_identity(pid) -> ProcessIdentity | None:
    _windows()
    if type(pid) is not int or not 0 < pid <= 0xFFFFFFFF:
        raise FilesystemError("process_denied", "Invalid process identifier")
    handle = k.OpenProcess(0x1000, False, pid)
    if not handle:
        if c.get_last_error() == 87:  # ERROR_INVALID_PARAMETER: no such PID
            return None
        raise c.WinError(c.get_last_error())  # access denied is uncertain, never dead
    try:
        creation, exit_time, kernel, user = (w.FILETIME() for _ in range(4))
        if not k.GetProcessTimes(handle, c.byref(creation), c.byref(exit_time),
                                 c.byref(kernel), c.byref(user)):
            raise c.WinError(c.get_last_error())
        if exit_time.dwLowDateTime or exit_time.dwHighDateTime:
            return None  # a terminated process object can outlive its PID handle
        buffer, length = c.create_unicode_buffer(32768), w.DWORD(32768)
        if not k.QueryFullProcessImageNameW(handle, 0, buffer, c.byref(length)):
            raise c.WinError(c.get_last_error())
        return ProcessIdentity(pid, creation.dwLowDateTime | (creation.dwHighDateTime << 32),
                               os.path.normcase(buffer.value))
    finally:
        k.CloseHandle(handle)


class RetainedGuard:
    """Deny writes/deletes to file identities through every hardlink alias.

    Immutable directory guards also temporarily deny add/delete-child with a
    noninheriting DACL ACE (share modes alone do not stop child creation). The
    original DACL/control is restored through retained WRITE_DAC handles. Do not
    abandon a guard or kill its process: those directory ACLs need explicit close.
    Unsupported protection refuses rather than exposing writable shared bytes.
    """
    def __init__(self, paths, *, immutable=False, exclusive=False, max_entries=10000):
        self._handles, self._acls, self._ancestors = [], [], None
        self._files, self._paths = [], []
        self._protection_tokens, self._protected_identities = [], set()
        self._directories, self._directory_identities = {}, set()
        if immutable and exclusive:
            raise FilesystemError("guard_mode", "Choose immutable sharing or exclusive ownership, not both")
        if type(max_entries) is not int or not 1 <= max_entries <= 100000:
            raise FilesystemError("inventory_limit", "Inventory limit must be a bounded positive integer")
        self.immutable, self.exclusive, self.max_entries = immutable, exclusive, max_entries
        try:
            roots = [exact_path(p) for p in paths]
            self._ancestors = guarded_roots([p.parent for p in roots])
            self._ancestors.__enter__()
            seen_paths = set()
            for root in roots:
                self._visit(root, seen_paths)
            if self.immutable:
                # All physical-identity tokens are acquired before ANY ACL edit.
                # A nested directory or hardlink conflict must not partially
                # snapshot/restore an existing guard's protection.
                protected = set()
                for path, handle, info in sorted(self._files, key=lambda entry: not entry[2].directory):
                    if info.identity in protected:
                        continue  # hardlink aliases share exactly one original DACL
                    acl_handle = _open(path, share=1, access=0x60080)
                    self._handles.append(acl_handle)
                    if _info(acl_handle).identity != info.identity:
                        raise FilesystemError("identity_changed", "Object changed during guard acquisition")
                    self._protect_directory(acl_handle, permissions=0x46 if info.directory else 0x10000)
                    protected.add(info.identity)
                # Enumeration preceded ACL installation. Refuse an appeared child
                # rather than publishing an incomplete immutable inventory.
                for path, names in self._directories.items():
                    if tuple(sorted(os.listdir(_extended(path)))) != names:
                        raise FilesystemError("identity_changed", "Directory changed during guard acquisition")
                # A hardlink path could have been removed/replaced during the
                # pre-ACL phase without changing directory names. Validate every
                # exposed alias after all declared parents have been protected.
                for path, _, info in self._files:
                    check = _open(path, share=1, access=0x80)
                    try:
                        if _info(check).identity != info.identity:
                            raise FilesystemError("identity_changed", "Exposed alias changed during guard acquisition")
                    finally:
                        k.CloseHandle(check)
            self.measurement = self.measure()
        except BaseException:
            self.close()
            raise

    def _visit(self, path, seen):
        key = str(path).casefold()
        if key in seen:
            raise FilesystemError("overlapping_roots", "Do not count overlapping owned paths")
        seen.add(key)
        if len(seen) > self.max_entries:
            raise FilesystemError("inventory_limit", "Bounded inventory exceeds entry limit")
        share = 0 if self.exclusive else (1 if self.immutable else 3)
        # READ_DATA is required for file hashing; WRITE_DAC/READ_CONTROL for dir ACL restoration.
        attrs_handle = _open(path, share=share, access=0x80000000)
        self._handles.append(attrs_handle)
        info = _info(attrs_handle)
        if info.directory:
            if info.identity in self._directory_identities:
                raise FilesystemError("overlapping_roots", "Physical directory aliases must not overlap")
            self._directory_identities.add(info.identity)
        if self.immutable and info.identity not in self._protected_identities:
            self._acquire_protection(info.identity)
        self._files.append((path, attrs_handle, info))
        self._paths.append(path)
        if info.directory:
            names = tuple(sorted(os.listdir(_extended(path))))
            self._directories[path] = names
            for name in names:
                self._visit(path / name, seen)

    def _acquire_protection(self, identity):
        # Semaphore (not recursively owned thread mutex): even same-thread guards
        # compete. Global namespace coordinates cooperating Windows sessions and
        # processes by volume-qualified identity, not a long/short/hardlink path.
        digest = hashlib.sha256((identity.volume + ":" + identity.file_id).encode("ascii")).hexdigest()
        token = k.CreateSemaphoreW(None, 1, 1, "Global\\RenulusImmutableV1-" + digest)
        if not token:
            raise c.WinError(c.get_last_error())
        result = k.WaitForSingleObject(token, 0)
        if result != 0:
            k.CloseHandle(token)
            if result == 258:
                raise FilesystemError("guard_busy", "Another guard owns immutable protection of this physical identity")
            raise FilesystemError("guard_wait", "Physical protection token could not be acquired")
        self._protection_tokens.append(token)
        self._protected_identities.add(identity)

    def _protect_directory(self, handle, permissions=0x2 | 0x4 | 0x40):
        dacl, descriptor = c.c_void_p(), c.c_void_p()
        result = a.GetSecurityInfo(handle, 1, 4, None, None, c.byref(dacl), None, c.byref(descriptor))
        if result:
            raise c.WinError(result)
        new_acl = c.c_void_p()
        try:
            control, revision = w.WORD(), w.DWORD()
            if not a.GetSecurityDescriptorControl(descriptor, c.byref(control), c.byref(revision)):
                raise c.WinError(c.get_last_error())
            sid, length = c.create_string_buffer(68), w.DWORD(68)
            if not a.CreateWellKnownSid(1, None, sid, c.byref(length)):  # Everyone
                raise c.WinError(c.get_last_error())
            ace = EXPLICIT_ACCESS(permissions, 3, 0,
                                  TRUSTEE(None, 0, 0, 1, c.cast(sid, c.c_void_p)))
            result = a.SetEntriesInAclW(1, c.byref(ace), dacl, c.byref(new_acl))
            if result:
                raise c.WinError(result)
            _native_audit("chmod", _handle_path(handle), _info(handle), retained=True)
            result = a.SetSecurityInfo(handle, 1, 4, None, None, new_acl, None)
            if result:
                raise c.WinError(result)
            self._acls.append((handle, descriptor, dacl, bool(control.value & 0x1000)))
            descriptor = None
        finally:
            if new_acl:
                k.LocalFree(new_acl)
            if descriptor:
                k.LocalFree(descriptor)

    def measure(self) -> Measurement:
        return _measure_entries(self._files)

    def hash_file(self, path) -> str:
        """Hash reviewed bytes through the retained immutable handle, no path reopen."""
        import msvcrt
        key = str(exact_path(path)).casefold()
        if not self.immutable:
            raise FilesystemError("guard_required", "Hashing requires retained immutable protection")
        for owned, handle, info in self._files:
            if str(owned).casefold() == key and not info.directory:
                _native_audit("read", owned, info, retained=True)
                # DuplicateHandle -> fd owns duplicate, not the guard's handle.
                duplicate = w.HANDLE()
                current = k.GetCurrentProcess
                current.restype, current.argtypes = w.HANDLE, []
                _signature(k, "DuplicateHandle", w.BOOL, w.HANDLE, w.HANDLE,
                           w.HANDLE, c.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD)
                if not k.DuplicateHandle(current(), handle, current(), c.byref(duplicate), 0, False, 2):
                    raise c.WinError(c.get_last_error())
                fd = msvcrt.open_osfhandle(duplicate.value, os.O_RDONLY | os.O_BINARY)
                with os.fdopen(fd, "rb") as stream:
                    stream.seek(0)
                    return hashlib.file_digest(stream, "sha256").hexdigest()
        raise FilesystemError("scope_denied", "File is not part of this guard")

    @property
    def entries(self):
        """Exact path + refreshed handle information; callers never reopen inventory files."""
        return tuple((path, _info(handle)) for path, handle, _ in self._files)

    def close(self):
        # Restoration failure is not settlement. Retain handles/descriptors for a
        # retry instead of silently leaving protected directories without an owner.
        while self._acls:
            handle, descriptor, dacl, protected = self._acls[-1]
            _native_audit("chmod", _handle_path(handle), _info(handle), retained=True)
            result = a.SetSecurityInfo(handle, 1, 4 | (0x80000000 if protected else 0x20000000),
                                       None, None, dacl, None)
            if result:
                raise c.WinError(result)
            k.LocalFree(descriptor)
            self._acls.pop()
        for handle in reversed(self._handles):
            k.CloseHandle(handle)
        self._handles.clear()
        if self._ancestors is not None:
            self._ancestors.__exit__(None, None, None)
            self._ancestors = None
        while self._protection_tokens:
            token = self._protection_tokens[-1]
            if not k.ReleaseSemaphore(token, 1, None):
                raise c.WinError(c.get_last_error())
            k.CloseHandle(token)
            self._protection_tokens.pop()
        self._protected_identities.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


@contextmanager
def serialized_guard(key):
    """Bounded cooperating-operation gate; never infers crash/sidecar recovery."""
    _windows()
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    token = k.CreateSemaphoreW(None, 1, 1, "Global\\RenulusRecorderV1-" + digest)
    if not token:
        raise c.WinError(c.get_last_error())
    acquired = False
    try:
        result = k.WaitForSingleObject(token, 30000)
        if result != 0:
            raise FilesystemError("recorder_busy", "Recorder operation gate unavailable; preserve state and retry or review recovery")
        acquired = True
        yield
    finally:
        if acquired and not k.ReleaseSemaphore(token, 1, None):
            raise c.WinError(c.get_last_error())
        k.CloseHandle(token)


def retained_guard(paths, *, immutable=False, exclusive=False, max_entries=10000):
    return RetainedGuard(paths, immutable=immutable, exclusive=exclusive, max_entries=max_entries)


def exclusive_guard(paths):
    """Exclusive exact-object fence, not a replacement for native/profile job coordination."""
    return retained_guard(paths, exclusive=True)


def _stream_metadata(handle):
    """Bounded FILE_STREAM_INFO; metadata only, never a mutation fence."""
    _windows()
    info = _info(handle)
    size = 4096
    while True:
        buffer = c.create_string_buffer(size)
        if k.GetFileInformationByHandleEx(handle, 7, buffer, size):
            break
        error = c.get_last_error()
        if error == 38 and info.directory:
            return ()
        if error not in (122, 234) or size == 1024 * 1024:
            if error in (122, 234):
                raise FilesystemError('stream_limit', 'Stream metadata exceeds the bounded native buffer')
            raise c.WinError(error)
        size = min(size * 2, 1024 * 1024)
    raw, offset, result, names = buffer.raw, 0, [], set()
    while True:
        if offset + 24 > size or len(result) >= 1024:
            raise FilesystemError('stream_limit', 'Invalid or oversized native stream metadata')
        following = int.from_bytes(raw[offset:offset+4], 'little')
        length = int.from_bytes(raw[offset+4:offset+8], 'little')
        logical = int.from_bytes(raw[offset+8:offset+16], 'little', signed=True)
        allocated = int.from_bytes(raw[offset+16:offset+24], 'little', signed=True)
        if not length and not following and not result and not logical and not allocated:
            if info.directory:
                return ()
            raise FilesystemError('stream_metadata', 'A regular file requires valid default-stream metadata')
        if not length or length % 2 or length > 65534 or offset + 24 + length > size or min(logical, allocated) < 0:
            raise FilesystemError('stream_metadata', 'Invalid native stream lengths/allocation')
        try:
            name = raw[offset+24:offset+24+length].decode('utf-16-le')
        except UnicodeDecodeError:
            raise FilesystemError('stream_metadata', 'Invalid native stream name') from None
        if '\0' in name or not name.startswith(':') or not name.endswith(':$DATA') or name.casefold() in names:
            raise FilesystemError('stream_metadata', 'Unrecognized/duplicate native stream record')
        names.add(name.casefold())
        result.append((name, logical, allocated))
        if not following:
            break
        if following % 8 or following < 24 + length or offset + following >= size:
            raise FilesystemError('stream_metadata', 'Invalid native stream record chain')
        offset += following
    return tuple(sorted(result))


def _data_info(handle, initial=None):
    info = _info(handle)
    if initial is not None and info.identity != initial.identity:
        raise FilesystemError("identity_changed", "An opened object changed identity")
    streams = _stream_metadata(handle)
    named = [item for item in streams if item[0] != '::$DATA']
    return DataInfo(info, streams,
                    (0 if info.directory else info.logical_bytes) + sum(item[1] for item in named),
                    (0 if info.directory else info.allocated_bytes) + sum(item[2] for item in named))


def directory_empty(path, *, identity=None):
    """Point-in-time no-follow emptiness, including zero-length directory streams.

    Retained path pins prevent replacement, not concurrent stream mutation. This
    validates cooperative admission; it never grants destructive authority.
    """
    path = exact_path(path)
    with guarded_roots([path]):
        handle = _open(path, access=1, share=3)
        try:
            info = _info(handle)
            if not info.directory or identity is not None and info.identity != identity:
                raise FilesystemError('identity_changed', 'Expected exact directory changed')
            return not _stream_metadata(handle) and not os.listdir(_extended(path))
        finally:
            k.CloseHandle(handle)


def _measure_entries(files):
    unique, count = {}, {}
    logical = 0
    for _, handle, initial in files:
        data = _data_info(handle, initial)
        info, data_allocated = data.info, data.allocated_bytes
        logical += data.logical_bytes
        if info.directory and not data_allocated and not data.logical_bytes:
            continue
        previous = unique.get(info.identity)
        # Metadata is point-in-time. If aliases differ during a cooperating
        # checkpoint, retain the larger observed allocation rather than undercount.
        unique[info.identity] = (info, max(data_allocated, previous[1] if previous else 0),
                                 max(initial.links, info.links, previous[2] if previous else 0))
        count[info.identity] = count.get(info.identity, 0) + 1
    by_volume = {}
    for identity, (_, allocated, _) in unique.items():
        by_volume[identity.volume] = by_volume.get(identity.volume, 0) + allocated
    return Measurement(logical, sum(allocated for _, allocated, _ in unique.values()),
                       sum(allocated for key, (info, allocated, links) in unique.items() if info.directory or count[key] == links),
                       by_volume, tuple(sorted(unique, key=lambda i: (i.volume, i.file_id))))


class MetadataInventory:
    """Read-only metadata accounting, NOT a read/immutable/exclusive work lease.

    Zero desired access coexists with exclusive native tokens. Leaf handles share
    read/write/delete so canonical writers can run; directory/ancestor list-only
    pins deny deletion and reject reparses. Files/size changes are point-in-time,
    not a quiescent snapshot; checkpoints require cooperating bounded producers.
    Inaccessible/changed objects always refuse, never disappear from accounting.
    """
    def __init__(self, paths, *, max_entries=10000):
        if type(max_entries) is not int or not 1 <= max_entries <= 100000:
            raise FilesystemError("inventory_limit", "Inventory limit must be a bounded positive integer")
        self._handles, self._files, self._directories = [], [], set()
        self._names = {}
        self._ancestors = None
        self.max_entries = max_entries
        try:
            roots = [exact_path(p) for p in paths]
            self._ancestors = _guarded_roots([p.parent for p in roots], access=1)
            self._ancestors.__enter__()
            seen = set()
            for root in roots:
                self._visit(root, seen)
            for path, names in self._names.items():
                if tuple(sorted(os.listdir(_extended(path)))) != names:
                    raise FilesystemError("identity_changed", "Directory inventory changed during accounting")
            for path, _, initial in self._files:
                check = _open(path, access=0, share=7)
                try:
                    if _info(check).identity != initial.identity:
                        raise FilesystemError("identity_changed", "Accounting alias changed during inventory")
                finally:
                    k.CloseHandle(check)
            self.measurement = self.measure()
        except BaseException:
            self.close()
            raise

    def _visit(self, path, seen):
        key = str(path).casefold()
        if key in seen:
            raise FilesystemError("overlapping_roots", "Do not count overlapping paths")
        seen.add(key)
        if len(seen) > self.max_entries:
            raise FilesystemError("inventory_limit", "Bounded inventory exceeds entry limit")
        handle = _open(path, access=0, share=7)
        self._handles.append(handle)
        info = _info(handle)
        if info.directory:
            # Retain the probe until the directory no-delete pin is validated.
            pinned = _open(path, access=1, share=3)  # LIST_DIRECTORY enforces no-delete sharing
            self._handles.append(pinned)
            current = _info(pinned)
            if current.identity != info.identity:
                raise FilesystemError("identity_changed", "Directory changed during metadata inventory")
            if info.identity in self._directories:
                raise FilesystemError("overlapping_roots", "Physical directory aliases must not overlap")
            self._directories.add(info.identity)
            handle = pinned
        self._files.append((path, handle, info))
        if info.directory:
            names = tuple(sorted(os.listdir(_extended(path))))
            self._names[path] = names
            for name in names:
                self._visit(path / name, seen)

    def measure(self):
        return _measure_entries(self._files)

    @property
    def data_entries(self):
        """All data-stream allocations through retained handles; FileInfo stays unchanged."""
        return tuple((path, _data_info(handle, initial)) for path, handle, initial in self._files)

    @property
    def entries(self):
        result = []
        for path, handle, initial in self._files:
            info = _info(handle)
            if info.identity != initial.identity:
                raise FilesystemError("identity_changed", "Metadata identity changed")
            result.append((path, info))
        return tuple(result)

    def close(self):
        for handle in reversed(self._handles):
            k.CloseHandle(handle)
        self._handles.clear()
        if self._ancestors is not None:
            self._ancestors.__exit__(None, None, None)
            self._ancestors = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def metadata_inventory(paths, *, max_entries=10000):
    return MetadataInventory(paths, max_entries=max_entries)


def measure_roots(paths, *, max_entries=10000) -> Measurement:
    with metadata_inventory(paths, max_entries=max_entries) as inventory:
        return inventory.measurement
