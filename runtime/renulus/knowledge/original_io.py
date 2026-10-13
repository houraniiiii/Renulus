"""Bounded Library default-stream I/O on an already retained Windows claim.

This restores the existing 64 MiB original contract without changing recorder
limits or the frozen filesystem. It opens no data path, duplicates no handle and
loads no WinDLL: it uses the retained core resource and core-bound primitives.
Every native data read/write/truncate/flush is explicitly audited BEFORE the
call. Stream metadata checkpoints are observations, never all-stream ownership,
reclamation authority or a fence against later aliases/ADS.
"""
from __future__ import annotations

import hashlib
import sys

from .engines import MAX_BYTES

MAX_ORIGINAL_BYTES = MAX_BYTES
CHUNK_BYTES = 1024 ** 2
STREAM_METADATA_BYTES = 1024 ** 2


def _refuse_named_streams(fs, handle):
    """Bounded FILE_STREAM_INFO through the SAME handle; never open an ADS."""
    size = 4096
    while True:
        buffer = fs.c.create_string_buffer(size)
        if fs.k.GetFileInformationByHandleEx(handle, 7, buffer, size):
            break
        error = fs.c.get_last_error()
        if error not in (122, 234) or size >= STREAM_METADATA_BYTES:
            if error in (122, 234):
                raise fs.FilesystemError('stream_limit', 'Original stream metadata is uncertain; preserve the original')
            raise fs.c.WinError(error)
        size = min(size * 2, STREAM_METADATA_BYTES)
    raw, offset, records = buffer.raw, 0, 0
    while True:
        if offset + 24 > size or records >= 1024:
            raise fs.FilesystemError('stream_limit', 'Original stream metadata is uncertain; preserve the original')
        following = int.from_bytes(raw[offset:offset+4], 'little')
        length = int.from_bytes(raw[offset+4:offset+8], 'little')
        logical = int.from_bytes(raw[offset+8:offset+16], 'little', signed=True)
        allocated = int.from_bytes(raw[offset+16:offset+24], 'little', signed=True)
        if not length or length % 2 or length > 65534 or offset + 24 + length > size or min(logical, allocated) < 0:
            raise fs.FilesystemError('stream_metadata', 'Original stream metadata is uncertain; preserve the original')
        try:
            name = raw[offset+24:offset+24+length].decode('utf-16-le')
        except UnicodeDecodeError:
            raise fs.FilesystemError('stream_metadata', 'Original stream metadata is uncertain; preserve the original') from None
        if name != '::$DATA':
            raise fs.FilesystemError('named_stream_hold', 'Unknown original streams remain preserved; publication is held')
        records += 1
        if records != 1 or following:
            # A regular file must have exactly one default stream. No named or
            # duplicate stream is accepted, regardless of its content/size.
            raise fs.FilesystemError('named_stream_hold', 'Unknown original streams remain preserved; publication is held')
        return


class RetainedOriginalIO:
    """Library-only wrapper; caller retains its no-replace creation/open context.

    The parent/ancestor no-delete pins and exact physical DOS target remain live
    for this wrapper's lifetime. No auto-repair, retry of partial publication or
    removal occurs. CreatedFile's existing once-only flag is consumed before I/O.
    """
    def __init__(self, filesystem, resource, path):
        self.fs, self.resource = filesystem, resource
        self.path = filesystem.exact_path(path)
        self.identity = resource.info.identity
        self._pins = None
        self._parent_identity = None

    def __enter__(self):
        fs = self.fs
        if not isinstance(self.resource, fs.OpenedFile) or self.resource._handle is None:
            raise fs.FilesystemError('publication_denied', 'A live retained native original handle is required')
        self._pins = fs.guarded_roots([self.path.parent])
        self._pins.__enter__()
        try:
            self.path = fs.canonical_path(self.path)
            self._parent_identity = fs.file_info(self.path.parent).identity
            if fs.file_info(self.path).identity != self.identity:
                raise fs.FilesystemError('identity_changed', 'Original target changed before retained I/O')
            self.checkpoint()
        except BaseException:
            self._pins.__exit__(*sys.exc_info())
            self._pins = None
            raise
        return self

    def __exit__(self, *exc):
        # Closing pins is not a disposition or a new ownership claim. Do not run
        # a new fallible validation AFTER the caller's canonical commit.
        if self._pins is not None:
            self._pins.__exit__(*exc)
            self._pins = None

    def checkpoint(self, *, expected_bytes=None):
        fs = self.fs
        if self._pins is None or self.resource._handle is None:
            raise fs.FilesystemError('publication_denied', 'Original retained context is closed')
        info = self.resource.check()
        parent = fs.file_info(self.path.parent)
        if (info.identity != self.identity or info.directory or info.links != 1 or
                not parent.directory or parent.identity != self._parent_identity):
            raise fs.FilesystemError('identity_changed', 'Original identity, parent or alias changed; preserve all bytes')
        if not 0 <= info.logical_bytes <= MAX_ORIGINAL_BYTES or (expected_bytes is not None and info.logical_bytes != expected_bytes):
            raise fs.FilesystemError('publication_incomplete', 'Original length did not verify; preserve the recorded attempt')
        _refuse_named_streams(fs, self.resource._handle)
        return info

    def _audit(self, operation):
        # Same event shape as storage filesystem._native_audit (producer15).
        # The identity is captured from the retained resource, not a pathname
        # lookup. Audit denial propagates; no call/fallback follows a refusal.
        sys.audit('renulus.storage.native', operation, str(self.path), self.identity, True)

    def _seek(self, operation):
        self._audit(operation)
        self.fs._seek_start(self.resource._handle)

    def _write(self, data):
        fs = self.fs
        if not 0 < len(data) <= CHUNK_BYTES:
            raise fs.FilesystemError('publication_denied', 'Original native chunks must be at most 1 MiB')
        buffer, count = fs.c.create_string_buffer(data), fs.w.DWORD()
        self._audit('write')
        if not fs.k.WriteFile(self.resource._handle, buffer, len(data), fs.c.byref(count), None):
            raise fs.c.WinError(fs.c.get_last_error())
        return count.value

    def _truncate(self):
        self._audit('truncate')
        if not self.fs.k.SetEndOfFile(self.resource._handle):
            raise self.fs.c.WinError(self.fs.c.get_last_error())

    def _flush(self):
        self._audit('flush')
        if not self.fs.k.FlushFileBuffers(self.resource._handle):
            raise self.fs.c.WinError(self.fs.c.get_last_error())

    def _read(self, size):
        fs = self.fs
        if type(size) is not int or not 0 < size <= CHUNK_BYTES:
            raise fs.FilesystemError('publication_denied', 'Original native chunks must be at most 1 MiB')
        buffer, count = fs.c.create_string_buffer(size), fs.w.DWORD()
        self._audit('read')
        if not fs.k.ReadFile(self.resource._handle, buffer, size, fs.c.byref(count), None):
            raise fs.c.WinError(fs.c.get_last_error())
        if count.value != size:
            raise fs.FilesystemError('publication_incomplete', 'Incomplete original read; preserve the recorded attempt')
        return buffer.raw

    def publish(self, data):
        fs = self.fs
        if (not isinstance(data, bytes) or not 0 < len(data) <= MAX_ORIGINAL_BYTES or
                not isinstance(self.resource, fs.CreatedFile) or not self.resource.writable or self.resource._published):
            raise fs.FilesystemError('publication_denied', 'Publish one newly claimed original, nonempty and at most 64 MiB')
        self.resource._published = True  # No partial-write retry, including audit refusal.
        self.checkpoint(expected_bytes=0)
        self._seek('write')
        offset = 0
        while offset < len(data):
            self.checkpoint(expected_bytes=offset)
            chunk = data[offset:offset+CHUNK_BYTES]
            if self._write(chunk) != len(chunk):
                raise fs.FilesystemError('publication_incomplete', 'Incomplete original write; preserve the recorded attempt')
            offset += len(chunk)
            self.checkpoint(expected_bytes=offset)
        self.checkpoint(expected_bytes=len(data))
        self._truncate()
        self.checkpoint(expected_bytes=len(data))
        self._flush()
        self.checkpoint(expected_bytes=len(data))

    def sha256(self, *, expected_bytes):
        fs = self.fs
        if type(expected_bytes) is not int or not 0 < expected_bytes <= MAX_ORIGINAL_BYTES:
            raise fs.FilesystemError('publication_denied', 'Original hash requires a nonempty expected length up to 64 MiB')
        self.checkpoint(expected_bytes=expected_bytes)
        self._seek('read')
        digest, offset = hashlib.sha256(), 0
        while offset < expected_bytes:
            self.checkpoint(expected_bytes=expected_bytes)
            size = min(CHUNK_BYTES, expected_bytes-offset)
            chunk = self._read(size)
            if len(chunk) != size:
                raise fs.FilesystemError('publication_incomplete', 'Incomplete original read; preserve the recorded attempt')
            digest.update(chunk)
            offset += size
            self.checkpoint(expected_bytes=expected_bytes)
        return digest.hexdigest()
