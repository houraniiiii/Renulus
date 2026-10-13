"""Knowledge-only native lifetime fences and conservative target-volume forecasts.

Uses #27's shared Windows filesystem API, not a competing lease ledger. There is
no POSIX enforcement fallback: portable tests explicitly inject a filesystem
model. Native token files are local coordination objects, never canonical data.
"""
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
from threading import RLock

from ..contracts import ApiError

MIN_FREE_BYTES = 12 * 1024 ** 3
NATIVE_MARGIN = 8 * 1024 ** 2


def filesystem_api():
    try:
        from ..storage import filesystem
    except ImportError:
        raise ApiError('index_ownership_unavailable',
            'The Windows Library ownership policy is not installed', 503, True) from None
    return filesystem


def exact_path_absent(filesystem, path):
    """Acknowledge absence only under no-follow pins of existing ancestors.

    Never create a missing namespace to retire it. A reparse, access failure or
    concurrent creation is uncertainty, not absence or deletion authority.
    """
    path = Path(path).absolute()
    ancestor, missing_child = path.parent, None
    while not filesystem.path_exists(ancestor):
        missing_child = ancestor
        parent = ancestor.parent
        if parent == ancestor:
            raise RuntimeError('No verifiable Library ancestor')
        ancestor = parent
    with filesystem.guarded_roots([ancestor]):
        if missing_child is not None:
            # Recheck the first absent child of the now-pinned ancestor, not a
            # descendant lookup through a newly appeared/unpinned reparse path.
            if filesystem.path_exists(missing_child):
                raise RuntimeError('Library absence namespace changed')
            return True
        return not filesystem.path_exists(path)


class NativeOwnership:
    """Retain one exact no-sharing file handle until its actual owner closes.

    The same physical token coordinates threads, processes and hardlink aliases.
    Its parents are pinned by exclusive_guard. No timestamp, PID disappearance,
    serialized_guard timeout, SQLite restore or garbage collector releases it.
    """
    def __init__(self, token, *, filesystem=None):
        self.path = Path(token)
        self.fs = filesystem or filesystem_api()
        self._guard = None
        self._path_pin = None
        self._sealed = False
        self._pid = os.getpid()
        self.process = None
        self._lock = RLock()

    def acquire(self):
        with self._lock:
            if self._sealed:
                raise ApiError('index_close_pending', 'The Library owner has sealed native admission', 503, True)
            if self._guard is not None:
                self.require()
                return self
            try:
                # Atomic no-replace publication. A concurrent first creator may
                # cause retryable refusal, never overwrite/adoption of its bytes.
                if not self.fs.path_exists(self.path):
                    with self.fs.created_file(self.path) as created:
                        created.publish(b'Renulus native ownership v1\n')
                process = self.fs.process_identity(self._pid)
                if process is None:
                    raise RuntimeError('Uncertain current process identity')
                guard = self.fs.exclusive_guard([self.path])
                self.process, self._guard = process, guard
            except Exception:
                raise ApiError('index_owner_busy',
                    'This Library is owned elsewhere or its native ownership needs recovery. Close the other profile and retry',
                    503, True) from None
            return self

    def acquire_for_path(self, target, *, create=True):
        """Validate/pin the actual generation before deriving its sibling token.

        A lexical sibling alone never checks the generation itself. No-follow
        handles refuse junctions; canonical long names coordinate short-name
        aliases. Newly created ancestors/leaves retain their atomic creation
        handles until exact generation pins and the sibling token are acquired.
        Retirement retains the pins; close is not tree-reclamation authority.
        """
        with self._lock:
            if self._guard is not None:
                self.require_open()
                return self
            pin = None
            try:
                target = Path(target).absolute()
                missing = []
                parent = target.parent
                while not self.fs.path_exists(parent):
                    missing.append(parent)
                    ancestor = parent.parent
                    if ancestor == parent:
                        raise RuntimeError('No verifiable Library ancestor')
                    parent = ancestor
                if not create and (missing or not self.fs.path_exists(target)):
                    raise RuntimeError('Retirement cannot create its missing generation')
                with ExitStack() as claims:
                    claims.enter_context(self.fs.guarded_roots([parent]))
                    created = []
                    for folder in [*reversed(missing), target]:
                        if not self.fs.path_exists(folder):
                            info = claims.enter_context(self.fs.created_directory(folder))
                            created.append((folder, info.identity))
                        elif folder in missing:
                            # A previously absent parent appeared before our claim.
                            raise RuntimeError('Library creation namespace changed')
                    pin = self.fs.guarded_roots([target])
                    pin.__enter__()
                    for folder, identity in created:
                        current = self.fs.file_info(folder)
                        if not current.directory or current.identity != identity:
                            raise RuntimeError('Library creation identity changed')
                    physical = self.fs.canonical_path(target)
                    self.path = physical.parent / (physical.name + '.native-owner')
                    self.acquire()
                self._path_pin = pin
            except Exception:
                if pin is not None:
                    pin.__exit__(None, None, None)
                raise ApiError('index_owner_busy',
                    'This Library generation is owned elsewhere or its exact physical path needs recovery',
                    503, True) from None
            return self

    def release_path_pin(self):
        # Called only after native handles close; the token still owns parents.
        with self._lock:
            self.require()
            if self._path_pin is not None:
                self._path_pin.__exit__(None, None, None)
                self._path_pin = None

    def require(self):
        if self._guard is None or self._pid != os.getpid():
            raise ApiError('index_owner_required',
                'The Library native lifetime is not owned by this process', 503, True)

    def seal(self):
        # Seal admission, not ownership: drain/retirement/close still require and
        # retain the exact handle until real settlement.
        with self._lock:
            self.require()
            self._sealed = True

    def require_open(self):
        self.require()
        if self._sealed:
            raise ApiError('index_close_pending', 'The Library owner has sealed native admission', 503, True)

    @contextmanager
    def maintenance(self):
        # Caller serializes native operations and drains all readers. The token
        # remains held after this operation, including a native failure/timeout.
        self.require()
        yield

    def close(self):
        with self._lock:
            if self._guard is not None:
                self.require()
                self.release_path_pin()
                self._guard.close()  # failure retains authority for retry
                self._guard = None


@dataclass(frozen=True)
class CapacityForecast:
    logical_bytes: int
    allocated_bytes: int
    peak_bytes: int


class KnowledgeCapacity:
    """Admission before bytes are materialized, with bounded phase rechecks.

    Measurements are metadata-only unique physical allocation, not an immutable
    work lease. The caller already holds native/profile ownership. The initial
    forecast is deliberately conservative: a full measured rewrite plus overlap
    and native margin. Serial actual SDK acceptance must calibrate its peak.
    """
    def __init__(self, *, filesystem=None, floor_bytes=MIN_FREE_BYTES):
        if type(floor_bytes) is not int or floor_bytes < MIN_FREE_BYTES:
            raise ValueError('The existing 12 GiB floor cannot be lowered')
        self.fs = filesystem or filesystem_api()
        self.floor_bytes = floor_bytes

    @staticmethod
    def rows_bytes(rows):
        return sum(len(row['text'].encode('utf-8')) + 4 * len(row['vector']) +
                   sum(len(row[key].encode('utf-8')) for key in ('passage_id', 'revision_id', 'document_id')) + 128
                   for row in rows)

    def preflight(self, target, *, operation, growth_bytes=0, live_bytes=0, measured_root=None):
        if any(type(value) is not int or value < 0 for value in (growth_bytes, live_bytes)):
            raise ValueError('Capacity forecasts require nonnegative bytes')
        try:
            target = Path(target)
            while not self.fs.path_exists(target):
                parent = target.parent
                if parent == target:
                    raise RuntimeError('No owned target volume')
                target = parent
            logical = allocated = 0
            if measured_root is not None and self.fs.path_exists(measured_root):
                measurement = self.fs.measure_roots([measured_root], max_entries=100000)
                logical, allocated = measurement.logical_bytes, measurement.allocated_bytes
            rewrite = max(logical, allocated, live_bytes)
            if operation == 'original':
                peak = growth_bytes + 1024 ** 2
            elif operation in ('stage', 'fts', 'rebuild', 'maintenance', 'removal'):
                peak = 2 * (rewrite + growth_bytes) + NATIVE_MARGIN
            else:
                raise ValueError('Unknown Library capacity operation')
            if self.fs.available_bytes(target) < self.floor_bytes + peak:
                raise ApiError('knowledge_low_space',
                    'Library work is waiting for disk space on its target volume. Originals and ready documents are preserved; free space and retry',
                    503, True)
            return CapacityForecast(logical, allocated, peak)
        except ApiError:
            raise
        except Exception:
            raise ApiError('knowledge_capacity_unavailable',
                'Library target-volume capacity could not be verified. Preserve the current profile and retry', 503, True) from None
