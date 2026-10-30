# SPDX-License-Identifier: MIT
"""Desktop assembly of the existing native learning runtime.

The desktop owns its profile singleton before entering here. Credentials and
subscription selection belong to ProviderManager. Native activation is lazy;
opening a fresh app never requires an account or makes an inference request.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import hashlib
from pathlib import Path
import re
from uuid import uuid4

import httpx

from renulus.contracts import ApiError
from .harness_bootstrap import HarnessBootstrap
from .harness_bootstrap_runtime import ManagedBootstrapRuntime
from .harness_configuration import (AttemptPolicy, ChildPolicy, ConfigurationAuthority,
    ContextPolicy, PURPOSES, RolePolicy, RouteLimits)
from .harness_deployment import DeploymentEvidence
from .harness_gateway import GatewayBounds
from .harness_launch import FrozenLaunchInputs, LaunchArtifactStore, finish_spec
from .harness_model_registry import HarnessModelRegistry, ModelRegistryBounds
from .harness_process import HarnessProcessConfig, ManagedHarnessProcess
from .harness_profile_owner import ProfileOwnerScope, acquire_profile_owner


NODE = Path('C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe')


def native_entry(source):
    """A staged backend bundle (packaging/backend_bundle.py) carries its pinned Node
    and closed-graph launcher; a source checkout keeps the reviewed developer Node."""
    if (source / 'backend-bundle.json').is_file():
        return source / 'node/node.exe', source / 'harness-launch.mjs'
    return NODE, source / 'packages/harness/src/main.mjs'
# Deliberate app policy, NOT vendor limits, an exact tokenizer or account evidence.
# Each UTF-8 content byte costs one local unit, plus generous framing reserves.
INPUT_BUDGET = 49152
OUTPUT_BUDGET = 4096
WINDOW_BUDGET = 57344
DISPATCH_BUDGET = 12
POLICY_REVISION = 'renulus_desktop_local_text_budget_v1'


async def local_text_budget(_body, manifest):
    """Budget structured content, never raw request JSON or encoded media.

    This deliberately restrictive text policy is independent of any vendor's
    tokenization/capacity. Provider context rejection remains visible. Images
    require separately verified accounting and are refused by this text path.
    """
    def size(value):
        return len(value.encode('utf-8'))

    units = 4096 + size(manifest.system)
    for message in manifest.messages:
        units += 256 + size(message.role)
        for part in message.content:
            if part.type == 'image':
                raise ApiError('desktop_image_budget_unavailable',
                    'This learning runtime currently supports text and Library tools. Image accounting is not configured.', 409)
            units += 128
            for field in ('text', 'id', 'name', 'arguments_json', 'output_text'):
                value = getattr(part, field, None)
                if value is not None:
                    units += size(value)
    for tool in manifest.tools:
        units += 1024 + size(tool.name) + size(tool.description) + size(tool.parameters_json)
    return units


def _http_transport(_route):
    # Each dispatch owns and closes its own real transport; no implicit retries.
    return httpx.AsyncHTTPTransport(retries=0, trust_env=False)


class DesktopHarness:
    def __init__(self, app, bootstrap, config, lease, store, candidate_root):
        self.app, self.bootstrap, self.config, self.lease = app, bootstrap, config, lease
        self.services = app.state.services
        self.provider = self.services.get('provider')
        self.authority = ConfigurationAuthority(self.services.db)
        self.store, self.candidate_root = store, candidate_root
        self.task = None
        self.bootstrap_started = False
        self.connection = self.route = self.evidence = None
        self.services.on_shutdown.append(self.settle_activation)
        app.state.harness_bootstrap = bootstrap
        app.state.harness_configuration_authority = self.authority
        app.state.harness_bootstrap_runtime = None
        app.state.harness_bootstrap_result = None

    def has_native_history(self, identifier):
        with self.services.db.transaction() as conn:
            return conn.execute('SELECT 1 FROM learn_harness_mappings WHERE thread_id=?',
                (identifier,)).fetchone() is not None

    async def ensure(self):
        if self.services.stopping:
            raise ApiError('runtime_stopping', 'Renulus is closing this profile.', 503, True)
        if self.task is None:
            # Local check before retaining a task: a no-account Send can be
            # retried after connecting, without restarting or falling to Hermes.
            if self.provider.connections()['selected_provider'] is None:
                raise ApiError('connection_required', 'Connect and select a subscription in Settings before sending.', 409)
            self.task = asyncio.create_task(self._activate(), name='renulus-desktop-harness')
            self.task.add_done_callback(lambda task: None if task.cancelled() else task.exception())
        try:
            await asyncio.shield(self.task)
        except Exception as error:
            if not self.bootstrap_started:
                self.task = None  # Connection preparation can be retried safely.
                if isinstance(error, ApiError):
                    raise
                raise ApiError('desktop_harness_startup_failed',
                    'The native learning runtime could not start. Check this installation and retry.', 503, True) from None
            raise ApiError('desktop_harness_restart_required',
                'The learning runtime could not activate. Close and reopen Renulus, then retry.', 503, True) from None
        try:
            self.provider.require_configuration_connection(self.connection)
        except ApiError:
            raise ApiError('desktop_harness_reconnect_required',
                'The selected model or connection changed. Reconnect if needed, then close and reopen Renulus to apply it.',
                409, True) from None

    async def settle_activation(self):
        if self.task is not None:
            await asyncio.gather(asyncio.shield(self.task), return_exceptions=True)

    async def _registry_hash(self):
        process = ManagedHarnessProcess()
        identity = 'desktop-inspect-' + uuid4().hex
        config = replace(self.config, profile_root=self.candidate_root / identity,
            profile_id=identity, store_id=identity + '-runtime', domain_store_id=identity + '-domain')
        try:
            await process.start(config)
            native = process.native_identity()
            self.lease.register_native(native.pid, generation=native.generation)
            async with asyncio.timeout(60):
                result = await process.request('host.inspect', {}, identity, '1', 30)
                while result['outcome'] == 'accepted_pending':
                    await asyncio.sleep(.02)
                    result = await process.query_result(result['request_id'])
                if result['outcome'] != 'committed_reference':
                    raise ApiError('desktop_harness_registry_unavailable', 'The native learning tools could not be inspected.', 503, True)
                observed = result['result']
                if (not re.fullmatch(r'[a-f0-9]{64}', observed.get('registry_hash', ''))
                        or any(observed.get(key) is not False for key in ('generation_open', 'recovery_open',
                            'package_acquisition_open', 'mcp_startup_open', 'live_store_writer'))
                        or {tool['name'] for tool in observed['registry']} != {
                            'renulus_library_retrieve', 'renulus_library_citation'}):
                    raise ApiError('desktop_harness_registry_mismatch', 'The native learning tool registry did not match.', 409)
                await process.release_observation(result['request_id'])
                return observed['registry_hash']
        finally:
            while True:
                await process.close(1)
                if (await process.settlement(1))['state'] == 'settled' and process.domain_status()['active'] == 0:
                    break

    async def _activate(self):
        # Normal desktop only: existing protected app credentials, no fixture
        # account, catalogue probe, environment credential or fallback model.
        self.route = await self.provider.prepare_harness_route()
        self.connection = self.provider.configuration_connection()
        registry_hash = await self._registry_hash()
        self.provider.require_configuration_connection(self.connection)
        inputs = FrozenLaunchInputs(boot_settings={}, connection=self.connection,
            roles=tuple(RolePolicy(purpose=purpose, enabled=purpose == 'explain',
                model_id=self.route.catalog_model_id, output_tokens=OUTPUT_BUDGET,
                dispatch_limit=DISPATCH_BUDGET if purpose == 'explain' else 0)
                for purpose in sorted(PURPOSES)), inputs=(), capabilities=('text', 'tools'),
            context=ContextPolicy(requested_window_tokens=WINDOW_BUDGET, reserve_tokens=4096),
            attempts=AttemptPolicy(foreground_dispatches=DISPATCH_BUDGET,
                standalone_dispatches=0, title_dispatches=0, retries=0),
            children=ChildPolicy(max_depth=0, concurrency=0))
        self.store.save(inputs)
        # The existing dispatch adapter calls this record DeploymentEvidence.
        # Here its revisions explicitly identify local policy, not measured
        # provider limits/capabilities or an exact account tokenizer attestation.
        self.evidence = DeploymentEvidence(POLICY_REVISION, self.route,
            RouteLimits(input_tokens=INPUT_BUDGET, output_tokens=OUTPUT_BUDGET,
                window_tokens=WINDOW_BUDGET), ('text', 'tools'),
            POLICY_REVISION, 'renulus_desktop_text_tools_request_policy_v1',
            'renulus_structured_utf8_bytes_and_framing_policy_v1', local_text_budget)
        self.bootstrap_started = True
        result = await self.bootstrap.start(authority=self.authority, provider=self.provider,
            launch_store=self.store, assemble_runtime=self._assemble,
            initial_spec=finish_spec(inputs, registry_hash), replace_on_restart=True,
            defer_failure_cleanup=True)
        self.app.state.harness_bootstrap_result = result
        if not result.admission_open:
            raise ApiError('desktop_harness_not_active', 'The learning runtime could not activate. Reopen Renulus and retry.', 503, True)
        await self.services.get('memory').start()

    def _model_registry(self, resolve_run):
        def evidence(route):
            if replace(route, catalogue_listed=None) == replace(self.route, catalogue_listed=None):
                return self.evidence
            return None

        return HarnessModelRegistry(self.provider, self.authority, resolve_run=resolve_run,
            evidence=evidence, http_transport=_http_transport,
            gateway_bounds=GatewayBounds(max_request_bytes=1048576,
                max_response_bytes=2097152, timeout_seconds=300),
            bounds=ModelRegistryBounds(max_runs=3, max_plans_per_run=DISPATCH_BUDGET,
                max_owned=3, max_retained_bytes=16777216,
                max_manifest_bytes=1048576, max_frame_bytes=4194304))

    def _assemble(self, spec, inputs, issuer):
        runtime = ManagedBootstrapRuntime(spec, inputs, issuer, services=self.services,
            authority=self.authority, config=self.config, launch_store=self.store,
            candidate_root=self.candidate_root, attempt_timeout=60,
            model_registry_factory=self._model_registry)
        self.app.state.harness_bootstrap_runtime = runtime
        return runtime


def create_desktop_app(profile, *, token=None, source_root=None, provider_http_transport=None):
    root = Path(profile).expanduser().resolve()
    source = Path(source_root).resolve() if source_root else Path(__file__).resolve().parents[3]
    profile_id = 'desktop-' + hashlib.sha256(str(root).casefold().encode()).hexdigest()[:32]
    node, entry = native_entry(source)
    config = HarnessProcessConfig(node_executable=node.resolve(),
        host_entry=entry, profile_root=root,
        profile_id=profile_id, store_id=profile_id + '-runtime',
        domain_store_id=profile_id + '-domain', domain_path='state/renulus.sqlite3',
        max_frame_bytes=4194304, start_timeout=60)
    scope = ProfileOwnerScope(root, config.profile_id, config.domain_store_id, config.store_id)
    # This entry is used after Electron acquired the profile singleton. The
    # issuer mutex still fences concurrent Python/native owners before writes.
    lease = acquire_profile_owner(scope, initialize_new=True, adopt_legacy=True)
    bootstrap = HarnessBootstrap(scope, profile_owner=lease)
    app = bootstrap.create_app(token=token, source_root=source,
        provider_http_transport=provider_http_transport)
    # The native owner binds its committed-answer extractor once, before the
    # memory outbox worker starts. Lazy activation must preserve that ordering.
    memory = app.state.services.get('memory')
    app.state.services.on_startup.remove(memory.start)
    candidates = root.parent / (root.name + '.harness-candidates')
    store = LaunchArtifactStore(root.parent / (root.name + '.harness-launch'),
        live_root=root, candidate_root=candidates)
    owner = DesktopHarness(app, bootstrap, config, lease, store, candidates)
    app.state.desktop_harness = owner
    app.state.services.registry['desktop_harness'] = owner
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        try:
            async with original(application) as state:
                yield state
        finally:
            if owner.task is not None:
                await asyncio.gather(asyncio.shield(owner.task), return_exceptions=True)
            await bootstrap.close()
            await app.state.services.finish_shutdown()

    app.router.lifespan_context = lifespan
    return app
