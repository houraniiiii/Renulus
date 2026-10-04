# SPDX-License-Identifier: MIT
"""Canonical pack installation, activation, pinned versions and withdrawals."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path

from .validation import canonical_json, digest, validate_pack


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
                "SELECT family_id FROM content_question_versions WHERE question_id=? LIMIT 1",
                (item["id"],)).fetchone()
            if previous and previous[0] != item["family_id"]:
                raise ContentConflict(f"Question family cannot change: {item['id']}")
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
        bundle, manifest = pack.bundle, pack.manifest
        pack_id, version = manifest["id"], manifest["version"]
        with self.db.transaction() as conn:
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

    def _active_rows(self, name):
        table, id_column, version_column = {
            "topics": ("content_topics", "topic_id", "topic_version"),
            "cases": ("content_case_versions", "case_id", "case_version"),
            "questions": ("content_question_versions", "question_id", "question_version"),
        }[name]
        with closing(self.db.connect()) as conn:
            rows = conn.execute(
                f"SELECT v.body_json FROM content_active_pack a JOIN content_pack_{name} s "
                f"ON s.pack_id=a.pack_id AND s.pack_version=a.pack_version JOIN {table} v "
                f"ON v.{id_column}=s.{id_column} AND v.version=s.{version_column} WHERE a.slot=1 "
                + ("AND NOT EXISTS (SELECT 1 FROM content_question_withdrawals w WHERE "
                   "w.question_id=v.question_id AND w.version=v.version) " if name == "questions" else "")
                + f"ORDER BY v.{id_column}").fetchall()
            return [json.loads(r[0]) for r in rows]

    def list_topics(self) -> list[dict]:
        return self._active_rows("topics")

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
        if track not in (None, "general_nephrology"):
            return []
        if topic_id is not None and domain is not None and topic_id != domain:
            return []
        return [{k: q[k] for k in ("id", "version", "family_id", "family_version",
                                  "key_version", "topic_id", "objective_ids",
                                  "difficulty", "usage", "review")}
                for q in self.list_questions(topic_id or domain)]

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
