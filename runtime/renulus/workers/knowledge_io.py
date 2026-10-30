"""Authenticated native originals and inert readers; no canonical DB or services.

Canonical intent precedes reserve. Native claims and original I/O reuse the
existing Windows primitives. A failed/late publication is preserved with its
intent journal, never replaced or silently removed. Chooser grants are one-use
host files; paths never enter the command/reply JSON boundary.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import hmac
import json
from pathlib import Path
from threading import RLock
import time

from .artifacts import Refused
from .native_contracts import NativeIntent

MAX = 64 * 1024 * 1024
SUFFIX = {'text/plain': '.txt', 'text/markdown': '.md', 'text/csv': '.csv',
    'text/html': '.html', 'application/xml': '.xml', 'text/xml': '.xml',
    'application/pdf': '.pdf', 'image/png': '.png', 'image/jpeg': '.jpg', 'image/tiff': '.tiff',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx'}


def require(current):
    if not current():
        raise Refused('stale_revision')


def verified(data, size, digest):
    if not 0 < size <= MAX or len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise Refused('digest_mismatch')
    return data


class ProtectedHandles:
    """Constructor-only chooser registry. Synthetic tests inject callbacks here.

    Production consumes a main-process protected binary grant, then retains the
    exact no-follow selected file. No runtime method accepts an arbitrary path.
    """
    def __init__(self, config, *, selection=None, destination=None):
        self.config = config
        self.selection, self.destination = selection, destination
        self.used = set()

    def claim(self, handle, kind, fs):
        if handle in self.used or not handle.startswith('selected_') or not handle[9:].isalnum():
            raise Refused('artifact_denied')
        if len(handle) > 128:
            raise Refused('artifact_denied')
        callback = self.selection if kind == 1 else self.destination
        if callback is not None:
            path = callback(handle)
            if path is None:
                raise Refused('artifact_denied')
        else:
            with fs.opened_file(Path(self.config.grants_root) / handle) as resource:
                raw = resource.read(limit=16384)
            if (len(raw) < 51 or raw[:8] != b'RENKIO1\0' or raw[40] != kind
                    or int.from_bytes(raw[41:49], 'little') <= int(time.time() * 1000)
                    or not hmac.compare_digest(hashlib.sha256(raw[8:40]).hexdigest(), self.config.grant_token_sha256)):
                raise Refused('artifact_denied')
            path = raw[49:].decode('utf-16-le')
        # Never retry/rebind a consumed grant, even if the native claim fails.
        self.used.add(handle)
        return fs.exact_path(path)


class KnowledgeIO:
    def __init__(self, config, *, handles=None, storage=None, filesystem=None, opener=None):
        from renulus.storage import filesystem as native_fs
        from renulus.knowledge.ownership import NativeOwnership
        from .native_storage import NativeStorage
        self.config, self.fs = config, filesystem or native_fs
        self.root = self.fs.exact_path(config.originals_root)
        self.handles = handles or ProtectedHandles(config)
        self.opener = opener or open_original
        self.lock = RLock()
        self.owner = NativeOwnership(self.root.parent / (self.root.name + '.native-owner'), filesystem=self.fs)
        self.owner.acquire_for_path(self.root)
        self.storage = storage or NativeStorage([config.budget_root], self.root)
        self.intents = {}
        self.selections = {}
        self.closed = False

    @staticmethod
    def _binding(i):
        # stamp is expected to advance on original/ready canonical commits.
        return i.model_dump(exclude={'stamp'})

    def _handle(self, revision, digest):
        return 'original_' + hashlib.sha256((revision + ':' + digest).encode()).hexdigest()

    def _path(self, pin):
        if pin.original_handle != self._handle(pin.revision_id, pin.sha256):
            raise Refused('artifact_denied')
        suffix = SUFFIX.get(pin.media_type)
        if suffix is None:
            raise Refused('invalid_command')
        return self.root / (pin.original_handle + suffix)

    def _journal(self, i):
        return self.root / ('intent_' + hashlib.sha256(i.intent_id.encode()).hexdigest())

    def _read(self, path, size, digest, current):
        from renulus.knowledge.original_io import RetainedOriginalIO, CHUNK_BYTES
        with self.fs.opened_file(path) as resource:
            with RetainedOriginalIO(self.fs, resource, path) as io:
                return self._read_retained(io, size, digest, current, CHUNK_BYTES)

    @staticmethod
    def _read_retained(io, size, digest, current, chunk_bytes=1024 * 1024):
        require(current)
        io.checkpoint(expected_bytes=size)
        io._seek('read')
        body = bytearray()
        while len(body) < size:
            require(current)
            io.checkpoint(expected_bytes=size)
            body.extend(io._read(min(chunk_bytes, size - len(body))))
        io.checkpoint(expected_bytes=size)
        require(current)
        return verified(bytes(body), size, digest)

    def _reserved(self, i):
        record = self.intents.get(i.intent_id)
        if record is None or self._binding(record['intent']) != self._binding(i) or record['settled']:
            raise Refused('artifact_denied')
        return record

    def execute(self, input, body, current, publication_lock):
        from renulus.knowledge.original_io import RetainedOriginalIO
        with self.lock:
            require(current)
            if self.closed:
                raise Refused('worker_closed')
            action = input.action
            if action == 'reserve':
                i = input.intent
                if i.intent_id in self.intents:
                    self._reserved(i)
                    return {'reserved': True}
                if len(self.intents) >= 128:
                    raise Refused('artifact_limit')
                # Existing journal means recovery is required, never a new claim.
                if self.fs.path_exists(self._journal(i)):
                    raise Refused('artifact_denied')
                self.storage.reserve(i.reservation_id, i.intent_id, 2 * i.bytes + 8 * 1024 ** 2)
                record = {'intent': i, 'settled': False, 'original': None, 'lease': None,
                    'claimed': False, 'journal': False}
                self.intents[i.intent_id] = record
                with self.fs.created_file(self._journal(i)) as resource:
                    resource.publish(json.dumps(self._binding(i), separators=(',', ':')).encode())
                record['journal'] = True
                require(current)
                return {'reserved': True}
            if action == 'read_selection':
                i = input.intent
                self._reserved(i)
                selected = self.selections.get(input.handle)
                if selected is None:
                    path = self.handles.claim(input.handle, 1, self.fs)
                    lease = ExitStack()
                    try:
                        resource = lease.enter_context(self.fs.opened_file(path))
                        io = lease.enter_context(RetainedOriginalIO(self.fs, resource, path))
                        selected = (i.intent_id, lease, io)
                        self.selections[input.handle] = selected
                    except BaseException:
                        lease.close()
                        raise
                if selected[0] != i.intent_id:
                    raise Refused('artifact_denied')
                return self._read_retained(selected[2], i.bytes, i.sha256, current)
            if action == 'publish':
                i = input.intent
                record = self._reserved(i)
                verified(body, i.bytes, i.sha256)
                handle = self._handle(i.revision_id, i.sha256)
                if record['original'] is not None:
                    require(current)
                    return {'original_handle': record['original']}
                if record['claimed']:
                    raise Refused('artifact_denied')
                path = self.root / (handle + SUFFIX[i.media_type])
                # Serialize final cancellation check and atomic no-replace claim.
                # The lease then survives cancellation until actual settle.
                with publication_lock:
                    require(current)
                    lease = ExitStack()
                    resource = lease.enter_context(self.fs.created_file(path))
                    record['claimed'], record['lease'] = True, lease
                io = lease.enter_context(RetainedOriginalIO(self.fs, resource, path))
                io.publish(body)
                if io.sha256(expected_bytes=i.bytes) != i.sha256:
                    raise Refused('digest_mismatch')
                record['original'] = handle
                require(current)  # Late bytes remain journalled; no reference escapes.
                return {'original_handle': handle}
            if action == 'settle':
                i = input.intent
                record = self.intents.get(i.intent_id)
                if record is None:
                    # Failed admission has no native reservation to release.
                    return {'settled': True}
                if self._binding(record['intent']) != self._binding(i):
                    raise Refused('artifact_denied')
                if record['settled']:
                    return {'settled': True}
                if record['lease'] is not None:
                    record['lease'].close()
                    record['lease'] = None
                for handle, selected in list(self.selections.items()):
                    if selected[0] == i.intent_id:
                        selected[1].close()
                        del self.selections[handle]
                debt = i.bytes if record['claimed'] and input.state != 'ready' else 0
                self.storage.settle(i.reservation_id, i.intent_id, cleanup_debt_bytes=debt)
                record['settled'] = True
                return {'settled': True}
            if action == 'measure':
                return {**self.storage.measure(), **self.storage.status(), 'ceiling_bytes': self.storage.ceiling}
            if action == 'retire':
                try:
                    return self.storage.retire(self.config.budget_root, input.candidate_id)
                except ValueError:
                    raise Refused('invalid_command')
            p = input.pin
            if action == 'read':
                return self._read(self._path(p), p.bytes, p.sha256, current)
            if action in ('payload', 'asset'):
                verified(body, p.bytes, p.sha256)
                # Pin metadata is host/canonical authority; body must match it.
                return self._parse(input, body)
            if action == 'handoff':
                data = self._read(self._path(p), p.bytes, p.sha256, current)
                with publication_lock:
                    require(current)
                    if input.operation == 'save':
                        if input.destination_handle is None:
                            raise Refused('artifact_denied')
                        path = self.handles.claim(input.destination_handle, 2, self.fs)
                        with self.fs.created_file(path) as resource:
                            with RetainedOriginalIO(self.fs, resource, path) as io:
                                io.publish(data)
                                if io.sha256(expected_bytes=p.bytes) != p.sha256:
                                    raise Refused('digest_mismatch')
                    else:
                        if input.destination_handle is not None:
                            raise Refused('invalid_command')
                        # Only a declared app-generated original destination reaches
                        # the OS document association; no shell/command string.
                        self.opener(self._path(p))
                return {'handed_off': True}
            raise Refused('invalid_command')

    @staticmethod
    def _parse(input, body):
        from renulus.knowledge.reader_models import ReaderRequest
        from renulus.knowledge.reader_text import text_payload
        from renulus.knowledge.reader_binary import (pdf_payload, docx_payload, xlsx_payload,
            image_payload, binary_asset)
        p = input.pin
        suffix = SUFFIX[p.media_type]
        request = ReaderRequest.model_validate({'reference': {'target': {
            'type': 'library_revision', 'id': p.revision_id}}, **input.position.model_dump()})
        if input.action == 'asset':
            return binary_asset(body, suffix, input.asset_id)
        parse = {'.pdf': pdf_payload, '.docx': docx_payload, '.xlsx': xlsx_payload,
            '.png': image_payload, '.jpg': image_payload, '.tiff': image_payload}.get(suffix)
        payload = parse(body, request) if parse else text_payload(body, suffix, request)
        return payload.model_dump(mode='json')

    def close(self):
        with self.lock:
            for selected in self.selections.values():
                selected[1].close()
            self.selections.clear()
            for record in self.intents.values():
                if record['lease'] is not None:
                    record['lease'].close()
                    record['lease'] = None
            self.owner.close()
            self.closed = True


def open_original(path):
    """Launch a declared original with the Windows document association API."""
    import ctypes
    from ctypes import wintypes as w
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    function = shell.ShellExecuteW
    function.argtypes = [w.HWND, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, w.INT]
    function.restype = w.HINSTANCE
    result = function(None, 'open', str(path), None, None, 1)
    if not result or int(result) <= 32:
        raise Refused('engine_failed')
