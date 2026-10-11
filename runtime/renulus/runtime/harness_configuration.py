"""Canonical H04 configuration authority; no transport, credentials or runtime writer.

The parent supplies closed-candidate and stopped-host evidence. This module never
starts a host or grants a network effect merely by staging a configuration.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path
from typing import Callable, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from renulus.contracts import ApiError
from renulus.storage.database import Database, utc_now
from .policy import ALLOWED_MODELS, BASE_URLS


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class ConnectionReference(FrozenModel):
    provider: Literal["codex", "opencode-go"]
    credential_reference: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    credential_revision: int = Field(ge=0)
    selected_model: str | None = None

    @model_validator(mode="after")
    def allowed_selection(self):
        if self.selected_model is not None and self.selected_model not in ALLOWED_MODELS[self.provider]:
            raise ValueError("Model is outside the selected subscription allowlist")
        return self


PURPOSES = frozenset({"explain", "case-discuss", "case-image-discuss", "evidence-review",
    "generated-practice", "fictional-test", "test-import", "memory-extraction", "compaction",
    "summary", "test-result-narrative", "daily_suggestions", "updates-digest", "title"})
STANDALONE_PURPOSES = frozenset({"memory-extraction", "compaction", "summary",
    "test-result-narrative", "daily_suggestions", "updates-digest"})
AUXILIARY_PURPOSES = {"title": "title", "summary": "summary", "compaction": "compaction",
                      "summary-repair": "compaction"}


class RolePolicy(FrozenModel):
    purpose: str
    enabled: bool = True
    model_id: str | None = None
    output_tokens: int = Field(default=4096, ge=1, le=32768)
    dispatch_limit: int | None = Field(default=None, ge=0, le=128)

    @model_validator(mode="after")
    def known_purpose(self):
        if self.purpose not in PURPOSES:
            raise ValueError("Unknown owning-domain purpose")
        return self


class ContextPolicy(FrozenModel):
    requested_window_tokens: int = Field(default=131072, ge=1, le=262144)
    reserve_tokens: int = Field(default=0, ge=0, le=262144)


class AttemptPolicy(FrozenModel):
    foreground_dispatches: int = Field(default=12, ge=0, le=128)
    standalone_dispatches: int = Field(default=1, ge=0, le=128)
    title_dispatches: int = Field(default=0, ge=0, le=128)
    retries: int = Field(default=0, ge=0, le=10)
    retryable_errors: tuple[Literal["transport_unavailable", "summary_invalid"], ...] = ()


class ChildPolicy(FrozenModel):
    max_depth: int = Field(default=1, ge=0, le=1)
    concurrency: int = Field(default=2, ge=0, le=2)


class InputHash(FrozenModel):
    kind: Literal["artifact", "build", "role", "instruction", "skill", "tool-schema", "mcp-identity"]
    name: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RouteLimits(FrozenModel):
    """Proven limits from H03 for the exact pinned deployment; absence denies dispatch."""
    input_tokens: int | None = Field(default=None, ge=1)
    output_tokens: int | None = Field(default=None, ge=1)
    window_tokens: int | None = Field(default=None, ge=1)


class ConfigurationSpec(FrozenModel):
    connection: ConnectionReference
    registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    roles: tuple[RolePolicy, ...] = ()
    inputs: tuple[InputHash, ...] = ()
    capabilities: tuple[str, ...] = ()
    context: ContextPolicy = ContextPolicy()
    attempts: AttemptPolicy = AttemptPolicy()
    children: ChildPolicy = ChildPolicy()

    @model_validator(mode="after")
    def unique_allowed_roles(self):
        if len({role.purpose for role in self.roles}) != len(self.roles):
            raise ValueError("Duplicate purpose policy")
        if any(role.model_id is not None and role.model_id not in ALLOWED_MODELS[self.connection.provider]
               for role in self.roles):
            raise ValueError("Role model is outside the selected subscription allowlist")
        if len({(item.kind, item.name) for item in self.inputs}) != len(self.inputs):
            raise ValueError("Duplicate immutable input")
        if len(set(self.capabilities)) != len(self.capabilities) or any(
                not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", item) for item in self.capabilities):
            raise ValueError("Use unique opaque capability identifiers")
        return self


@dataclass(frozen=True)
class RoleBinding:
    version: str
    purpose: str
    connection: ConnectionReference
    model_id: str
    output_tokens: int
    dispatch_limit: int


class CandidateHealth(FrozenModel):
    configuration_version: str = Field(pattern=r"^[0-9a-f]{64}$")
    grant_epoch: int = Field(ge=0)
    registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    healthy: bool = True
    generation_open: bool = False
    recovery_open: bool = False
    package_acquisition_open: bool = False
    mcp_startup_open: bool = False
    live_store_writer: bool = False


class RestartBoundary(FrozenModel):
    admission_closed: bool
    runtime_stopped: bool
    domain_settled: bool


@dataclass(frozen=True)
class Candidate:
    version: str
    spec: ConfigurationSpec
    grant_epoch: int
    generation_open: bool = False
    recovery_open: bool = False
    package_acquisition_open: bool = False
    mcp_startup_open: bool = False
    live_store_writer: bool = False


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _deny(code: str):
    raise ApiError(code, "The configuration operation is unavailable under the current policy.", 409)


def _identifier(value: str):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        _deny("invalid_operation_identity")


class ConfigurationAuthority:
    def __init__(self, database: Database):
        self.db = database
        migration = Path(__file__).with_name("migrations") / "002-harness-configuration.sql"
        self.db.apply_migration("runtime-002-harness-configuration", migration.read_text(encoding="utf-8"))
        purpose_migration = migration.with_name("004-harness-dispatch-purpose.sql")
        self.db.apply_migration("runtime-004-harness-dispatch-purpose", purpose_migration.read_text(encoding="utf-8"))

    def status(self) -> dict:
        row = self.db.fetch_one("SELECT * FROM harness_configuration_pointer WHERE id=1")
        return {key: bool(row[key]) if key == "admission_open" else row[key]
                for key in ("requested", "effective", "failed", "failure_code", "admission_open")}

    def configuration(self, version: str) -> ConfigurationSpec:
        with closing(self.db.connect()) as conn:
            return self._configuration(conn, version)

    def _configuration(self, conn, version: str) -> ConfigurationSpec:
        row = conn.execute("SELECT * FROM harness_configuration_versions WHERE version=?", (version,)).fetchone()
        if not row:
            _deny("configuration_missing")
        if hashlib.sha256(row["payload_json"].encode()).hexdigest() != version:
            _deny("configuration_hash_mismatch")
        return ConfigurationSpec.model_validate_json(_json(json.loads(row["payload_json"])["spec"]))

    def activation_snapshot(self) -> dict:
        """Trusted controller observation; policy pins are not native settlement proof."""
        with self.db.transaction() as conn:
            return self._activation_snapshot(conn)

    def _activation_snapshot(self, conn) -> dict:
        pointer = conn.execute("SELECT * FROM harness_configuration_pointer WHERE id=1").fetchone()
        overlay = self.revocation_overlay(conn=conn)
        return {
            **{key: bool(pointer[key]) if key == "admission_open" else pointer[key]
               for key in ("requested", "effective", "previous", "activating",
                           "failed", "failure_code", "admission_open")},
            "grant_epoch": overlay["epoch"], "revoked": overlay["revoked"],
            "configuration": self._configuration(conn, pointer["effective"])
                if pointer["effective"] else None,
            "requested_configuration": self._configuration(conn, pointer["requested"])
                if pointer["requested"] else None,
            "pinned_runs": [dict(row) for row in conn.execute(
                "SELECT r.run_id,r.purpose,r.version FROM harness_configuration_runs r "
                "WHERE r.state IS NULL OR r.state != 'settled' OR EXISTS ("
                "SELECT 1 FROM harness_configuration_attempts a "
                "WHERE (a.run_id=r.run_id OR a.root_id=r.run_id) AND (a.state IS NULL OR "
                "a.state NOT IN ('confirmed','failed','uncertain','cancelled_before_send'))) "
                "ORDER BY r.run_id")],
        }

    def close_admission(self, *, expected_effective: str | None, requested_version: str,
                        grant_epoch: int) -> dict:
        """Seal canonical admission only; parent owns ingress and actual settlement."""
        if not isinstance(requested_version, str) or not re.fullmatch(r"[0-9a-f]{64}", requested_version):
            _deny("activation_conflict")
        if type(grant_epoch) is not int or grant_epoch < 0:
            _deny("candidate_authority_stale")
        with self.db.transaction() as conn:
            snapshot = self._activation_snapshot(conn)
            if (snapshot["effective"] != expected_effective
                    or snapshot["requested"] != requested_version or snapshot["activating"]):
                _deny("activation_conflict")
            if snapshot["grant_epoch"] != grant_epoch:
                _deny("candidate_authority_stale")
            if snapshot["pinned_runs"]:
                raise ApiError("harness_configuration_busy",
                    "Finish or stop the pinned runs before activating configuration.", 409, True)
            conn.execute("UPDATE harness_configuration_pointer SET admission_open=0 WHERE id=1")
            return {**snapshot, "admission_open": False}

    def stage(self, spec: ConfigurationSpec) -> str:
        if not isinstance(spec, ConfigurationSpec):
            _deny("configuration_invalid")
        spec = ConfigurationSpec.model_validate_json(spec.model_dump_json())
        with self.db.transaction() as conn:
            predecessor = conn.execute("SELECT effective FROM harness_configuration_pointer WHERE id=1").fetchone()[0]
            payload = _json({"predecessor": predecessor, "spec": spec.model_dump(mode="json")})
            version = hashlib.sha256(payload.encode()).hexdigest()
            conn.execute("INSERT OR IGNORE INTO harness_configuration_versions VALUES(?,?,?,?)",
                         (version, predecessor, payload, utc_now()))
            conn.execute("INSERT OR IGNORE INTO harness_configuration_health(version,state) VALUES(?,'staged')", (version,))
            conn.execute("UPDATE harness_configuration_pointer SET requested=? WHERE id=1", (version,))
        return version

    def resolve_role(self, version: str, purpose: str, *, catalogue: tuple[str, ...] = (),
                     operation_model: str | None = None, parent_model: str | None = None) -> RoleBinding:
        spec = self.configuration(version)
        if purpose not in PURPOSES:
            _deny("purpose_not_allowed")
        role = next((value for value in spec.roles if value.purpose == purpose),
                    RolePolicy(purpose=purpose, enabled=purpose != "title"))
        if not role.enabled:
            _deny("role_disabled")
        allowed = ALLOWED_MODELS[spec.connection.provider]
        chosen = next((value for value in (operation_model, role.model_id, parent_model,
                                          spec.connection.selected_model) if value is not None), None)
        if chosen is not None and chosen not in allowed:
            _deny("model_not_allowed")
        chosen = chosen or next((value for value in allowed if value in catalogue), allowed[0])
        default_limit = (spec.attempts.title_dispatches if purpose == "title" else
                         spec.attempts.standalone_dispatches if purpose in STANDALONE_PURPOSES else
                         spec.attempts.foreground_dispatches)
        limit = role.dispatch_limit if role.dispatch_limit is not None else default_limit
        return RoleBinding(version, purpose, spec.connection, chosen, role.output_tokens, limit)

    def begin_run(self, run_id: str, purpose: str, *, capability_scope: tuple[str, ...] = (),
                  catalogue: tuple[str, ...] = (), operation_model: str | None = None) -> dict:
        """Owning domain supplies trusted purpose/scope; identifiers contain no user text."""
        _identifier(run_id)
        with self.db.transaction() as conn:
            pointer = conn.execute("SELECT * FROM harness_configuration_pointer WHERE id=1").fetchone()
            if not pointer["admission_open"] or not pointer["effective"]:
                _deny("configuration_not_active")
            version = pointer["effective"]
            spec = self.configuration(version)
            if not set(capability_scope).issubset(spec.capabilities):
                _deny("scope_widening")
            binding = self.resolve_role(version, purpose, catalogue=catalogue, operation_model=operation_model)
            route = {"provider": binding.connection.provider,
                     "credential_reference": binding.connection.credential_reference,
                     "credential_revision": binding.connection.credential_revision,
                     "model_id": binding.model_id, "output_tokens": binding.output_tokens,
                     "endpoint": BASE_URLS[binding.connection.provider],
                     "protocol": "responses" if binding.connection.provider == "codex" else "chat-completions"}
            if conn.execute("SELECT 1 FROM harness_configuration_runs WHERE run_id=?", (run_id,)).fetchone():
                _deny("run_already_exists")
            conn.execute("INSERT INTO harness_configuration_runs VALUES(?,?,?,?,?,?,?,?,?,'active',?)",
                (run_id, version, run_id, None, purpose, 0, binding.dispatch_limit,
                 _json(sorted(capability_scope)), _json(route), utc_now()))
        return self.run(run_id)

    def begin_child(self, run_id: str, parent_id: str, purpose: str, *,
                    capability_scope: tuple[str, ...] = (), operation_model: str | None = None) -> dict:
        _identifier(run_id)
        with self.db.transaction() as conn:
            parent = conn.execute("SELECT * FROM harness_configuration_runs WHERE run_id=?", (parent_id,)).fetchone()
            if not parent or parent["state"] != "active":
                _deny("parent_unavailable")
            spec = self.configuration(parent["version"])
            if parent["depth"] >= spec.children.max_depth:
                _deny("child_depth_exhausted")
            count = conn.execute("SELECT COUNT(*) FROM harness_configuration_runs WHERE root_id=? AND parent_id IS NOT NULL AND state='active'", (parent["root_id"],)).fetchone()[0]
            if count >= spec.children.concurrency:
                _deny("child_concurrency_exhausted")
            if not set(capability_scope).issubset(self._capabilities(conn, parent)):
                _deny("scope_widening")
            parent_route = json.loads(parent["route_json"])
            binding = self.resolve_role(parent["version"], purpose, operation_model=operation_model,
                                        parent_model=parent_route["model_id"])
            route = {**parent_route, "model_id": binding.model_id, "output_tokens": binding.output_tokens}
            if conn.execute("SELECT 1 FROM harness_configuration_runs WHERE run_id=?", (run_id,)).fetchone():
                _deny("run_already_exists")
            conn.execute("INSERT INTO harness_configuration_runs VALUES(?,?,?,?,?,?,?,?,?,'active',?)",
                (run_id, parent["version"], parent["root_id"], parent_id, purpose, parent["depth"] + 1,
                 binding.dispatch_limit, _json(sorted(capability_scope)), _json(route), utc_now()))
        return self.run(run_id)

    def run(self, run_id: str) -> dict:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM harness_configuration_runs WHERE run_id=?", (run_id,)).fetchone()
            if not row:
                _deny("run_missing")
            return {"run_id": row["run_id"], "version": row["version"], "root_id": row["root_id"],
                    "parent_id": row["parent_id"], "purpose": row["purpose"], "state": row["state"],
                    "dispatch_limit": row["dispatch_limit"], "route": json.loads(row["route_json"]),
                    "effective_capabilities": sorted(self._capabilities(conn, row)),
                    "spent_dispatches": conn.execute("SELECT COUNT(*) FROM harness_configuration_attempts WHERE root_id=?", (row["root_id"],)).fetchone()[0]}

    def _capabilities(self, conn, row) -> set[str]:
        revoked = {value[0] for value in conn.execute("SELECT capability FROM harness_configuration_revocations")}
        granted = set(json.loads(row["capabilities_json"])) - revoked
        if row["parent_id"]:
            parent = conn.execute("SELECT * FROM harness_configuration_runs WHERE run_id=?", (row["parent_id"],)).fetchone()
            granted &= self._capabilities(conn, parent)
        return granted

    def settle_run(self, run_id: str):
        """Integrator calls after actual runtime settlement; this only closes policy ownership."""
        with self.db.transaction() as conn:
            row = conn.execute("SELECT state FROM harness_configuration_runs WHERE run_id=?", (run_id,)).fetchone()
            if not row:
                _deny("run_missing")
            if conn.execute("SELECT 1 FROM harness_configuration_attempts WHERE run_id=? AND state IN ('reserved','dispatched')", (run_id,)).fetchone():
                _deny("run_not_settled")
            if conn.execute("SELECT 1 FROM harness_configuration_runs WHERE parent_id=? AND state='active'", (run_id,)).fetchone():
                _deny("run_not_settled")
            conn.execute("UPDATE harness_configuration_runs SET state='settled' WHERE run_id=?", (run_id,))

    def revoke(self, capability: str) -> int:
        """Monotonic narrowing also supports purpose:<id>, connection:<ref>, model:<id>."""
        if not isinstance(capability, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", capability):
            _deny("invalid_capability")
        with self.db.transaction() as conn:
            conn.execute("UPDATE harness_configuration_grants SET epoch=epoch+1 WHERE id=1")
            epoch = conn.execute("SELECT epoch FROM harness_configuration_grants WHERE id=1").fetchone()[0]
            conn.execute("INSERT OR IGNORE INTO harness_configuration_revocations VALUES(?,?,?)", (capability, epoch, utc_now()))
        return epoch

    def revocation_overlay(self, *, conn=None) -> dict:
        """Current mandatory narrowing, including in an owning publication transaction."""
        if conn is None:
            with self.db.transaction() as transaction:
                return self.revocation_overlay(conn=transaction)
        epoch = conn.execute("SELECT epoch FROM harness_configuration_grants WHERE id=1").fetchone()[0]
        return {"epoch": epoch, "revoked": [row[0] for row in conn.execute(
            "SELECT capability FROM harness_configuration_revocations ORDER BY capability")]}

    def require_current(self, run_id: str, *, required_capabilities: tuple[str, ...] = (),
                        connection: ConnectionReference | None = None,
                        permit_id: str | None = None, conn=None) -> dict:
        """Local guard for final dispatch AND the parent's canonical publication transaction."""
        if conn is None:
            with self.db.transaction() as transaction:
                return self.require_current(run_id, required_capabilities=required_capabilities,
                                            connection=connection, permit_id=permit_id, conn=transaction)
        row = conn.execute("SELECT * FROM harness_configuration_runs WHERE run_id=?", (run_id,)).fetchone()
        if not row or row["state"] != "active":
            _deny("run_unavailable")
        overlay = self.revocation_overlay(conn=conn)
        revoked = set(overlay["revoked"])
        dispatch_purpose = row["purpose"]
        if permit_id is not None:
            attempt = conn.execute("SELECT * FROM harness_configuration_attempts WHERE permit_id=?",
                                   (permit_id,)).fetchone()
            if not attempt or attempt["run_id"] != run_id:
                _deny("permit_authority_mismatch")
            dispatch_purpose = self._dispatch_purposes(conn, row["root_id"])[permit_id]
            if dispatch_purpose is None:
                _deny("dispatch_purpose_unavailable")
            if "purpose:" + dispatch_purpose in revoked:
                _deny("authority_revoked")
            required_capabilities = tuple(set(required_capabilities) |
                                          set(json.loads(attempt["required_capabilities_json"])))
        ancestor = row
        while ancestor:
            route = json.loads(ancestor["route_json"])
            if ancestor["state"] != "active" or revoked & {"purpose:" + ancestor["purpose"],
                    "connection:" + route["credential_reference"], "model:" + route["model_id"]}:
                _deny("authority_revoked")
            ancestor = (conn.execute("SELECT * FROM harness_configuration_runs WHERE run_id=?",
                                    (ancestor["parent_id"],)).fetchone() if ancestor["parent_id"] else None)
        granted = self._capabilities(conn, row)
        if not set(required_capabilities).issubset(granted):
            _deny("capability_revoked")
        route = json.loads(row["route_json"])
        if connection is not None and (connection.provider != route["provider"]
                or connection.credential_reference != route["credential_reference"]
                or connection.credential_revision != route["credential_revision"]):
            _deny("connection_changed")
        return {"version": row["version"], "purpose": row["purpose"],
                "dispatch_purpose": dispatch_purpose, "grant_epoch": overlay["epoch"],
                "effective_capabilities": sorted(granted), "route": route}

    def _fit(self, spec: ConfigurationSpec, limits: RouteLimits, input_tokens: int, output: int) -> int:
        if type(input_tokens) is not int or input_tokens < 0:
            _deny("invalid_input_budget")
        if any(value is None for value in (limits.input_tokens, limits.output_tokens, limits.window_tokens)):
            _deny("route_limits_unknown")
        output = min(output, limits.output_tokens)
        window = min(spec.context.requested_window_tokens, limits.window_tokens)
        if input_tokens > limits.input_tokens or input_tokens + output + spec.context.reserve_tokens > window:
            _deny("request_does_not_fit")
        return output

    def _dispatch_purposes(self, conn, root_id: str) -> dict[str, str | None]:
        """Read the ledger, conservatively identifying pre-004 attempts."""
        purposes, steps, mixed_runs = {}, {}, set()
        for attempt in conn.execute("SELECT a.*,r.purpose AS run_purpose FROM harness_configuration_attempts a "
                "JOIN harness_configuration_runs r ON r.run_id=a.run_id WHERE a.root_id=? ORDER BY a.rowid", (root_id,)):
            step = (attempt["run_id"], attempt["step_id"])
            purpose = attempt["dispatch_purpose"]
            if purpose is None:
                if attempt["retry_number"]:
                    purpose = steps.get(step)
                elif attempt["request_kind"] == "tool-continuation" and attempt["run_id"] in mixed_runs:
                    purpose = None
                else:
                    purpose = AUXILIARY_PURPOSES.get(attempt["request_kind"], attempt["run_purpose"])
            if purpose not in PURPOSES:
                purpose = None
            purposes[attempt["permit_id"]] = purpose
            if not attempt["retry_number"]:
                steps[step] = purpose
            if purpose != attempt["run_purpose"]:
                mixed_runs.add(attempt["run_id"])
        return purposes

    def _check_dispatch_budget(self, conn, run, purpose: str, purposes: dict[str, str | None],
                               *, permit_id: str | None = None) -> int:
        """Enforce pooled debits at reservation or at a permit's original ledger position."""
        identities = list(purposes)
        if permit_id is not None:
            identities = identities[:identities.index(permit_id) + 1]
        counted = [purposes[identity] for identity in identities]
        if None in counted:
            _deny("dispatch_purpose_unavailable")
        route = json.loads(run["route_json"])
        purpose_limit, output = run["dispatch_limit"], route["output_tokens"]
        if purpose != run["purpose"]:
            binding = self.resolve_role(run["version"], purpose, parent_model=route["model_id"])
            if binding.model_id != route["model_id"]:
                _deny("auxiliary_route_requires_own_run")
            purpose_limit, output = binding.dispatch_limit, min(output, binding.output_tokens)
        root_limit = conn.execute("SELECT dispatch_limit FROM harness_configuration_runs WHERE run_id=?",
                                  (run["root_id"],)).fetchone()[0]
        local_spent = conn.execute("SELECT COUNT(*) FROM harness_configuration_attempts WHERE run_id=? AND (? IS NULL OR rowid <= (SELECT rowid FROM harness_configuration_attempts WHERE permit_id=?))",
                                   (run["run_id"], permit_id, permit_id)).fetchone()[0]
        debit = 1 if permit_id is None else 0
        if (counted.count(purpose) + debit > purpose_limit
                or len(counted) + debit > root_limit
                or (run["parent_id"] and local_spent + debit > run["dispatch_limit"])):
            _deny("dispatch_budget_exhausted")
        return output

    def admit(self, run_id: str, step_id: str, *, payload_hash: str, request_kind: str,
              connection: ConnectionReference, limits: RouteLimits, input_tokens: int,
              required_capabilities: tuple[str, ...] = (), retry_of: str | None = None,
              continuation_of: str | None = None) -> dict:
        """Durably debit immediately before transport. No network work inside this method."""
        _identifier(step_id)
        if not isinstance(payload_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", payload_hash):
            _deny("invalid_payload_identity")
        if request_kind not in {"primary", "child", "tool-continuation", "generate", "title",
                                 "summary", "compaction", "summary-repair", "transport-fallback", "recovery"}:
            _deny("request_kind_not_allowed")
        if type(input_tokens) is not int or input_tokens < 0:
            _deny("invalid_input_budget")
        if continuation_of is not None:
            _identifier(continuation_of)
            if request_kind != "tool-continuation" or retry_of is not None:
                _deny("invalid_continuation")
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM harness_configuration_runs WHERE run_id=?", (run_id,)).fetchone()
            if not row or row["state"] != "active":
                _deny("run_unavailable")
            if not conn.execute("SELECT admission_open FROM harness_configuration_pointer WHERE id=1").fetchone()[0]:
                _deny("configuration_not_active")
            route = json.loads(row["route_json"])
            self.require_current(run_id, required_capabilities=required_capabilities, connection=connection, conn=conn)
            if (connection.provider != route["provider"] or connection.credential_reference != route["credential_reference"]
                    or connection.credential_revision != route["credential_revision"]):
                _deny("connection_changed")
            revoked = {value[0] for value in conn.execute("SELECT capability FROM harness_configuration_revocations")}
            if revoked & {"purpose:" + row["purpose"], "connection:" + route["credential_reference"], "model:" + route["model_id"]}:
                _deny("authority_revoked")
            if not set(required_capabilities).issubset(self._capabilities(conn, row)):
                _deny("capability_revoked")
            previous = conn.execute("SELECT * FROM harness_configuration_attempts WHERE run_id=? AND step_id=? ORDER BY retry_number DESC LIMIT 1", (run_id, step_id)).fetchone()
            spec = self.configuration(row["version"])
            retry_number = 0
            if previous:
                if previous["payload_hash"] != payload_hash:
                    _deny("payload_changed")
                if previous["state"] == "confirmed" and retry_of is None:
                    return self.permit(previous["permit_id"])
                if previous["state"] in {"dispatched", "uncertain"}:
                    _deny("dispatch_uncertain")
                if (retry_of != previous["permit_id"] or previous["state"] != "failed"
                        or previous["failure_code"] not in spec.attempts.retryable_errors
                        or previous["retry_number"] >= spec.attempts.retries):
                    _deny("retry_not_allowed")
                retry_number = previous["retry_number"] + 1
            elif retry_of is not None or request_kind in {"summary-repair", "transport-fallback", "recovery"}:
                _deny("retry_not_allowed")
            purposes = self._dispatch_purposes(conn, row["root_id"])
            if None in purposes.values():
                _deny("dispatch_purpose_unavailable")
            dispatch_purpose = AUXILIARY_PURPOSES.get(request_kind, row["purpose"])
            if previous:
                dispatch_purpose = purposes[previous["permit_id"]]
            elif request_kind == "tool-continuation":
                if continuation_of is None:
                    prior = conn.execute("SELECT permit_id,state FROM harness_configuration_attempts WHERE run_id=? ORDER BY rowid DESC LIMIT 1",
                                         (run_id,)).fetchone()
                    if prior is None or any(purposes[attempt[0]] != row["purpose"] for attempt in conn.execute(
                            "SELECT permit_id FROM harness_configuration_attempts WHERE run_id=?", (run_id,))):
                        _deny("continuation_identity_required")
                else:
                    prior = conn.execute("SELECT permit_id,state,run_id FROM harness_configuration_attempts WHERE permit_id=?",
                                         (continuation_of,)).fetchone()
                    if prior is None or prior["run_id"] != run_id:
                        _deny("continuation_authority_mismatch")
                if prior["state"] != "confirmed":
                    _deny("continuation_not_confirmed")
                dispatch_purpose = purposes[prior["permit_id"]]
            if "purpose:" + dispatch_purpose in revoked:
                _deny("authority_revoked")
            output = self._check_dispatch_budget(conn, row, dispatch_purpose, purposes)
            output = self._fit(spec, limits, input_tokens, output)
            epoch = conn.execute("SELECT epoch FROM harness_configuration_grants WHERE id=1").fetchone()[0]
            permit_id = uuid4().hex
            conn.execute("INSERT INTO harness_configuration_attempts(permit_id,run_id,root_id,step_id,payload_hash,request_kind,required_capabilities_json,retry_number,grant_epoch,output_tokens,state,created_at,dispatch_purpose) VALUES(?,?,?,?,?,?,?,?,?,?,'reserved',?,?)",
                (permit_id, run_id, row["root_id"], step_id, payload_hash, request_kind, _json(sorted(required_capabilities)), retry_number, epoch, output, utc_now(), dispatch_purpose))
        return self.permit(permit_id)

    def permit(self, permit_id: str) -> dict:
        with closing(self.db.connect()) as conn:
            result = conn.execute("SELECT a.*,r.version,r.purpose,r.route_json FROM harness_configuration_attempts a JOIN harness_configuration_runs r ON r.run_id=a.run_id WHERE permit_id=?", (permit_id,)).fetchone()
            if not result:
                _deny("permit_missing")
            row = dict(result)
            if row["dispatch_purpose"] is None:
                row["dispatch_purpose"] = self._dispatch_purposes(conn, row["root_id"])[permit_id]
        row["route"] = json.loads(row.pop("route_json"))
        row["required_capabilities"] = json.loads(row.pop("required_capabilities_json"))
        row["dispatch_allowed"] = False
        return row

    def mark_dispatched(self, permit_id: str, *, connection: ConnectionReference, limits: RouteLimits,
                        input_tokens: int, payload_hash: str,
                        required_capabilities: tuple[str, ...] = ()) -> dict:
        """Serialized final admission; a returned dispatched permit may already have been sent.

        Transport must send exactly once after this returns, enforce output_tokens and
        bind endpoint/protocol/model to route. Timeout or lost acknowledgement is uncertain.
        """
        with self.db.transaction() as conn:
            attempt = conn.execute("SELECT * FROM harness_configuration_attempts WHERE permit_id=?", (permit_id,)).fetchone()
            if not attempt:
                _deny("permit_missing")
            if attempt["state"] != "reserved":
                _deny("dispatch_already_admitted")
            if not conn.execute("SELECT admission_open FROM harness_configuration_pointer WHERE id=1").fetchone()[0]:
                _deny("configuration_not_active")
            if payload_hash != attempt["payload_hash"]:
                _deny("payload_changed")
            required = tuple(sorted(set(required_capabilities) | set(json.loads(attempt["required_capabilities_json"]))))
            current = self.require_current(attempt["run_id"], required_capabilities=required,
                                           connection=connection, permit_id=permit_id, conn=conn)
            run = conn.execute("SELECT * FROM harness_configuration_runs WHERE run_id=?",
                               (attempt["run_id"],)).fetchone()
            purposes = self._dispatch_purposes(conn, attempt["root_id"])
            output = min(attempt["output_tokens"], self._check_dispatch_budget(
                conn, run, current["dispatch_purpose"], purposes, permit_id=permit_id))
            output = self._fit(self.configuration(current["version"]), limits, input_tokens, output)
            conn.execute("UPDATE harness_configuration_attempts SET state='dispatched',grant_epoch=?,output_tokens=?,required_capabilities_json=? WHERE permit_id=?",
                         (current["grant_epoch"], output, _json(required), permit_id))
        permit = self.permit(permit_id)
        permit["dispatch_allowed"] = True
        return permit

    def complete(self, permit_id: str, outcome: str, *, result_reference: str | None = None,
                 failure_code: str | None = None) -> dict:
        if outcome not in {"confirmed", "failed", "uncertain", "cancelled_before_send"}:
            _deny("invalid_dispatch_outcome")
        if result_reference is not None:
            _identifier(result_reference)
        if failure_code not in {None, "transport_unavailable", "summary_invalid", "authentication_required",
                                "subscription_limit", "model_unavailable", "input_unsupported"}:
            _deny("invalid_failure_code")
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM harness_configuration_attempts WHERE permit_id=?", (permit_id,)).fetchone()
            if not row:
                _deny("permit_missing")
            if row["state"] == "reserved" and outcome != "cancelled_before_send":
                _deny("dispatch_not_started")
            if row["state"] == "dispatched" and outcome == "cancelled_before_send":
                _deny("dispatch_may_have_sent")
            late_receipt = row["state"] == "uncertain" and outcome == "confirmed" and result_reference is not None
            if row["state"] not in {"reserved", "dispatched"} and not late_receipt:
                if (row["state"], row["result_reference"], row["failure_code"]) != (outcome, result_reference, failure_code):
                    _deny("receipt_conflict")
            else:
                conn.execute("UPDATE harness_configuration_attempts SET state=?,result_reference=?,failure_code=? WHERE permit_id=?", (outcome, result_reference, failure_code, permit_id))
        return self.permit(permit_id)

    def validate(self, version: str, probe: Callable[[Candidate], CandidateHealth]) -> bool:
        spec = self.configuration(version)
        epoch = self.revocation_overlay()["epoch"]
        failure = None
        try:
            health = probe(Candidate(version, spec, epoch))  # No canonical transaction across host work.
            if not isinstance(health, CandidateHealth) or not health.healthy:
                failure = "candidate_unhealthy"
            elif any((health.generation_open, health.recovery_open, health.package_acquisition_open,
                      health.mcp_startup_open, health.live_store_writer)):
                failure = "candidate_not_closed"
            elif health.registry_hash != spec.registry_hash:
                failure = "registry_mismatch"
            elif health.configuration_version != version or health.grant_epoch != epoch:
                failure = "candidate_authority_stale"
        except Exception:
            failure = "candidate_validation_failed"
        with self.db.transaction() as conn:
            if conn.execute("SELECT epoch FROM harness_configuration_grants WHERE id=1").fetchone()[0] != epoch:
                failure = "candidate_authority_stale"
            conn.execute("UPDATE harness_configuration_health SET state=?,registry_hash=?,grant_epoch=?,failure_code=? WHERE version=?",
                         ("failed" if failure else "ready", None if failure else spec.registry_hash, epoch, failure, version))
            if failure:
                conn.execute("UPDATE harness_configuration_pointer SET failed=?,failure_code=? WHERE id=1", (version, failure))
                conn.execute("UPDATE harness_configuration_pointer SET admission_open=0 WHERE id=1 AND effective=?", (version,))
        return failure is None

    def activate(self, version: str, boundary: RestartBoundary, *, expected_effective: str | None):
        if not all((boundary.admission_closed, boundary.runtime_stopped, boundary.domain_settled)):
            _deny("restart_boundary_required")
        with self.db.transaction() as conn:
            pointer = conn.execute("SELECT * FROM harness_configuration_pointer WHERE id=1").fetchone()
            row = conn.execute("SELECT v.predecessor,h.state,h.grant_epoch FROM harness_configuration_versions v JOIN harness_configuration_health h USING(version) WHERE version=?", (version,)).fetchone()
            epoch = conn.execute("SELECT epoch FROM harness_configuration_grants WHERE id=1").fetchone()[0]
            if (not row or row["state"] != "ready" or pointer["requested"] != version
                    or pointer["effective"] != expected_effective or row["predecessor"] != expected_effective
                    or row["grant_epoch"] != epoch or pointer["activating"]):
                _deny("activation_conflict")
            conn.execute("UPDATE harness_configuration_pointer SET previous=effective,effective=?,activating=?,admission_open=0 WHERE id=1", (version, version))

    def open_admission(self, version: str, *, registry_hash: str, grant_epoch: int):
        spec = self.configuration(version)
        if registry_hash != spec.registry_hash:
            _deny("registry_mismatch")
        with self.db.transaction() as conn:
            pointer = conn.execute("SELECT effective FROM harness_configuration_pointer WHERE id=1").fetchone()
            if pointer[0] != version:
                _deny("activation_conflict")
            health = conn.execute("SELECT state,grant_epoch FROM harness_configuration_health WHERE version=?", (version,)).fetchone()
            epoch = conn.execute("SELECT epoch FROM harness_configuration_grants WHERE id=1").fetchone()[0]
            if health["state"] != "ready" or grant_epoch != epoch or health["grant_epoch"] != epoch:
                _deny("candidate_authority_stale")
            conn.execute("UPDATE harness_configuration_pointer SET admission_open=1,previous=NULL,activating=NULL WHERE id=1")

    def reconcile_restart(self, boundary: RestartBoundary):
        """Call only after the parent has fenced and stopped the old runtime owner."""
        if not all((boundary.admission_closed, boundary.runtime_stopped, boundary.domain_settled)):
            _deny("restart_boundary_required")
        with self.db.transaction() as conn:
            conn.execute("UPDATE harness_configuration_attempts SET state='uncertain' WHERE state='dispatched'")
            conn.execute("UPDATE harness_configuration_attempts SET state='cancelled_before_send' WHERE state='reserved'")
            row = conn.execute("SELECT * FROM harness_configuration_pointer WHERE id=1").fetchone()
            if row["activating"]:
                conn.execute("UPDATE harness_configuration_health SET state='failed',failure_code='activation_interrupted' WHERE version=?", (row["activating"],))
                conn.execute("UPDATE harness_configuration_pointer SET effective=previous,previous=NULL,failed=activating,activating=NULL,failure_code='activation_interrupted',admission_open=0 WHERE id=1")
            else:
                conn.execute("UPDATE harness_configuration_pointer SET admission_open=0 WHERE id=1")
