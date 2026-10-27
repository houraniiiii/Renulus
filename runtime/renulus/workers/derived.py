"""Small reuse adapter for host-owned derived namespaces, never canonical stores.

The host supplies the complete deletion frontier at launch and immutable plans at
admission. A staged row is only a candidate; accepted canonical references on each
read are the eligibility gate. All native handles close before their exact lease.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
import time

from renulus.worker_contracts import LibraryBatch, MemoryBatch
from .artifacts import Refused


class UnsettledEngine(Exception):
    """An incomplete native constructor cannot prove resource settlement."""


def _directory(value):
    path = Path(value)
    if not path.is_absolute():
        raise Refused("artifact_denied")
    for item in (path, *path.parents):
        if item.is_symlink() or item.is_junction():
            raise Refused("artifact_denied")
    return path


class DerivedEngines:
    def __init__(self, config, engines):
        self.config, self.engines = config, engines
        self.library_deleted = set(config.derived.library_tombstones) if config.derived else set()
        self.memory_deleted = set(config.derived.memory_tombstones) if config.derived else set()
        self.unsettled = []

    def _root(self):
        if self.config.derived is None or self.config.helpers is None:
            raise Refused("helper_unavailable")
        # Temporary Lance is deliberately unavailable: LanceDB's selected adapter
        # is disk-backed. Mem0 extraction below uses a fresh RAM graph only.
        root = _directory(self.config.derived.root)
        for protected in self.config.helpers.model_dump().values():
            protected = _directory(protected)
            if root.is_relative_to(protected) or protected.is_relative_to(root):
                raise Refused("artifact_denied")
        return root / self.config.derived.namespace

    @staticmethod
    def _close(close):
        # A failed native close is still ownership, including after Stop. Retain
        # this task/thread and exact path pin; the host may resolve process death
        # as uncertain, never infer settlement from a timeout.
        while True:
            try:
                close()
                return
            except Exception:
                time.sleep(0.05)

    @contextmanager
    def _library(self):
        if self.config.retention != "saved":
            raise Refused("artifact_denied")
        self.engines._load()
        self.engines._versions({"lancedb": "0.39.0"})
        from renulus.knowledge.engines import LanceIndex
        index = LanceIndex(self._root() / "library", dimensions=384)
        try:
            # Apply tombstones before any query, staging or readiness output.
            for revision in self.library_deleted:
                index.remove(revision)
            yield index
        finally:
            self._close(index.close)

    def _memory_services(self):
        self.engines._load()
        self.engines._versions({"mem0ai": "2.2.1", "qdrant-client": "1.19.1", "fastembed": "0.8.1"})
        base = self._root()
        helpers = self.engines._assets.services.registry["helpers"]
        # Mem0Index needs these path values and HelperAssets only. No Services,
        # repositories, provider registry or Database is constructed.
        paths = SimpleNamespace(helpers=helpers.paths.helpers, cache=helpers.paths.cache,
            source_root=helpers.paths.source_root, indexes=base / "indexes",
            owned=lambda relative: helpers.paths.cache / "memory-bootstrap")
        return SimpleNamespace(paths=paths, registry=MappingProxyType({"helpers": helpers}))

    @contextmanager
    def _memory(self, *, transient=False):
        if self.config.retention != "saved" and not transient:
            raise Refused("artifact_denied")
        services = self._memory_services()
        from renulus.memory.engine import Mem0Index, embedding_config
        from renulus.memory.providers import OfflineEmbedding
        from renulus.knowledge.ownership import NativeOwnership
        path = services.paths.indexes / "learner-memory" / ("capture" if transient else "facts")
        embedding = OfflineEmbedding(embedding_config(services))
        owner, index = None, None
        if not transient:
            owner = NativeOwnership(path.parent / (path.name + ".native-owner"))
            owner.acquire_for_path(path)
        try:
            # Keep even a partially initialized object reachable. Mem0 may have
            # opened native resources before its constructor raises; no successful
            # return means we cannot assert those resources closed.
            candidate = Mem0Index.__new__(Mem0Index)
            try:
                candidate.__init__(services, path, embedding, transient=transient)
            except Exception:
                self.unsettled.append((candidate, owner))
                owner = None  # Retain exact guard until actual process death.
                raise UnsettledEngine() from None
            index = candidate
            if not transient:
                self._purge(index, self.memory_deleted)
            yield index
        finally:
            if index is not None:
                def close():
                    # Hermes close suppresses exceptions; explicitly close the
                    # actual Qdrant client first so lease release cannot mask one.
                    index.memory.vector_store.client.close()
                    index.close()
                self._close(close)
            if owner is not None:
                self._close(owner.close)

    @staticmethod
    def _rows(index, ids):
        if not ids:
            return
        from qdrant_client import models
        selector = models.Filter(must=[models.FieldCondition(key="canonical_id",
            match=models.MatchAny(any=list(ids)))])
        cursor = None
        while True:
            rows, cursor = index.memory.vector_store.client.scroll(
                collection_name=index.collection, scroll_filter=selector,
                limit=128, offset=cursor, with_payload=True, with_vectors=False)
            yield from rows
            if cursor is None:
                break

    def _purge(self, index, ids):
        count = 0
        # Restart each bounded page after deletion. No unbounded payload list and
        # no cursor may skip records just removed from the local collection.
        while True:
            rows = []
            for row in self._rows(index, ids):
                rows.append(row)
                if len(rows) == 128:
                    break
            if not rows:
                break
            for row in rows:
                index.backend.delete(str(row.id))
                count += 1
        index.purge_history()
        return count

    def execute(self, command, body, current, capture=None):
        i, name = command.input, command.command
        if name.startswith("library."):
            with self._library() as index:
                if name == "library.query":
                    allowed = [r for r in i.allowed_revision_ids if r not in self.library_deleted]
                    rows = index.search(i.query, self.engines.embed([i.query], query=True)["vectors"][0],
                        allowed, i.limit) if allowed else []
                    return {"tag": "library_candidates", "rows": [
                        {key: row[key] for key in ("passage_id", "revision_id", "document_id", "text")}
                        for row in rows]}
                if name == "library.stage":
                    batch = LibraryBatch.model_validate_json(body)
                    if i.revision_id in self.library_deleted or not current():
                        raise Refused("stale_revision")
                    ids = [p.passage_id for p in batch.passages]
                    if len(set(ids)) != len(ids):
                        raise Refused("artifact_invalid")
                    from tokenizers import Tokenizer
                    tokenizer = Tokenizer.from_file(str(self.engines._assets.config("fastembed")["tokenizer_path"]))
                    tokenizer.no_truncation()
                    tokenizer.no_padding()
                    if any(len(tokenizer.encode(p.text).ids) > 480 for p in batch.passages):
                        raise Refused("artifact_limit")
                    rows = [dict(passage_id=p.passage_id, revision_id=i.revision_id,
                        document_id=i.document_id, text=p.text) for p in batch.passages]
                    # A revision is immutable. Replay can reuse identical staging,
                    # never append duplicates or replace another revision's bytes.
                    where = "revision_id = '" + i.revision_id.replace("'", "''") + "'"
                    table = index._open()
                    existing = table.search().where(where).select(list(rows[0])).limit(12001).to_list()
                    if existing:
                        if sorted(existing, key=lambda r: r["passage_id"]) != sorted(rows, key=lambda r: r["passage_id"]):
                            raise Refused("stale_revision")
                    else:
                        vectors = self.engines.embed([p.text for p in batch.passages], query=False)["vectors"]
                        if not current():
                            raise Refused("stale_revision")
                        index.stage([{**r, "vector": v} for r, v in zip(rows, vectors, strict=True)])
                    index.build_fts()
                    return {"tag": "library_staged", "document_id": i.document_id,
                        "revision_id": i.revision_id, "passage_ids": ids,
                        "input_sha256": hashlib.sha256(body).hexdigest(), "eligible": False}
                if len(self.library_deleted | set(i.revision_ids)) > 4096:
                    raise Refused("artifact_limit")
                self.library_deleted.update(i.revision_ids)
                for revision in i.revision_ids:
                    index.remove(revision)
                if name == "library.maintain" and i.optimize:
                    index.optimize()
                return {"tag": "library_maintained", "removed_revision_ids": i.revision_ids,
                    "tombstones_applied": True}
        if name == "memory.extract":
            if hashlib.sha256(body).hexdigest() != i.capture_plan.source_sha256:
                raise Refused("digest_mismatch")
            text = body.decode("utf-8")
            if len(text) > 32768 or not text.strip() or not current():
                raise Refused("artifact_limit")
            with self._memory(transient=True) as index:
                facts = index.extract(text, capture.binding())
            return {"tag": "memory_extracted", "facts": facts,
                "capture_plan": i.capture_plan.model_dump(), "eligible": False}
        with self._memory() as index:
            if name == "memory.recall":
                accepted = {(r.engine_id, r.canonical_id, r.canonical_revision) for r in i.accepted
                    if r.canonical_id not in self.memory_deleted}
                if not accepted:
                    rows = []
                else:
                    # Narrow the actual Mem0/Hermes search before top-k, then bind
                    # exact engine ID/revision again before returning text.
                    filters = {"user_id": index.user_id, "agent_id": index.agent_id, "OR": [
                        {"canonical_id": cid, "canonical_revision": rev} for _, cid, rev in accepted]}
                    candidates = index.backend.search(i.query, filters=filters, top_k=i.limit, rerank=False)
                    rows = []
                    for row in candidates:
                        meta = row.get("metadata", {})
                        binding = (row["id"], meta.get("canonical_id"), meta.get("canonical_revision"))
                        if binding in accepted:
                            rows.append(dict(engine_id=binding[0], canonical_id=binding[1],
                                canonical_revision=binding[2], text=row["memory"]))
                return {"tag": "memory_candidates", "rows": rows}
            if name == "memory.purge":
                if len(self.memory_deleted | set(i.canonical_ids)) > 4096:
                    raise Refused("artifact_limit")
                self.memory_deleted.update(i.canonical_ids)
                count = self._purge(index, i.canonical_ids)
                return {"tag": "memory_purged", "removed": count, "tombstones_applied": True}
            batch = MemoryBatch.model_validate_json(body)
            ids = [record.id for record in batch.records]
            if len(set(ids)) != len(ids) or any(cid in self.memory_deleted for cid in ids):
                raise Refused("stale_revision")
            refs = []
            for record in batch.records:
                if not current():
                    raise Refused("stale_revision")
                existing = None
                for row in self._rows(index, [record.id]):
                    if row.payload.get("canonical_revision") == record.revision:
                        if (row.payload.get("data") != record.text or any(
                                row.payload.get(key) != getattr(record, key)
                                for key in ("scope", "topic_id", "kind"))):
                            raise Refused("stale_revision")
                        existing = str(row.id)
                refs.append(dict(canonical_id=record.id, canonical_revision=record.revision,
                    engine_id=existing or index.add(record.model_dump())))
            index.purge_history()
            return {"tag": "memory_reconciled", "references": refs, "eligible": False}
