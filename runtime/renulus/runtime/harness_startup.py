# SPDX-License-Identifier: MIT
"""Explicit developer startup on the serving loop, under the real profile issuer.

The normal launcher keeps its existing path. This entry requires an immutable
policy and observed registry before serving; absent deployment evidence grants
no inference. Boot settings come only from the policy's launch artifact.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, fields
import json
import math
from pathlib import Path
import re

from fastapi import FastAPI

from renulus.contracts import ApiError
from .harness_bootstrap import HarnessBootstrap
from .harness_configuration import ConfigurationAuthority, ConfigurationSpec
from .harness_launch import HarnessLaunchError, LaunchArtifactStore
from .harness_process import HarnessProcessConfig
from .harness_profile_owner import ProfileOwnerScope, acquire_profile_owner


MAX_STARTUP_BYTES = 262144
_PATH_FIELDS = ('node_executable', 'host_entry', 'profile_root')
_IDENTITY_FIELDS = ('profile_id', 'store_id', 'domain_store_id')
_REQUIRED_PROCESS = frozenset((*_PATH_FIELDS, *_IDENTITY_FIELDS, 'domain_path'))
_PROCESS_FIELDS = frozenset(field.name for field in fields(HarnessProcessConfig))


def _invalid():
    return ApiError('harness_startup_invalid', 'The explicit harness startup configuration is invalid.', 409)


@dataclass(frozen=True)
class HarnessStartupOptions:
    scope: ProfileOwnerScope
    config: HarnessProcessConfig
    artifact_root: Path
    candidate_root: Path
    attempt_timeout: float
    initialize_new: bool = False
    initial_spec: ConfigurationSpec | None = None

    def __post_init__(self):
        config, scope = self.config, self.scope
        if (type(config) is not HarnessProcessConfig or type(scope) is not ProfileOwnerScope
                or scope != ProfileOwnerScope(config.profile_root, config.profile_id,
                    config.domain_store_id, config.store_id)
                or config.domain_path != 'state/renulus.sqlite3' or config.boot_settings != {}
                or type(self.initialize_new) is not bool
                or (self.initial_spec is not None and type(self.initial_spec) is not ConfigurationSpec)
                or type(self.attempt_timeout) not in (int, float)
                or not math.isfinite(self.attempt_timeout) or not 0 < self.attempt_timeout <= 300):
            raise _invalid()
        for name in _IDENTITY_FIELDS:
            value = getattr(config, name)
            if type(value) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', value) is None:
                raise _invalid()
        for path in (scope.root, config.node_executable, config.host_entry,
                     self.artifact_root, self.candidate_root):
            if (not isinstance(path, Path) or not path.is_absolute()
                    or path == Path(path.anchor) or path.resolve() != path):
                raise _invalid()
        if (self.candidate_root.is_relative_to(scope.root)
                or scope.root.is_relative_to(self.candidate_root)):
            raise _invalid()
        for name in _PROCESS_FIELDS - _REQUIRED_PROCESS - {'boot_settings', 'start_timeout'}:
            value = getattr(config, name)
            if type(value) is not int or value <= 0:
                raise _invalid()
        if (type(config.start_timeout) not in (int, float)
                or not math.isfinite(config.start_timeout) or config.start_timeout <= 0):
            raise _invalid()
        try:
            LaunchArtifactStore(self.artifact_root, live_root=scope.root, candidate_root=self.candidate_root)
        except HarnessLaunchError:
            raise _invalid() from None


def _unique_fields(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise _invalid()
        result[name] = value
    return result


def load_startup_options(path: Path, *, profile: Path) -> HarnessStartupOptions:
    """Read bounded explicit metadata; no app, profile, credential or engine writes."""
    try:
        if not isinstance(path, Path) or not path.is_absolute():
            raise _invalid()
        with path.open('rb') as source:
            raw = source.read(MAX_STARTUP_BYTES + 1)
        if len(raw) > MAX_STARTUP_BYTES:
            raise _invalid()
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_fields,
            parse_constant=lambda value: (_ for _ in ()).throw(_invalid()))
        required = {'version', 'process', 'artifact_root', 'candidate_root', 'attempt_timeout'}
        if (type(data) is not dict or not required <= set(data)
                or set(data) - required - {'initialize_new', 'initial_spec'}
                or type(data['version']) is not int or data['version'] != 1):
            raise _invalid()
        process = data['process']
        if (type(process) is not dict or not _REQUIRED_PROCESS <= set(process)
                or set(process) - _PROCESS_FIELDS
                or any(type(process[name]) is not str for name in _PATH_FIELDS)):
            raise _invalid()
        config = HarnessProcessConfig(**{**process,
            **{name: Path(process[name]) for name in _PATH_FIELDS}})
        if not isinstance(profile, Path) or config.profile_root != profile:
            raise _invalid()
        if any(type(data[name]) is not str for name in ('artifact_root', 'candidate_root')):
            raise _invalid()
        spec = data.get('initial_spec')
        if spec is not None:
            if type(spec) is not dict:
                raise _invalid()
            spec = ConfigurationSpec.model_validate_json(json.dumps(spec, allow_nan=False))
        scope = ProfileOwnerScope(profile, config.profile_id, config.domain_store_id, config.store_id)
        return HarnessStartupOptions(scope, config, Path(data['artifact_root']),
            Path(data['candidate_root']), data['attempt_timeout'], data.get('initialize_new', False), spec)
    except ApiError:
        raise
    except (OSError, TypeError, ValueError, KeyError, OverflowError, RecursionError):
        raise _invalid() from None


def create_managed_app(options: HarnessStartupOptions, *, token: str | None = None,
                       source_root: Path | None = None, model_registry_factory=None,
                       prepare_startup=None, provider_http_transport=None) -> FastAPI:
    """Call in a dedicated Windows Python process; the issuer lives until exit.

    Trusted assembly may prepare an initial policy on the serving loop using
    the already-bound app/lease/authority/store. The CLI never injects it. That
    callback and an explicit initial_spec are mutually exclusive.
    """
    if (type(options) is not HarnessStartupOptions
            or (prepare_startup is not None and (not callable(prepare_startup) or options.initial_spec is not None))):
        raise _invalid()
    options.__post_init__()
    if not options.config.node_executable.is_file() or not options.config.host_entry.is_file():
        raise _invalid()
    lease = acquire_profile_owner(options.scope, initialize_new=options.initialize_new)
    bootstrap = HarnessBootstrap(options.scope, profile_owner=lease)
    app = bootstrap.create_app(token=token, source_root=source_root,
        provider_http_transport=provider_http_transport)
    services = app.state.services
    authority = ConfigurationAuthority(services.db)
    provider = services.get('provider')
    store = LaunchArtifactStore(options.artifact_root, live_root=options.scope.root,
        candidate_root=options.candidate_root)
    app.state.harness_bootstrap = bootstrap
    app.state.harness_configuration_authority = authority
    app.state.harness_bootstrap_result = None
    app.state.harness_bootstrap_runtime = None

    def assemble(spec, inputs, issuer):
        from .harness_bootstrap_runtime import ManagedBootstrapRuntime
        runtime = ManagedBootstrapRuntime(spec, inputs, issuer, services=services,
            authority=authority, config=options.config, launch_store=store,
            candidate_root=options.candidate_root, attempt_timeout=options.attempt_timeout,
            model_registry_factory=model_registry_factory)
        app.state.harness_bootstrap_runtime = runtime
        return runtime

    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        try:
            spec = options.initial_spec
            if prepare_startup is not None:
                spec = await prepare_startup(application, lease, authority, store)
                if spec is not None and type(spec) is not ConfigurationSpec:
                    raise _invalid()
            result = await bootstrap.start(authority=authority, provider=provider,
                launch_store=store, assemble_runtime=assemble, initial_spec=spec)
            application.state.harness_bootstrap_result = result
            if not result.admission_open:
                raise ApiError('configuration_not_active',
                    'This explicit harness startup requires a selected connection and validated policy.', 409, True)
            async with original(application) as state:
                yield state
        finally:
            # Also covers bootstrap/ordinary-startup failure before original
            # lifespan reaches its yield. Never release the issuer or its job.
            await services.finish_shutdown()

    app.router.lifespan_context = lifespan
    return app
