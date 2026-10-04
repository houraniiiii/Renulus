"""Isolated synthetic state and test-only providers; never live inference."""

import asyncio
from contextlib import closing
from copy import deepcopy
from pathlib import Path

import pytest

from renulus.cases.repository import CaseRepository
from renulus.services import Services
from renulus.storage import AppPaths, Database

SENTINEL = "RENULUS_SYNTHETIC_CASE_63F8A9_NEVER_AUTOSAVE"
LATE_SENTINEL = "RENULUS_SYNTHETIC_LATE_RESULT_217FBA"
HIDDEN_SENTINEL = "RENULUS_SYNTHETIC_UNREVEALED_56DE93"

TEACHING = {
    "id": "case-synthetic-transplant", "version": 1, "topic_id": "transplantation",
    "title": "Synthetic staged transplant learning", "summary": "A synthetic teaching scenario",
    "synthetic": True, "original": True, "usage": "teaching", "license": "CC-BY-4.0",
    "review": {"status": "assistant_reviewed"},
    "stages": [
        {"id": "presentation", "narrative": "Initial synthetic presentation",
         "prompts": ["What information would help?"],
         "teaching_points": ["First stage debrief, hidden initially"], "sources": []},
        {"id": "additional-information", "narrative": HIDDEN_SENTINEL,
         "prompts": ["How does the additional information change your reasoning?"],
         "teaching_points": ["Second stage debrief, hidden until completion"], "sources": []},
    ],
    "take_home": ["Synthetic general learning conclusion"],
}


class ContentFixture:
    def __init__(self):
        self.item = deepcopy(TEACHING)

    def list_cases(self):
        return [deepcopy(self.item)]

    def get_case(self, case_id):
        if case_id != self.item["id"]:
            raise LookupError("Unknown synthetic case")
        return deepcopy(self.item)


class ProviderFixture:
    def __init__(self, deltas=None, error=None, *, blocked=False, ignore_cancel=False):
        self.deltas = ["Synthetic answer"] if deltas is None else deltas
        self.error = error
        self.blocked = blocked
        self.ignore_cancel = ignore_cancel
        self.calls = []
        self.cancelled = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    def status(self):
        return {"status": "test-only"}

    async def stream(self, messages, *, scope, run_id, model=None, system=None, purpose="explain"):
        self.calls.append({"messages": deepcopy(messages), "scope": scope.model_copy(deep=True),
                           "run_id": run_id, "model": model, "system": system, "purpose": purpose})
        for index, delta in enumerate(self.deltas):
            if self.blocked and index == 1:
                self.started.set()
                try:
                    await self.release.wait()
                except asyncio.CancelledError:
                    if not self.ignore_cancel:
                        raise
                    await self.release.wait()
            yield delta
        if self.error:
            raise self.error

    async def cancel(self, run_id):
        self.cancelled.append(run_id)
        return True


@pytest.fixture
def services(tmp_path):
    paths = AppPaths.create(tmp_path / "cases-profile")
    db = Database(paths.database)
    schema = Path(__file__).parents[2] / "runtime/renulus/cases/schema.sql"
    db.apply_migration("cases-001", schema.read_text(encoding="utf-8"))
    result = Services(paths, db)
    result.registry["content"] = ContentFixture()
    # Empty app-owned history/export/cache directories exercise every retention path.
    for name in ("history", "export", "backups"):
        (paths.root / name).mkdir()
    return result


@pytest.fixture
def repository(services):
    return CaseRepository(services)


def assert_absent_from_profile(services, *sentinels):
    for path in services.paths.root.rglob("*"):
        if path.is_file():
            raw = path.read_bytes()
            for sentinel in sentinels:
                assert sentinel.encode() not in raw, f"Synthetic content leaked into {path.name}"
    with closing(services.db.connect()) as conn:
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            table = row[0]
            # Names come from the app schema, never test/user input.
            data = repr([tuple(r) for r in conn.execute(f'SELECT * FROM "{table}"')])
            for sentinel in sentinels:
                assert sentinel not in data, f"Synthetic content leaked into table {table}"


def assert_terminals(events, expected):
    assert [e.sequence for e in events] == sorted(set(e.sequence for e in events))
    assert len({e.run_id for e in events}) == 1
    terminals = [e.type for e in events if e.type in ("completed", "failed", "cancelled")]
    assert terminals == [expected]
