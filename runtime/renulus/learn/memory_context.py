"""Volatile canonical pins for Memory used by one ordinary-study explanation."""
import asyncio
from contextlib import suppress
from dataclasses import dataclass, field

from renulus.contracts import ApiError
from renulus.memory.models import ELIGIBLE_SCOPES


def memory_changed():
    return ApiError("explain_memory_changed",
        "Learner memory changed during this explanation. Your question was kept; start a new explanation.",
        409, True)


@dataclass(frozen=True)
class MemoryContext:
    # These pins and text live only for this request; never persist a summary.
    pins: tuple = field(default=(), repr=False)
    context: str = field(default="", repr=False)

    @classmethod
    def capture(cls, db, recalled, topic_id):
        records = recalled.get("records", []) if isinstance(recalled, dict) else []
        pins, lines, size, seen = [], [], 0, set()
        if not isinstance(records, list):
            raise memory_changed()
        if not records:
            return cls()
        with db.transaction() as conn:
            for record in records[:6]:
                if not isinstance(record, dict):
                    raise memory_changed()
                identifier, revision = record.get("id"), record.get("revision")
                if not isinstance(identifier, str) or type(revision) is not int:
                    raise memory_changed()
                row = cls._eligible(conn, identifier)
                if (not row or row["revision"] != revision or
                        (topic_id and row["topic_id"] not in (None, topic_id))):
                    raise memory_changed()
                if identifier in seen:
                    continue
                # The prompt comes from the checked canonical row, not opaque
                # derivative text or a second retrieval with different pins.
                line = f"[{identifier} r{revision}] {row['text']}\n"
                if size + len(line) > 3000:
                    continue
                seen.add(identifier)
                size += len(line)
                lines.append(line)
                pins.append((identifier, revision, row["text"], row["scope"], row["topic_id"]))
        return cls(tuple(pins), "".join(lines))

    @staticmethod
    def _eligible(conn, identifier):
        row = conn.execute(
            "SELECT id,revision,text,scope,topic_id FROM memory_facts f WHERE id=? "
            "AND NOT EXISTS (SELECT 1 FROM deletion_ledger "
            "WHERE entity_type='memory_fact' AND entity_id=f.id)", (identifier,)).fetchone()
        return row if row and row["scope"] in ELIGIBLE_SCOPES else None

    def check(self, db, *, conn=None):
        if not self.pins:
            return
        if conn is None:
            with db.transaction() as current:
                self.check(db, conn=current)
            return
        for pin in self.pins:
            row = self._eligible(conn, pin[0])
            if row is None or tuple(row) != pin:
                raise memory_changed()


async def guarded_stream(provider, messages, *, memory_context, db, **kwargs):
    """Observe runtime compaction boundaries hidden by its text-only stream()."""
    memory_context.check(db)
    events = getattr(provider, "events", None)
    use_events = bool(memory_context.pins) and callable(events)
    stream = (events(messages, **kwargs) if use_events else provider.stream(messages, **kwargs))
    try:
        while True:
            # Also check after the consumer resumes a previously yielded delta.
            memory_context.check(db)
            try:
                item = await anext(stream)
            except StopAsyncIteration:
                break
            if use_events:
                if item.type == "cancelled":
                    raise asyncio.CancelledError()
                if item.type == "error":
                    raise ApiError(item.payload["code"], item.payload["message"],
                        item.payload.get("status", 503), item.payload["retryable"])
            memory_context.check(db)
            if not use_events:
                yield item
            elif item.type == "delta":
                yield item.payload["text"]
            # Runtime yields started before planning/dispatch and progress both
            # before and after compaction, before advancing to primary transport.
    finally:
        if hasattr(stream, "aclose"):
            with suppress(Exception):
                await stream.aclose()
