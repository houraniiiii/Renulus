"""Reference-only completed-answer support using the existing Design C types."""
import inspect
import json
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from renulus.contracts import ApiError, ContextScope
from renulus.design_c_contracts import Dependency, EligibleInput, Identity, canonical_digest
from renulus.storage import utc_now

from .study_answers import answer_reference_in


INELIGIBLE_LINEAGE_CODES = frozenset({
    "memory_dependency_revoked", "memory_lineage_unknown", "memory_dependency_unknown",
    "memory_project_scope", "memory_lineage_cycle", "memory_lineage_conflict",
    "memory_capture_suppressed", "memory_scope_excluded", "memory_answer_unavailable",
    "memory_answer_reference", "memory_evidence_deleted", "memory_answer_version",
})
# Local adapters use these codes only for known stale or unknown support.
# Infrastructure failures and support-budget errors must propagate unchanged.


class AnswerInputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: int = Field(default=1, ge=1, le=1, strict=True)
    inputs: tuple[EligibleInput, ...] = Field(default=(), max_length=100)
    dependencies: tuple[Dependency, ...] = Field(default=(), max_length=100)


class LocalDependencyResolver(Protocol):
    def resolve_dependency_in(self, conn, dependency: Dependency, *,
                              project_id: str | None, for_support: bool) -> AnswerInputs:
        """Validate local eligibility and return immutable typed ancestors.

        Never perform IPC, await work or resolve answer bytes here. Empty inputs
        attest an independently rooted eligible revision, not unknown lineage.
        """
        ...


class AnswerLineage:
    def __init__(self, db, resolvers):
        self.db = db
        self.resolvers = resolvers

    def register_resolver(self, target_type, resolver: LocalDependencyResolver):
        Identity(type=target_type, id="resolver")
        if target_type in ("memory_revision", "learning_evidence"):
            raise ValueError("Memory and answer lineage have their canonical resolver already")
        if not callable(getattr(resolver, "resolve_dependency_in", None)) or inspect.iscoroutinefunction(resolver.resolve_dependency_in):
            raise ValueError("Dependency resolvers must synchronously validate local canonical records")
        self.resolvers[target_type] = resolver

    def resolve_in(self, conn, dependency, *, project_id=None, for_support=False):
        resolver = self.resolvers.get(dependency.target.type)
        if resolver is None:
            raise ApiError("memory_dependency_unknown", "This dependency has no local eligibility resolver", 409)
        closure = resolver.resolve_dependency_in(conn, dependency, project_id=project_id, for_support=for_support)
        if inspect.isawaitable(closure):
            if inspect.iscoroutine(closure):
                closure.close()
            raise ApiError("memory_dependency_unknown", "Dependency validation must use local canonical receipts", 409)
        if not isinstance(closure, AnswerInputs):
            raise ApiError("memory_dependency_unknown", "Dependency validation needs a known typed closure", 409)
        return closure

    def expand_in(self, conn, manifest, *, project_id=None, seen=frozenset()):
        """Persist registered source/history/tool ancestors at publication."""
        if len(seen) >= 100:
            raise ApiError("memory_support_budget", "This support ancestry exceeds the publication budget", 409)
        inputs, dependencies = list(manifest.inputs), list(manifest.dependencies)
        for dependency in (*[item.dependency for item in manifest.inputs], *manifest.dependencies):
            if dependency.target.key in seen:
                raise ApiError("memory_lineage_cycle", "Support cannot contain a cycle", 409)
            if dependency.target.type in ("memory_revision", "learning_evidence"):
                continue
            closure = self.resolve_in(conn, dependency, project_id=project_id)
            expanded = self.expand_in(conn, closure, project_id=project_id, seen=seen | {dependency.target.key})
            inputs.extend(expanded.inputs)
            dependencies.extend(expanded.dependencies)
        inputs, dependencies = tuple(dict.fromkeys(inputs)), tuple(dict.fromkeys(dependencies))
        if len(inputs) > 100 or len(dependencies) > 100:
            raise ApiError("memory_support_budget", "This support closure exceeds the publication budget", 409)
        return AnswerInputs(inputs=inputs, dependencies=dependencies)

    @staticmethod
    def group_inputs_in(conn, group_id):
        return tuple(Dependency(target=Identity(type=row["target_type"], id=row["target_id"]),
            expected_revision=row["expected_revision"]) for row in conn.execute(
                "SELECT * FROM memory_support_inputs WHERE group_id=? ORDER BY target_type,target_id,expected_revision",
                (group_id,)))

    def support_groups_in(self, conn, manifest, *, seen=frozenset(), project_id=None):
        """Joint inputs multiply alternatives; echoes keep ancestor root pins."""
        if len(seen) >= 100:
            raise ApiError("memory_support_budget", "This support ancestry exceeds the capture budget", 409)
        groups = [()]
        for dependency in (*[item.dependency for item in manifest.inputs], *manifest.dependencies):
            target = dependency.target
            if target.key in seen:
                raise ApiError("memory_lineage_cycle", "Support cannot contain a cycle", 409)
            branches = [()]
            if target.type == "memory_revision":
                identifier = target.id.rpartition(":")[0]
                rows = conn.execute("SELECT group_id FROM memory_support_groups WHERE record_id=? AND state='active'",
                                    (identifier,)).fetchall()
                branches = [self.group_inputs_in(conn, row[0]) for row in rows] or [()]
            elif target.type == "learning_evidence":
                prior = self.check_in(conn, target.id, expected=dependency.expected_revision)
                branches = self.support_groups_in(conn, AnswerInputs.model_validate_json(prior["manifest_json"]),
                                                  seen=seen | {target.key}, project_id=project_id)
            else:
                closure = self.resolve_in(conn, dependency, project_id=project_id)
                branches = self.support_groups_in(conn, closure, seen=seen | {target.key}, project_id=project_id)
            groups = [(*group, dependency, *branch) for group in groups for branch in branches]
            if len(groups) > 100 or any(len(set(group)) > 100 for group in groups):
                raise ApiError("memory_support_budget", "This support closure needs fewer independent alternatives", 409)
        return groups

    def add_support_in(self, conn, record_id, source_key, *, manifest=None, project_id=None, kind="manual"):
        groups = self.support_groups_in(conn, manifest, project_id=project_id) if manifest is not None else [()]
        revision = conn.execute("SELECT revision FROM memory_facts WHERE id=?", (record_id,)).fetchone()[0]
        for inputs in groups:
            # Recapturing an echo of this exact record never creates new support.
            if any(d.target.type == "memory_revision" and d.target.id.rpartition(":")[0] == record_id for d in inputs):
                continue
            unique = {canonical_digest(d.model_dump(mode="json")): d for d in inputs}
            inputs = tuple(unique[key] for key in sorted(unique))
            group_id = "support:" + canonical_digest({"record": record_id, "revision": revision, "source": source_key,
                "inputs": [d.model_dump(mode="json") for d in inputs], "project_id": project_id})
            conn.execute("INSERT OR IGNORE INTO memory_support_groups VALUES(?,?,?,?,?,?)",
                         (group_id, record_id, source_key, kind, "active", project_id))
            conn.executemany("INSERT OR IGNORE INTO memory_support_inputs VALUES(?,?,?,?)",
                [(group_id, d.target.type, d.target.id, d.expected_revision) for d in inputs])

    def check_group_in(self, conn, row, *, seen=frozenset()):
        self.check_inputs_in(conn, AnswerInputs(dependencies=self.group_inputs_in(conn, row["group_id"])),
                             project_id=row["project_id"], seen=seen, for_support=True)
        if row["support_kind"] == "generated":
            self.check_in(conn, row["source_key"][len("evidence:"):], seen=seen, for_support=True)

    def revoke_in(self, conn, suppress):
        """Revocation is terminal; surviving independent groups preserve a fact."""
        changed = True
        removed = []
        while changed:
            changed = False
            for row in conn.execute("SELECT * FROM memory_answer_lineage WHERE state='active'").fetchall():
                try:
                    self.check_in(conn, row["evidence_id"], for_support=True)
                except ApiError as error:
                    if error.code not in INELIGIBLE_LINEAGE_CODES:
                        raise
                    conn.execute("UPDATE memory_answer_lineage SET state='revoked' WHERE evidence_id=?", (row["evidence_id"],))
                    conn.execute("INSERT OR IGNORE INTO memory_suppression VALUES(?,?)",
                                 ("evidence:" + row["evidence_id"], utc_now()))
                    conn.execute("UPDATE memory_jobs SET state='cancelled',error_code='memory_dependency_revoked',updated_at=? "
                        "WHERE evidence_id=? AND state IN ('queued','running','failed')", (utc_now(), row["evidence_id"]))
                    changed = True
            for row in conn.execute("SELECT * FROM memory_support_groups WHERE state='active'").fetchall():
                try:
                    self.check_group_in(conn, row)
                except ApiError as error:
                    if error.code not in INELIGIBLE_LINEAGE_CODES:
                        raise
                    conn.execute("UPDATE memory_support_groups SET state='revoked' WHERE group_id=?", (row["group_id"],))
                    changed = True
            rows = conn.execute("SELECT f.id FROM memory_facts f WHERE "
                "EXISTS (SELECT 1 FROM memory_support_groups g WHERE g.record_id=f.id) AND "
                "NOT EXISTS (SELECT 1 FROM memory_support_groups g WHERE g.record_id=f.id AND g.state='active')").fetchall()
            for row in rows:
                suppress(conn, row["id"])
                self.db.mark_deleted("memory_fact", row["id"], conn)
                conn.execute("DELETE FROM memory_facts WHERE id=?", (row["id"],))
                removed.append(row["id"])
                changed = True
        return removed

    def publish_in(self, conn, evidence_id, *, inputs, dependencies=(), project_id=None):
        if project_id is not None:
            Identity(type="project", id=project_id)
        manifest = AnswerInputs(inputs=inputs, dependencies=dependencies)
        manifest = self.expand_in(conn, manifest, project_id=project_id)
        row = conn.execute("SELECT * FROM learning_evidence WHERE id=?", (evidence_id,)).fetchone()
        if row is None or row["kind"] != "study-answer":
            raise ApiError("memory_answer_unavailable", "Publish an eligible completed answer first", 409)
        payload = json.loads(row["payload_json"])
        if payload.get("scope", {}).get("kind") != "study":
            raise ApiError("memory_scope_excluded", "Answer capture requires ordinary Study scope", 409)
        self.check_inputs_in(conn, manifest, project_id=project_id)
        publication = canonical_digest({"evidence": dict(row), "manifest": manifest.model_dump(mode="json"),
                                        "project_id": project_id})
        prior = conn.execute("SELECT * FROM memory_answer_lineage WHERE evidence_id=?", (evidence_id,)).fetchone()
        if prior:
            if prior["state"] != "active" or prior["publication_digest"] != publication:
                raise ApiError("memory_lineage_conflict", "An answer already has immutable or revoked support", 409)
            return publication
        conn.execute("INSERT INTO memory_answer_lineage VALUES(?,?,?,?,?,?)",
                     (evidence_id, publication, manifest.model_dump_json(), "active", project_id, utc_now()))
        return publication

    def check_inputs_in(self, conn, manifest, *, seen=frozenset(), project_id=None, for_support=False):
        if len(seen) >= 100:
            raise ApiError("memory_support_budget", "This support ancestry exceeds the validation budget", 409)
        for dependency in (*[item.dependency for item in manifest.inputs], *manifest.dependencies):
            target = dependency.target
            if target.key in seen:
                raise ApiError("memory_lineage_cycle", "Support cannot contain a cycle", 409)
            if target.type == "memory_revision":
                identifier, separator, revision = target.id.rpartition(":")
                row = conn.execute("SELECT revision,(SELECT project_id FROM memory_support_groups g "
                    "WHERE g.record_id=memory_facts.id LIMIT 1) AS project_id FROM memory_facts WHERE id=? AND NOT EXISTS "
                    "(SELECT 1 FROM deletion_ledger WHERE entity_type='memory_fact' AND entity_id=?)",
                    (identifier, identifier)).fetchone()
                if (not separator or not row or str(row["revision"]) != revision or
                        revision != dependency.expected_revision):
                    raise ApiError("memory_dependency_revoked", "Consumed learner memory was corrected or removed", 409)
                if row["project_id"] not in (None, project_id):
                    raise ApiError("memory_project_scope", "Project learner support must keep its original ownership", 409)
                groups = conn.execute("SELECT * FROM memory_support_groups WHERE record_id=? AND state='active'",
                                      (identifier,)).fetchall()
                for group in groups:
                    try:
                        self.check_group_in(conn, group, seen=seen | {target.key})
                    except ApiError as error:
                        if error.code not in INELIGIBLE_LINEAGE_CODES:
                            raise
                        continue
                    break
                else:
                    raise ApiError("memory_dependency_revoked", "Consumed learner memory has no eligible support", 409)
            elif target.type == "learning_evidence":
                prior = self.check_in(conn, target.id, expected=dependency.expected_revision,
                                      seen=seen, for_support=for_support)
                if prior is not None and prior["project_id"] not in (None, project_id):
                    raise ApiError("memory_project_scope", "Historical project support must keep its original ownership", 409)
            else:
                closure = self.resolve_in(conn, dependency, project_id=project_id, for_support=for_support)
                self.check_inputs_in(conn, closure, seen=seen | {target.key},
                                     project_id=project_id, for_support=for_support)

    def check_in(self, conn, evidence_id, *, expected=None, seen=frozenset(), for_support=False):
        row = conn.execute("SELECT * FROM memory_answer_lineage WHERE evidence_id=?", (evidence_id,)).fetchone()
        if conn.execute("SELECT 1 FROM memory_suppression WHERE source_key=?", ("evidence:" + evidence_id,)).fetchone():
            raise ApiError("memory_dependency_revoked", "This answer's learner support was suppressed", 409)
        if row is None:
            if for_support:
                # Persisted groups already copied the complete ancestor roots
                # at admission. Removal of a source-owned receipt only makes
                # provenance unavailable; these groups still check their roots.
                return None
            raise ApiError("memory_lineage_unknown", "This historical answer has no verified support manifest", 409)
        if row["state"] != "active":
            raise ApiError("memory_dependency_revoked", "This answer's learner support was revoked", 409)
        if expected is not None and row["publication_digest"] != expected:
            raise ApiError("memory_dependency_revoked", "The referenced answer publication changed", 409)
        manifest = AnswerInputs.model_validate_json(row["manifest_json"])
        evidence = conn.execute("SELECT * FROM learning_evidence WHERE id=?", (evidence_id,)).fetchone()
        # Ordinary chat deletion leaves already retained learning independent
        # of transcript ownership. It cannot admit missing history to a new run.
        if not for_support:
            if evidence is None:
                raise ApiError("memory_answer_unavailable", "This historical answer is no longer available", 409)
            payload = json.loads(evidence["payload_json"])
            answer_reference_in(conn, evidence, payload, ContextScope.model_validate(payload["scope"]))
        if evidence is not None and row["publication_digest"] != canonical_digest({"evidence": dict(evidence),
                "manifest": manifest.model_dump(mode="json"), "project_id": row["project_id"]}):
            raise ApiError("memory_dependency_revoked", "The local answer publication changed", 409)
        self.check_inputs_in(conn, manifest, seen=seen | {("learning_evidence", evidence_id)},
                             project_id=row["project_id"], for_support=for_support)
        return dict(row)

    def eligible_history(self, messages, *, project_id=None):
        filtered, inputs = [], []
        with self.db.transaction() as conn:
            for message in messages:
                if message.get("role") != "assistant":
                    filtered.append(message)
                    continue
                identifier = "learn-answer:" + message.get("run_id", "")
                try:
                    lineage = self.check_in(conn, identifier)
                    if lineage["project_id"] not in (None, project_id):
                        continue
                except ApiError as error:
                    if error.code not in INELIGIBLE_LINEAGE_CODES:
                        raise
                    continue
                filtered.append(message)
                inputs.append(EligibleInput(kind="committed_evidence", dependency=Dependency(
                    target=Identity(type="learning_evidence", id=identifier),
                    expected_revision=lineage["publication_digest"])))
        return filtered, tuple(inputs)
