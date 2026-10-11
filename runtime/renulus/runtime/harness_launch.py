# SPDX-License-Identifier: MIT
"""Credential-free launch snapshots; registry observation and activation stay external."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from pydantic import model_validator

from .harness_configuration import (
    AttemptPolicy, ChildPolicy, ConfigurationSpec, ConnectionReference, ContextPolicy,
    FrozenModel, InputHash, RolePolicy,
)


class HarnessLaunchError(ValueError):
    """Only a bounded machine code and fixed message escape launch validation."""

    def __init__(self, code: str):
        self.code = code
        super().__init__("The launch artifact is unavailable or invalid.")


MAX_LAUNCH_BYTES = 262144


class _LaunchPolicy(FrozenModel):
    connection: ConnectionReference
    roles: tuple[RolePolicy, ...]
    inputs: tuple[InputHash, ...]
    capabilities: tuple[str, ...]
    context: ContextPolicy
    attempts: AttemptPolicy
    children: ChildPolicy

    @model_validator(mode="after")
    def valid_configuration_policy(self):
        # Reuse the existing spec invariants without inventing a registry hash.
        return ConfigurationSpec.unique_allowed_roles(self)


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _unique_fields(pairs):
    fields = {}
    for key, value in pairs:
        if key in fields:
            raise HarnessLaunchError("launch_artifact_invalid")
        fields[key] = value
    return fields


def _invalid_constant(_value):
    raise HarnessLaunchError("launch_artifact_invalid")


def _check_json(value, *, depth=0, active=None, budget=None):
    active = set() if active is None else active
    budget = [8192] if budget is None else budget
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        raise HarnessLaunchError("launch_inputs_invalid")
    kind = type(value)
    if kind in (dict, list):
        if id(value) in active:
            raise HarnessLaunchError("launch_inputs_invalid")
        active.add(id(value))
        try:
            if kind is dict:
                for key, item in value.items():
                    if type(key) is not str:
                        raise HarnessLaunchError("launch_inputs_invalid")
                    _check_json(key, depth=depth + 1, active=active, budget=budget)
                    _check_json(item, depth=depth + 1, active=active, budget=budget)
            else:
                for item in value:
                    _check_json(item, depth=depth + 1, active=active, budget=budget)
        finally:
            active.remove(id(value))
    elif kind is str:
        if len(value) > MAX_LAUNCH_BYTES or len(value.encode("utf-8")) > MAX_LAUNCH_BYTES:
            raise HarnessLaunchError("launch_too_large")
    elif kind is int:
        if abs(value) > 9007199254740991:
            raise HarnessLaunchError("launch_inputs_invalid")
    elif kind is float:
        if not math.isfinite(value):
            raise HarnessLaunchError("launch_inputs_invalid")
    elif value is not None and kind is not bool:
        raise HarnessLaunchError("launch_inputs_invalid")


def _credential_free(value):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            if normalized in {"auth", "authentication", "credentials", "credential",
                    "clientsecret", "secret", "secrets", "password", "apikey", "accesstoken",
                    "refreshtoken", "authorization", "proxyauthorization", "cookie", "setcookie", "token"}:
                raise HarnessLaunchError("launch_credentials_forbidden")
            _credential_free(item)
    elif isinstance(value, list):
        for item in value:
            _credential_free(item)
    elif isinstance(value, str):
        if re.match(r"(?i)^\s*(bearer|basic)\s+\S", value):
            raise HarnessLaunchError("launch_credentials_forbidden")
        if "://" in value and urlsplit(value).username is not None:
            raise HarnessLaunchError("launch_credentials_forbidden")


def _validated_model(value, model):
    if type(value) is not model or value.model_fields_set - model.model_fields.keys():
        raise HarnessLaunchError("launch_inputs_invalid")
    # Serializers can coerce invalid model_copy values (e.g. bool into int).
    # Revalidate raw public field values before any JSON serialization.
    return model.model_validate({name: getattr(value, name) for name in model.model_fields})


@dataclass(frozen=True, init=False)
class FrozenLaunchInputs:
    """One JSON snapshot; free text and supplied artifact evidence need integrator review."""

    _payload: bytes = field(repr=False)

    def __init__(self, *, boot_settings: dict, connection: ConnectionReference,
                 roles: tuple[RolePolicy, ...], inputs: tuple[InputHash, ...],
                 capabilities: tuple[str, ...], context: ContextPolicy,
                 attempts: AttemptPolicy, children: ChildPolicy):
        try:
            if type(boot_settings) is not dict or set(boot_settings) & {
                    "protocol", "profile_id", "store_id", "generation", "root",
                    "domain_store_id", "domain_path"}:
                raise HarnessLaunchError("launch_inputs_invalid")
            _check_json(boot_settings)
            _credential_free(boot_settings)
            if type(roles) is not tuple or type(inputs) is not tuple:
                raise HarnessLaunchError("launch_inputs_invalid")
            policy = _LaunchPolicy(connection=_validated_model(connection, ConnectionReference),
                roles=tuple(_validated_model(role, RolePolicy) for role in roles),
                inputs=tuple(_validated_model(item, InputHash) for item in inputs),
                capabilities=capabilities, context=_validated_model(context, ContextPolicy),
                attempts=_validated_model(attempts, AttemptPolicy),
                children=_validated_model(children, ChildPolicy))
            policy = _LaunchPolicy.model_validate_json(_canonical(policy.model_dump(mode="json")))
            if any(item.kind == "artifact" and item.name == "launch" for item in policy.inputs):
                raise HarnessLaunchError("launch_inputs_invalid")
            document = {"version": 1, "boot_settings": boot_settings,
                        "policy": policy.model_dump(mode="json")}
            _check_json(document)
            payload = _canonical(document)
            if len(payload) > MAX_LAUNCH_BYTES:
                raise HarnessLaunchError("launch_too_large")
        except HarnessLaunchError:
            raise
        except (AttributeError, TypeError, ValueError, OverflowError, RecursionError):
            raise HarnessLaunchError("launch_inputs_invalid") from None
        object.__setattr__(self, "_payload", payload)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self._payload).hexdigest()

    @property
    def launch_hash(self) -> InputHash:
        return InputHash(kind="artifact", name="launch", sha256=self.sha256)

    @property
    def boot_settings(self) -> dict:
        """Return a fresh decoded copy, never a mutable alias of the snapshot."""
        return json.loads(self._payload)["boot_settings"]


def finish_spec(inputs: FrozenLaunchInputs, registry_hash: str) -> ConfigurationSpec:
    """Finish the initial spec with observed registry identity, without staging/activation.

    Later role-only staging retains this spec's launch input reference; it does
    not rebuild the launch artifact or restore its initial role policy.
    """
    if (type(inputs) is not FrozenLaunchInputs or type(registry_hash) is not str
            or re.fullmatch(r"[0-9a-f]{64}", registry_hash) is None):
        raise HarnessLaunchError("launch_spec_invalid")
    try:
        policy = json.loads(inputs._payload)["policy"]
        policy["inputs"].append(inputs.launch_hash.model_dump(mode="json"))
        return ConfigurationSpec.model_validate_json(_canonical({**policy, "registry_hash": registry_hash}))
    except (TypeError, ValueError):
        raise HarnessLaunchError("launch_spec_invalid") from None


def _is_link(info) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _check_artifact_file(info):
    if _is_link(info) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise HarnessLaunchError("launch_artifact_invalid")


def _unsafe_windows_component(part: str) -> bool:
    # Keep the declared Python 3.12 floor; os.path.isreserved arrived later.
    return (part.endswith((" ", "."))
            or re.search(r'[<>:"|?*\x00-\x1f]', part) is not None
            or re.fullmatch(r"(?i)(con|prn|aux|nul|conin\$|conout\$|com[1-9¹²³]|lpt[1-9¹²³])(\..*)?", part)
            is not None)


class LaunchArtifactStore:
    """Windows content-addressed metadata, separate from either runtime store.

    The caller owns these explicit roots. Link checks do not sandbox a hostile
    concurrent OS user. Publication flushes the file before atomic no-replace
    rename; missing/corrupt artifacts after a crash fail closed on load.
    """

    def __init__(self, artifact_root: Path, *, live_root: Path, candidate_root: Path):
        if os.name != "nt":
            raise HarnessLaunchError("launch_path_invalid")
        for root in (artifact_root, live_root, candidate_root):
            if (not isinstance(root, Path) or not root.is_absolute()
                    or any(_unsafe_windows_component(part) for part in root.parts[1:])):
                raise HarnessLaunchError("launch_path_invalid")
        for protected in (live_root, candidate_root):
            if artifact_root.is_relative_to(protected) or protected.is_relative_to(artifact_root):
                raise HarnessLaunchError("launch_path_invalid")
        self._artifact_root = artifact_root
        self._live_root, self._candidate_root = live_root, candidate_root
        self._check_roots()

    def _check_roots(self):
        try:
            for root in (self._artifact_root, self._live_root, self._candidate_root):
                for component in (*reversed(root.parents), root):
                    try:
                        info = component.lstat()
                    except FileNotFoundError:
                        continue
                    if (_is_link(info) or not stat.S_ISDIR(info.st_mode)):
                        raise HarnessLaunchError("launch_path_invalid")
                if root.resolve() != root:
                    raise HarnessLaunchError("launch_path_invalid")
        except OSError:
            raise HarnessLaunchError("launch_path_invalid") from None

    def save(self, inputs: FrozenLaunchInputs) -> InputHash:
        if type(inputs) is not FrozenLaunchInputs:
            raise HarnessLaunchError("launch_inputs_invalid")
        self._check_roots()
        temporary = None
        try:
            root = self._artifact_root
            root.mkdir(parents=True, exist_ok=True)
            self._check_roots()
            destination = root / (inputs.sha256 + ".json")
            with NamedTemporaryFile(dir=root, prefix=".launch-", suffix=".tmp", delete=False) as staged:
                temporary = Path(staged.name)
                staged.write(inputs._payload)
                staged.flush()
                os.fsync(staged.fileno())
            self._check_roots()
            try:
                # Windows rename is atomic and fails if the destination exists.
                os.rename(temporary, destination)
            except FileExistsError:
                if self.load(inputs.sha256) != inputs:
                    raise HarnessLaunchError("launch_artifact_invalid")
        except OSError:
            raise HarnessLaunchError("launch_artifact_invalid") from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    raise HarnessLaunchError("launch_artifact_invalid") from None
        return inputs.launch_hash

    def load(self, sha256: str) -> FrozenLaunchInputs:
        if type(sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            raise HarnessLaunchError("launch_artifact_invalid")
        self._check_roots()
        try:
            path = self._artifact_root / (sha256 + ".json")
            _check_artifact_file(path.lstat())
            with path.open("rb") as artifact:
                _check_artifact_file(os.fstat(artifact.fileno()))
                payload = artifact.read(MAX_LAUNCH_BYTES + 1)
            if len(payload) > MAX_LAUNCH_BYTES:
                raise HarnessLaunchError("launch_too_large")
            if hashlib.sha256(payload).hexdigest() != sha256:
                raise HarnessLaunchError("launch_artifact_invalid")
            document = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_fields,
                                  parse_constant=_invalid_constant)
            _check_json(document)
            if (type(document) is not dict or set(document) != {"version", "boot_settings", "policy"}
                    or type(document["version"]) is not int or document["version"] != 1):
                raise HarnessLaunchError("launch_artifact_invalid")
            policy = _LaunchPolicy.model_validate_json(_canonical(document["policy"]))
            inputs = FrozenLaunchInputs(boot_settings=document["boot_settings"],
                **{name: getattr(policy, name) for name in _LaunchPolicy.model_fields})
            if inputs._payload != payload:
                raise HarnessLaunchError("launch_artifact_invalid")
            return inputs
        except HarnessLaunchError as error:
            if error.code == "launch_too_large":
                raise
            raise HarnessLaunchError("launch_artifact_invalid") from None
        except (OSError, TypeError, ValueError, KeyError, OverflowError, RecursionError):
            raise HarnessLaunchError("launch_artifact_invalid") from None
