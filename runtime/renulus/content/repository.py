# SPDX-License-Identifier: MIT
"""Canonical pack installation, activation, pinned versions and withdrawals."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
import re
from pathlib import Path

from .programmes import mapped_question_pins, programme_metadata
from .validation import MAX_FILE_BYTES, PackValidationError, canonical_json, digest, validate_pack


class ContentConflict(ValueError):
    pass


class ContentUnavailable(LookupError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class ContentRepository:
    """Uses the shared Database; the integrator applies schema.sql first.

    Only authored pack snapshots are written. Transient/saved user cases belong
    to M3, never this repository. get_question_version is a trusted backend API:
    M4 controls answer commitment/exposure before returning feedback.
    """

    def __init__(self, db, pack_root: str | Path):
        self.db = db
        self.pack_root = Path(pack_root).resolve()

    def active_manifest(self) -> dict | None:
        with closing(self.db.connect()) as conn:
            return self._manifest_from(conn)

    @staticmethod
    def _manifest_from(conn):
        row = conn.execute(
            "SELECT p.manifest_json FROM content_active_pack a JOIN content_packs p "
            "ON p.pack_id=a.pack_id AND p.version=a.pack_version WHERE a.slot=1"
        ).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def _store(conn, table, id_column, item, *, family=False):
        row = conn.execute(f"SELECT sha256 FROM {table} WHERE {id_column}=? AND version=?",
                           (item["id"], item["version"])).fetchone()
        body_hash = digest(item)
        if row:
            if row[0] != body_hash:
                raise ContentConflict(f"Immutable version changed: {item['id']} v{item['version']}")
            return
        if family:
            previous = conn.execute(
                "SELECT family_id,body_json,version FROM content_question_versions WHERE question_id=? "
                "ORDER BY version DESC LIMIT 1",
                (item["id"],)).fetchone()
            if previous and previous[0] != item["family_id"]:
                raise ContentConflict(f"Question family cannot change: {item['id']}")
            if previous:
                old = json.loads(previous[1])
                if item["version"] <= previous[2]:
                    raise ContentConflict("A newly published question must advance its version")
                if (old["answer"] != item["answer"] or old["options"] != item["options"]) and "correction" not in item:
                    raise ContentConflict("Changing a published key or choices requires a correction and withdrawal")
            conn.execute(f"INSERT INTO {table} ({id_column},version,family_id,body_json,sha256) "
                         "VALUES(?,?,?,?,?)", (item["id"], item["version"], item["family_id"],
                         canonical_json(item), body_hash))
        else:
            conn.execute(f"INSERT INTO {table} ({id_column},version,body_json,sha256) VALUES(?,?,?,?)",
                         (item["id"], item["version"], canonical_json(item), body_hash))

    @staticmethod
    def _withdraw_question(conn, question_id, version, reason, replacement_version=None):
        if not isinstance(reason, str) or not reason.strip():
            raise ContentConflict("Withdrawal requires a nonempty reason")
        previous = conn.execute(
            "SELECT reason,replacement_version FROM content_question_withdrawals "
            "WHERE question_id=? AND version=?", (question_id, version)).fetchone()
        if previous:
            if previous[0] != reason or previous[1] != replacement_version:
                raise ContentConflict("Withdrawal already recorded with different details")
            return
        exists = conn.execute(
            "SELECT 1 FROM content_question_versions WHERE question_id=? AND version=?",
            (question_id, version)).fetchone()
        if not exists:
            raise ContentUnavailable(f"Unknown pinned question: {question_id} v{version}")
        if replacement_version is not None:
            replacement = conn.execute(
                "SELECT 1 FROM content_question_versions WHERE question_id=? AND version=?",
                (question_id, replacement_version)).fetchone()
            withdrawn = conn.execute(
                "SELECT 1 FROM content_question_withdrawals WHERE question_id=? AND version=?",
                (question_id, replacement_version)).fetchone()
            if replacement_version <= version or not replacement or withdrawn:
                raise ContentConflict("Replacement must be an available later version of the same item")
        conn.execute("INSERT INTO content_question_withdrawals VALUES(?,?,?,?,?)",
                     (question_id, version, reason, _now(), replacement_version))

    def install_pack(self, path: str | Path) -> dict:
        chosen = Path(path)
        if not chosen.is_absolute():
            chosen = self.pack_root / chosen
        pack = validate_pack(chosen)
        with self.db.transaction() as conn:
            return self._install(conn, pack)

    def install_bundled_release(self, path: str | Path) -> dict:
        """Install required immutable predecessors and the release atomically.

        Only bundled published packs in the same lineage may supply a missing
        withdrawn version. Arbitrary imports retain the strict predecessor rule.
        """
        candidate = Path(path).resolve()
        if not candidate.is_relative_to(self.pack_root):
            raise ContentConflict("Bundled release must stay within the app pack directory")
        pack = validate_pack(candidate)
        lineage = (self.pack_root / pack.manifest["id"]).resolve()
        if (candidate.parent != lineage or candidate.name != pack.manifest["version"]
                or not lineage.is_relative_to(self.pack_root)):
            raise ContentConflict("Bundled release must match its pack lineage")
        with self.db.transaction() as conn:
            self._install_predecessors(conn, candidate, pack)
            return self._install(conn, pack)

    def _install_predecessors(self, conn, path, pack):
        required = {(item["question_id"], item["version"])
                    for item in pack.manifest["withdrawals"]}
        missing = {pin for pin in required if not conn.execute(
            "SELECT 1 FROM content_question_versions WHERE question_id=? AND version=?",
            pin).fetchone()}
        if not missing:
            return
        version = lambda value: tuple(int(part) for part in value.split("."))
        prior = sorted((item for item in path.parent.iterdir()
                        if item.is_dir() and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", item.name)
                        and version(item.name) < version(pack.manifest["version"])),
                       key=lambda item: version(item.name), reverse=True)
        for item in prior:
            resolved = item.resolve()
            if resolved.parent != path.parent:
                raise ContentConflict("Bundled predecessor must stay within its pack lineage")
            metadata = resolved / "manifest.json"
            if not metadata.is_file():
                continue
            if metadata.stat().st_size > MAX_FILE_BYTES:
                raise PackValidationError("Bundled predecessor manifest exceeds the supported size")
            header = json.loads(metadata.read_text(encoding="utf-8"))
            if isinstance(header, dict) and header.get("state") == "draft":
                continue
            # Validate immutable bytes before installing a published dependency.
            previous = validate_pack(resolved)
            if (previous.manifest["id"] != pack.manifest["id"]
                    or previous.manifest["version"] != item.name):
                raise ContentConflict("Bundled predecessor identity must match its directory")
            pins = {(q["id"], q["version"]) for q in previous.bundle["questions"]}
            if not missing.intersection(pins):
                continue
            self._install_predecessors(conn, resolved, previous)
            self._install(conn, previous)
            missing = {pin for pin in missing if not conn.execute(
                "SELECT 1 FROM content_question_versions WHERE question_id=? AND version=?",
                pin).fetchone()}
            if not missing:
                return
        raise ContentConflict("Install the predecessor before its correction; bundled predecessor is missing")

    def _install(self, conn, pack) -> dict:
        bundle, manifest = pack.bundle, pack.manifest
        pack_id, version = manifest["id"], manifest["version"]
        previous = conn.execute(
            "SELECT sha256 FROM content_packs WHERE pack_id=? AND version=?",
            (pack_id, version)).fetchone()
        if previous and previous[0] != pack.sha256:
            raise ContentConflict(f"Immutable pack changed: {pack_id} v{version}")
        if conn.execute("SELECT 1 FROM content_pack_withdrawals WHERE pack_id=? AND version=?",
                        (pack_id, version)).fetchone():
            raise ContentConflict("Withdrawn packs cannot be reactivated")
        if not previous:
            conn.execute("INSERT INTO content_packs VALUES(?,?,?,?,?)",
                         (pack_id, version, canonical_json(manifest), pack.sha256, _now()))
            definitions = (
                ("topics", "content_topics", "topic_id", "topic_version"),
                ("cases", "content_case_versions", "case_id", "case_version"),
                ("questions", "content_question_versions", "question_id", "question_version"),
            )
            for name, table, id_column, version_column in definitions:
                for item in bundle[name]:
                    if name in ("cases", "questions"):
                        cited = {s["source_id"] for s in item["sources"]}
                        if name == "cases":
                            cited.update(s["source_id"] for stage in item["stages"] for s in stage["sources"])
                        # Preserve edition/URL/check evidence inside the canonical
                        # immutable snapshot; future pack files may disappear.
                        item = {**item, "source_records": [s for s in bundle["sources"] if s["id"] in cited]}
                    self._store(conn, table, id_column, item, family=(name == "questions"))
                    if name == "questions" and "correction" in item:
                        correction = item["correction"]
                        if not conn.execute(
                            "SELECT 1 FROM content_question_versions WHERE question_id=? AND version=?",
                            (item["id"], correction["previous_version"])).fetchone():
                            raise ContentConflict("Install the predecessor before its correction")
                        if not any(w["question_id"] == item["id"]
                                   and w["version"] == correction["previous_version"]
                                   and w.get("replacement_version") == item["version"]
                                   for w in manifest["withdrawals"]):
                            raise ContentConflict("A key correction must withdraw the previous version")
                    conn.execute(f"INSERT INTO content_pack_{name} "
                                 f"(pack_id,pack_version,{id_column},{version_column}) VALUES(?,?,?,?)",
                                 (pack_id, version, item["id"], item["version"]))
            for withdrawal in manifest["withdrawals"]:
                self._withdraw_question(conn, **withdrawal)
        # Reject an old selected version after any global withdrawal, including on reinstallation.
        if conn.execute(
            "SELECT 1 FROM content_pack_questions s JOIN content_question_withdrawals w "
            "ON w.question_id=s.question_id AND w.version=s.question_version "
            "WHERE s.pack_id=? AND s.pack_version=?", (pack_id, version)).fetchone():
            raise ContentConflict("Pack selects withdrawn question versions")
        conn.execute("INSERT INTO content_active_pack VALUES(1,?,?) ON CONFLICT(slot) DO UPDATE "
                     "SET pack_id=excluded.pack_id,pack_version=excluded.pack_version",
                     (pack_id, version))
        return {"id": pack_id, "version": version, "sha256": pack.sha256,
                "installed": previous is None, "active": True,
                "questions": len(bundle["questions"]), "cases": len(bundle["cases"])}

    def _active_rows(self, name, connection=None):
        if connection is None:
            with closing(self.db.connect()) as conn:
                return self._active_rows(name, conn)
        table, id_column, version_column = {
            "topics": ("content_topics", "topic_id", "topic_version"),
            "cases": ("content_case_versions", "case_id", "case_version"),
            "questions": ("content_question_versions", "question_id", "question_version"),
        }[name]
        rows = connection.execute(
            f"SELECT v.body_json FROM content_active_pack a JOIN content_pack_{name} s "
            f"ON s.pack_id=a.pack_id AND s.pack_version=a.pack_version JOIN {table} v "
            f"ON v.{id_column}=s.{id_column} AND v.version=s.{version_column} WHERE a.slot=1 "
            + ("AND NOT EXISTS (SELECT 1 FROM content_question_withdrawals w WHERE "
               "w.question_id=v.question_id AND w.version=v.version) " if name == "questions" else "")
            + f"ORDER BY v.{id_column}").fetchall()
        return [json.loads(r[0]) for r in rows]

    def list_topics(self) -> list[dict]:
        return [{**topic, "title": topic["label"], "name": topic["label"]}
                for topic in self._active_rows("topics")]

    def list_sources(self) -> list[dict]:
        """Active cited source metadata only; no question text or answer keys."""
        sources = {}
        for item in [*self._active_rows("cases"), *self._active_rows("questions")]:
            for source in item["source_records"]:
                sources[source["id"]] = source
        return [sources[id] for id in sorted(sources)]

    def get_source(self, source_id: str) -> dict:
        for source in self.list_sources():
            if source["id"] == source_id:
                return source
        raise ContentUnavailable(f"No active source metadata: {source_id}")

    def references_for_source(self, source_id: str, *, include_historical=False) -> list[dict]:
        """Update impact: exact citation ID or SOURCES register family ID, no keys."""
        if include_historical:
            with closing(self.db.connect()) as conn:
                cases = [json.loads(r[0]) for r in conn.execute("SELECT body_json FROM content_case_versions")]
                questions = [json.loads(r[0]) for r in conn.execute("SELECT body_json FROM content_question_versions")]
        else:
            cases, questions = self._active_rows("cases"), self._active_rows("questions")
        result = []
        for kind, items in (("case", cases), ("question", questions)):
            for item in items:
                matching = {s["id"]: s for s in item["source_records"]
                            if source_id in (s["id"], s["register_id"])}
                for cited_id, source in matching.items():
                    result.append({"kind": kind, "id": item["id"], "version": item["version"],
                                   "topic_id": item["topic_id"], "source_id": cited_id,
                                   "register_id": source["register_id"],
                                   "locators": sorted({s["locator"] for s in item["sources"]
                                                       if s["source_id"] == cited_id}),
                                   "review_status": item["review"]["status"]})
        return sorted(result, key=lambda r: (r["kind"], r["id"], r["version"], r["source_id"]))

    def list_cases(self) -> list[dict]:
        return self._active_rows("cases")

    def get_case(self, id: str) -> dict:
        for case in self.list_cases():
            if case["id"] == id:
                return case
        raise ContentUnavailable(f"No active teaching case: {id}")

    def list_questions(self, topic_id: str | None = None) -> list[dict]:
        # Reviewed assessment is the default pool. Generated practice and held-out
        # evaluation have their own owners; neither enters scored-bank selection.
        return [q for q in self._active_rows("questions")
                if q["usage"] == "assessment_reserved"
                and (topic_id is None or q["topic_id"] == topic_id)]

    def get_question_version(self, id: str, version: int) -> dict:
        with closing(self.db.connect()) as conn:
            row = conn.execute(
                "SELECT q.body_json,w.reason,w.replacement_version FROM content_question_versions q "
                "LEFT JOIN content_question_withdrawals w ON w.question_id=q.question_id "
                "AND w.version=q.version WHERE q.question_id=? AND q.version=?", (id, version)).fetchone()
            if not row:
                raise ContentUnavailable(f"Unknown pinned question: {id} v{version}")
            question = json.loads(row[0])
            question["withdrawn"] = row[1] is not None
            question["withdrawal"] = ({"reason": row[1], "replacement_version": row[2]}
                                      if row[1] is not None else None)
            active = conn.execute(
                "SELECT s.question_version FROM content_pack_questions s JOIN content_active_pack a "
                "ON a.pack_id=s.pack_id AND a.pack_version=s.pack_version "
                "WHERE s.question_id=?", (id,)).fetchone()
            question["current_version"] = active[0] if active else None
            question["question_id"] = question["id"]
            question["correct_option_ids"] = [question["answer"]]
            question["explanation"] = question["rationale"]
            return question

    def list_question_summaries(self, topic_id=None, domain=None, track=None) -> list[dict]:
        """Key-free selection metadata. Domain currently means a stable topic ID."""
        if track not in (None, "general_nephrology", "esen_eph"):
            return []
        if topic_id is not None and domain is not None and topic_id != domain:
            return []
        # Manifest and active pins must describe one SQLite snapshot even if a
        # concurrent pack activation/withdrawal changes the active selection.
        with closing(self.db.connect()) as conn:
            conn.execute("BEGIN")
            pins = mapped_question_pins(self._manifest_from(conn), track) if track == "esen_eph" else None
            questions = self._active_rows("questions", conn)
        return [{k: q[k] for k in ("id", "version", "family_id", "family_version",
                                  "key_version", "topic_id", "objective_ids",
                                  "difficulty", "usage", "review")}
                for q in questions if q["usage"] == "assessment_reserved"
                and (topic_id or domain) in (None, q["topic_id"])
                and (pins is None or (q["id"], q["version"]) in pins)]

    def track_metadata(self) -> list[dict]:
        """Public coverage; exact active versions, no stems/options/keys or attempts."""
        with closing(self.db.connect()) as conn:
            conn.execute("BEGIN")
            return programme_metadata(self._manifest_from(conn), self._active_rows("topics", conn),
                                      self._active_rows("cases", conn),
                                      [q for q in self._active_rows("questions", conn)
                                       if q["usage"] == "assessment_reserved"])

    def withdraw_question(self, id: str, version: int, reason: str, replacement_version=None):
        with self.db.transaction() as conn:
            self._withdraw_question(conn, id, version, reason, replacement_version)
        return self.get_question_version(id, version)

    def withdraw_pack(self, id: str, version: str, reason: str):
        if not isinstance(reason, str) or not reason.strip():
            raise ContentConflict("Withdrawal requires a nonempty reason")
        with self.db.transaction() as conn:
            if not conn.execute("SELECT 1 FROM content_packs WHERE pack_id=? AND version=?",
                                (id, version)).fetchone():
                raise ContentUnavailable("Unknown pack version")
            previous = conn.execute("SELECT reason FROM content_pack_withdrawals WHERE pack_id=? AND version=?",
                                    (id, version)).fetchone()
            if previous and previous[0] != reason:
                raise ContentConflict("Pack withdrawal already recorded with another reason")
            if not previous:
                conn.execute("INSERT INTO content_pack_withdrawals VALUES(?,?,?,?)",
                             (id, version, reason, _now()))
            conn.execute("DELETE FROM content_active_pack WHERE pack_id=? AND pack_version=?", (id, version))
        return {"id": id, "version": version, "withdrawn": True, "reason": reason}

    def teaching_material(self) -> list[dict]:
        """The only teaching export: objectives and authored cases, never questions."""
        return [{"kind": "topic", **t} for t in self.list_topics()] + [
            {"kind": "case", **c} for c in self.list_cases()]
