# SPDX-License-Identifier: MIT
"""Worker-owned measured peak reservations. Never opens canonical SQLite.

The host persists the intent before calling reserve. Roots are supplied by the
launcher, never by a JSON/model request. Retain reservations until actual native
settlement; uncertainty retains both charge and cleanup debt. No eviction/deletion.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from threading import RLock

from renulus.storage import filesystem as fs

DEFAULT_CEILING = 100_000_000_000
FREE_FLOOR = 12 * 1024 ** 3


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    intent_id: str
    peak_bytes: int


class NativeStorage:
    def __init__(self, managed_roots, target_root, *, ceiling_bytes=DEFAULT_CEILING,
                 free_floor_bytes=FREE_FLOOR, max_entries=100000):
        if not 50_000_000_000 <= ceiling_bytes <= 150_000_000_000 or free_floor_bytes < FREE_FLOOR:
            raise ValueError("storage_budget_invalid")
        self.roots = tuple(fs.canonical_path(Path(p)) for p in managed_roots)
        self.target = fs.canonical_path(Path(target_root))
        self.ceiling, self.floor, self.max_entries = ceiling_bytes, free_floor_bytes, max_entries
        self._lock, self._reservations, self._debt = RLock(), {}, {}

    def measure(self):
        with fs.metadata_inventory(self.roots, max_entries=self.max_entries) as inventory:
            measured = inventory.measurement
            return {"logical_bytes": measured.logical_bytes, "allocated_bytes": measured.allocated_bytes,
                    "unique_bytes": sum(measured.by_volume.values()),
                    "free_bytes": fs.available_bytes(self.target)}

    def reserve(self, reservation_id: str, intent_id: str, peak_bytes: int):
        if not reservation_id or not intent_id or type(peak_bytes) is not int or peak_bytes <= 0:
            raise ValueError("storage_reservation_invalid")
        request = Reservation(reservation_id, intent_id, peak_bytes)
        with self._lock:
            previous = self._reservations.get(reservation_id)
            if previous:
                if previous != request:
                    raise ValueError("storage_reservation_conflict")
                return self.status()
            observed = self.measure()  # Inaccessible/locked/changed objects refuse, never count as zero.
            held = sum(r.peak_bytes for r in self._reservations.values()) + sum(self._debt.values())
            if observed["allocated_bytes"] + held + peak_bytes > self.ceiling or observed["free_bytes"] - held - peak_bytes < self.floor:
                raise ValueError("storage_waiting_space")
            self._reservations[reservation_id] = request
            return {**observed, **self.status()}

    def settle(self, reservation_id: str, intent_id: str, *, settled=True, cleanup_debt_bytes=0):
        with self._lock:
            previous = self._reservations.get(reservation_id)
            if previous is None or previous.intent_id != intent_id:
                raise ValueError("storage_reservation_missing")
            if type(cleanup_debt_bytes) is not int or cleanup_debt_bytes < 0:
                raise ValueError("storage_debt_invalid")
            if not settled:
                return self.status()  # Observer timeout is not settlement.
            del self._reservations[reservation_id]
            if cleanup_debt_bytes:
                self._debt[reservation_id] = cleanup_debt_bytes
            return self.status()

    def retire(self, profile_root, candidate_id):
        """Whole-object deletion is unfenced across streams, so a discarded candidate's
        bytes are retained as owned cleanup debt. Unknown and selected generations refuse."""
        with self._lock:
            profile, relative = fs.canonical_path(Path(profile_root)), "generations/" + candidate_id
            selector = profile / ".renulus-backend-selector.json"
            if fs.path_exists(selector):
                with fs.opened_file(selector) as resource:
                    if json.loads(resource.read(limit=16384)).get("generationPath") == relative:
                        raise ValueError("storage_generation_current")
            key = "generation:" + candidate_id
            if key not in self._debt:
                directory = profile / relative
                if not fs.path_exists(directory):
                    raise ValueError("storage_generation_unknown")
                with fs.metadata_inventory([directory], max_entries=self.max_entries) as inventory:
                    self._debt[key] = inventory.measurement.allocated_bytes
            return {"result": "retained_as_debt", "debt_bytes": self._debt[key]}

    def status(self):
        with self._lock:
            return {"reserved_bytes": sum(r.peak_bytes for r in self._reservations.values()),
                    "cleanup_debt_bytes": sum(self._debt.values()), "reservations": len(self._reservations)}

    def reconcile_debt(self, reservation_id: str, *, verified_reclaimed: bool):
        # Only an owned native cleanup receipt may discharge debt; this class deletes nothing.
        if verified_reclaimed is not True:
            raise ValueError("storage_cleanup_unconfirmed")
        with self._lock:
            self._debt.pop(reservation_id, None)
