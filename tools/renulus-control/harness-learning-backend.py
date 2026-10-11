# SPDX-License-Identifier: MIT
"""Fixed learning-v1 source fixture; account, limits and counts are synthetic."""
from __future__ import annotations

import hashlib
import argparse
import asyncio
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from fastapi import FastAPI
import httpx

from renulus.contracts import ApiError

SOURCE = Path(__file__).resolve().parents[2]
NODE = Path('C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe').resolve()
MAX_DOCUMENT_BYTES = 262144
MODEL = 'mimo-v2.6-pro'
CALL_ID = 'synthetic_learning_library_1'
_CREDENTIAL = 'synthetic_learning_fixture_never_networked_v1'
_ENDPOINT = 'https://opencode.ai/zen/go/v1/chat/completions'
_PATH = '/zen/go/v1/chat/completions'


def _invalid():
    return ApiError('harness_learning_fixture_invalid', 'The fixed learning fixture inputs are invalid.', 409)


def _no_links(file: Path, *, missing=False):
    for item in (file, *file.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            if missing:
                continue
            raise _invalid() from None
        if item.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise _invalid()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _invalid()
        result[key] = value
    return result


def load_fixture_launch(file: Path, digest: str, *, profile: Path, helper_assets: Path):
    """Validate the fixed controller document without acquiring or writing a profile."""
    from renulus.runtime.harness_startup import HarnessStartupOptions
    from renulus.runtime.harness_process import HarnessProcessConfig
    from renulus.runtime.harness_profile_owner import ProfileOwnerScope
    try:
        for location in (file, profile, helper_assets):
            if (not isinstance(location, Path) or not location.is_absolute()
                    or location.resolve() != location or location == Path(location.anchor)
                    or str(location).startswith(('\\', '//'))):
                raise _invalid()
        directory = profile.parent
        number = re.fullmatch(r'startup-([1-9][0-9]*)\.json', file.name)
        if (profile.name != 'p' or not re.fullmatch(r's-[a-f0-9]{8}', directory.name)
                or file.parent != directory / 'out' or number is None
                or type(digest) is not str or not re.fullmatch(r'[a-f0-9]{64}', digest)
                or helper_assets.is_relative_to(directory) or directory.is_relative_to(helper_assets)):
            raise _invalid()
        _no_links(file)
        _no_links(profile, missing=True)
        _no_links(helper_assets)
        if not helper_assets.is_dir() or not file.is_file():
            raise _invalid()
        with file.open('rb') as stream:
            raw = stream.read(MAX_DOCUMENT_BYTES + 1)
        if len(raw) > MAX_DOCUMENT_BYTES or hashlib.sha256(raw).hexdigest() != digest:
            raise _invalid()
        identity = 'synthetic-learning-' + directory.name
        process = {'node_executable': str(NODE), 'host_entry': str(SOURCE / 'packages/harness/src/main.mjs'),
            'profile_root': str(profile), 'profile_id': identity, 'store_id': identity + '-runtime',
            'domain_store_id': identity + '-domain', 'domain_path': 'state/renulus.sqlite3',
            'max_inflight': 1, 'max_domain_inflight': 1, 'max_frame_bytes': 65536, 'start_timeout': 45}
        expected = {'version': 1, 'process': process, 'artifact_root': str(directory / 'a'),
            'candidate_root': str(directory / 'k'), 'attempt_timeout': 45,
            'initialize_new': number.group(1) == '1'}
        data = json.loads(raw, object_pairs_hook=_unique,
            parse_constant=lambda value: (_ for _ in ()).throw(_invalid()))
        if json.dumps(data, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise _invalid()
        config = HarnessProcessConfig(**{**process, 'node_executable': NODE,
            'host_entry': SOURCE / 'packages/harness/src/main.mjs', 'profile_root': profile})
        scope = ProfileOwnerScope(profile, identity, identity + '-domain', identity + '-runtime')
        return HarnessStartupOptions(scope, config, directory / 'a', directory / 'k', 45,
            initialize_new=expected['initialize_new'])
    except ApiError:
        raise
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        raise _invalid() from None


class _LoopbackTransport(httpx.AsyncBaseTransport):
    """Keep exact official request bytes; only the external socket is remapped."""
    def __init__(self, fixture, route):
        self.fixture, self.route = fixture, route
        self.inner = httpx.AsyncHTTPTransport(retries=0)
        self.sent = self.finalized = False

    async def handle_async_request(self, request):
        self.fixture.require_route(self.route)
        if (self.sent or self.finalized or request.method != 'POST'
                or str(request.url) != _ENDPOINT
                or request.headers.get('authorization') != 'Bearer ' + _CREDENTIAL):
            raise _invalid()
        self.sent = True
        local = httpx.Request('POST', f'http://127.0.0.1:{self.fixture.port}{_PATH}',
            headers={key: value for key, value in request.headers.items() if key != 'host'},
            content=request.content)
        return await self.inner.handle_async_request(local)

    async def aclose(self):
        try:
            await self.inner.aclose()
        finally:
            self.finalized = True


class LearningFixture:
    """One owned loopback session; observations contain no bodies or protected refs."""
    def __init__(self):
        self.server = self.port = self.provider = self.authority = self.route = self.evidence = None
        self.handlers, self.transports = set(), []
        self.http_requests = self.completed = self.authenticated = self.counter_calls = self.errors = 0
        self.hashes = []
        self.listener_closed = False
        self.session_id = None
        self.query = None
        self._draining = None

    def observations(self) -> dict:
        return {'fixture': 'learning-v1', 'account_evidence': 'synthetic_learning_account_v1',
            'limits_evidence': 'synthetic_learning_immutable_limits_v1',
            'counter_evidence': 'synthetic_learning_inclusive_count_v1',
            'http_requests': self.http_requests, 'completed_http_requests': self.completed,
            'authenticated_requests': self.authenticated, 'counter_calls': self.counter_calls,
            'query_sha256': hashlib.sha256(self.query.encode()).hexdigest() if self.query is not None else None,
            'body_sha256': list(self.hashes), 'errors': self.errors, 'handlers': len(self.handlers),
            'finalized_transports': sum(transport.finalized for transport in self.transports),
            'listener_closed': self.listener_closed}

    def require_route(self, route):
        if (self.listener_closed or self.provider is None or self.route is None
                or replace(route, catalogue_listed=None) != replace(self.route, catalogue_listed=None)
                or route.endpoint != _ENDPOINT or route.catalog_model_id != MODEL):
            raise _invalid()
        self.provider.require_harness_route(route)

    def transport(self, route):
        self.require_route(route)
        if len(self.transports) >= 2:
            raise _invalid()
        result = _LoopbackTransport(self, route)
        self.transports.append(result)
        return result

    async def count(self, body, manifest):
        from jsonschema import validate
        self.require_route(self.route)
        if self.counter_calls >= 2:
            raise _invalid()
        tools = {tool.name: tool for tool in manifest.tools}
        if set(tools) != {'renulus_library_retrieve', 'renulus_library_citation'}:
            raise _invalid()
        query = self._prompt([message.model_dump(mode='json') for message in manifest.messages])
        validate({'query': query, 'limit': 1}, json.loads(tools['renulus_library_retrieve'].parameters_json))
        if self.query is not None and self.query != query:
            raise _invalid()
        self.query = query
        payload = json.loads(body)
        if (not manifest.system or payload.get('model') != MODEL or payload.get('stream') is not True
                or payload.get('max_completion_tokens') != 64):
            raise _invalid()
        if self.counter_calls:
            parts = [part for message in manifest.messages for part in message.content]
            calls = [part for part in parts if part.type == 'tool-call']
            results = [part for part in parts if part.type == 'tool-result']
            if (len(calls) != 1 or len(results) != 1 or calls[0].id != CALL_ID or results[0].id != CALL_ID
                    or calls[0].name != 'renulus_library_retrieve'
                    or json.loads(calls[0].arguments_json) != {'query': self.query, 'limit': 1}):
                raise _invalid()
            self._passage(json.loads(results[0].output_text))
        self.counter_calls += 1
        # Explicit synthetic inclusive attestations for system, native history,
        # schemas, tool call/result and provider framing. No tokenizer claim.
        return 260 if self.counter_calls == 2 else 200

    @staticmethod
    def _prompt(messages):
        """Read actual native input, never source coordinates or fixture scripts."""
        users = [message for message in messages if message.get('role') == 'user']
        if not users:
            raise _invalid()
        content = users[-1]['content']
        if isinstance(content, str):
            query = content
        elif (isinstance(content, list) and content and all(isinstance(part, dict)
                and part.get('type') == 'text' and isinstance(part.get('text'), str) for part in content)):
            query = '\n'.join(part['text'] for part in content)
        else:
            raise _invalid()
        if not query.strip() or len(query) > 16000:
            raise _invalid()
        return query

    @staticmethod
    def _passage(result):
        if (not isinstance(result, dict) or result.get('status') != 'ready'
                or not isinstance(result.get('passages'), list) or len(result['passages']) != 1):
            raise _invalid()
        passage = result['passages'][0]
        if (not isinstance(passage, dict) or not passage.get('id') or not passage.get('document_id')
                or not passage.get('document_revision') or not passage.get('locators')
                or not isinstance(passage.get('text'), str) or not passage['text'].strip()):
            raise _invalid()
        return passage

    async def serve(self, reader, writer):
        task = asyncio.current_task()
        self.handlers.add(task)
        try:
            async with asyncio.timeout(20):
                head = await reader.readuntil(b'\r\n\r\n')
                lines = head.decode('ascii').split('\r\n')
                headers = {}
                for line in lines[1:]:
                    if not line:
                        continue
                    name, value = line.split(':', 1)
                    if name.lower() in headers:
                        raise _invalid()
                    headers[name.lower()] = value.strip()
                size = int(headers['content-length'])
                if not 0 < size <= 32768 or lines[0] != f'POST {_PATH} HTTP/1.1':
                    raise _invalid()
                body = await reader.readexactly(size)
                self.http_requests += 1
                if self.http_requests > 2 or headers.get('authorization') != 'Bearer ' + _CREDENTIAL:
                    raise _invalid()
                self.authenticated += 1
                session = headers.get('x-opencode-session')
                if (not isinstance(session, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', session)
                        or self.session_id is not None and self.session_id != session):
                    raise _invalid()
                self.session_id = session
                self.require_route(self.route)
                payload = json.loads(body, object_pairs_hook=_unique)
                if payload.get('model') != MODEL or payload.get('stream') is not True:
                    raise _invalid()
                messages = payload['messages']
                if self._prompt(messages) != self.query:
                    raise _invalid()
                if self.http_requests == 1:
                    if any(message['role'] == 'tool' for message in messages):
                        raise _invalid()
                    delta = {'tool_calls': [{'index': 0, 'id': CALL_ID, 'type': 'function',
                        'function': {'name': 'renulus_library_retrieve',
                            'arguments': json.dumps({'query': self.query, 'limit': 1})}}]}
                    finish = 'tool_calls'
                else:
                    tools = [message for message in messages if message['role'] == 'tool']
                    calls = [call for message in messages for call in message.get('tool_calls', [])]
                    if (len(tools) != 1 or tools[0].get('tool_call_id') != CALL_ID
                            or len(calls) != 1 or calls[0].get('id') != CALL_ID
                            or calls[0]['function']['name'] != 'renulus_library_retrieve'
                            or json.loads(calls[0]['function']['arguments']) != {'query': self.query, 'limit': 1}):
                        raise _invalid()
                    passage = self._passage(json.loads(tools[0]['content']))
                    excerpt = ' '.join(passage['text'].split()[:28])[:200]
                    delta, finish = {'content': 'Synthetic Library excerpt: ' + excerpt + ' [1].'}, 'stop'
                events = [{'id': 'synthetic_learning_response', 'model': MODEL,
                    'choices': [{'index': 0, 'delta': current, 'finish_reason': outcome}]}
                    for current, outcome in ((delta, None), ({}, finish))]
                response = (''.join('data: ' + json.dumps(event) + '\n\n' for event in events)
                    + 'data: [DONE]\n\n').encode()
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n'
                    + f'Content-Length: {len(response)}\r\nConnection: close\r\n\r\n'.encode() + response)
                await writer.drain()
                self.hashes.append(hashlib.sha256(body).hexdigest())
                self.completed += 1
        except Exception:
            self.errors += 1
            writer.write(b'HTTP/1.1 409 Conflict\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            finally:
                self.handlers.discard(task)

    async def close(self):
        if self._draining is None:
            self._draining = asyncio.create_task(self._close())
        await _join(self._draining)

    async def _close(self):
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
        if self.handlers:
            await asyncio.gather(*self.handlers)
        for transport in self.transports:
            if not transport.finalized:
                await transport.aclose()
        self.listener_closed = True


async def _join(task):
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except BaseException:
            break
    if cancelled:
        if not task.cancelled():
            task.exception()
        raise asyncio.CancelledError
    return task.result()


async def _registry_hash(services, lease, options):
    """Observe production main under the issuer, with all generation doors closed."""
    from renulus.runtime.harness_process import ManagedHarnessProcess
    suffix = uuid4().hex
    config = replace(options.config, profile_root=options.candidate_root / ('initial-' + suffix),
        profile_id='initial-' + suffix, store_id='initial-runtime-' + suffix,
        domain_store_id='initial-domain-' + suffix)
    process, draining = ManagedHarnessProcess(), None

    async def settle():
        while True:
            await process.close(1)
            if (await process.settlement(1))['state'] == 'settled' and process.domain_status()['active'] == 0:
                return

    async def drain():
        nonlocal draining
        if draining is None:
            draining = asyncio.create_task(settle())
        await _join(draining)

    services.on_shutdown_dependencies.append(drain)
    try:
        lease.require_predecessor(lease.predecessor)
        await process.start(config)
        identity = process.native_identity()
        lease.register_native(identity.pid, generation=identity.generation)
        deadline = asyncio.get_running_loop().time() + options.attempt_timeout
        async with asyncio.timeout_at(deadline):
            result = await process.request('host.inspect', {}, 'learning-metadata-' + suffix, '1',
                options.attempt_timeout)
            while result['outcome'] == 'accepted_pending':
                await asyncio.sleep(.02)
                result = await process.query_result(result['request_id'])
            if result['outcome'] != 'committed_reference':
                raise _invalid()
            observed = result['result']
            if (not re.fullmatch(r'[a-f0-9]{64}', observed.get('registry_hash', ''))
                    or any(observed.get(key) is not False for key in ('generation_open', 'recovery_open',
                        'package_acquisition_open', 'mcp_startup_open', 'live_store_writer'))
                    or {item['name'] for item in observed['registry']} != {
                        'renulus_library_retrieve', 'renulus_library_citation'}):
                raise _invalid()
            if await process.release_observation(result['request_id']) is not True:
                raise _invalid()
            lease.require_predecessor(lease.predecessor)
            if asyncio.get_running_loop().time() >= deadline:
                raise _invalid()
    except ApiError:
        raise
    except Exception:
        raise _invalid() from None
    finally:
        await drain()
    lease.require_predecessor(lease.predecessor)
    if asyncio.get_running_loop().time() >= deadline:
        raise _invalid()
    return observed['registry_hash']


def create_fixture_app(file: Path, digest: str, *, profile: Path, helper_assets: Path, token: str) -> FastAPI:
    """Use the original app/provider/native registry; substitute only synthetic HTTP/evidence."""
    if type(token) is not str or not token.strip():
        raise _invalid()
    from renulus.runtime.harness_startup import create_managed_app
    options = load_fixture_launch(file, digest, profile=profile, helper_assets=helper_assets)
    for name in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY', 'DO_NOT_TRACK'):
        os.environ[name] = '1'
    shared_spec = importlib.util.spec_from_file_location('learning_shared_helpers',
        SOURCE / 'tools/renulus-control/harness-settings-backend.py')
    shared = importlib.util.module_from_spec(shared_spec)
    shared_spec.loader.exec_module(shared)
    fixture = LearningFixture()

    def catalogue(request):
        if (request.method != 'GET' or str(request.url) != 'https://opencode.ai/zen/go/v1/models'
                or request.headers.get('authorization') != 'Bearer ' + _CREDENTIAL):
            return httpx.Response(409, json={'error': {'code': 'synthetic_learning_catalogue_only'}})
        return httpx.Response(200, json={'data': [{'id': MODEL}]})

    async def prepare(app, lease, authority, store):
        from renulus.runtime.harness_configuration import (PURPOSES, RolePolicy, ContextPolicy,
            AttemptPolicy, ChildPolicy, RouteLimits)
        from renulus.runtime.harness_deployment import DeploymentEvidence
        from renulus.runtime.harness_launch import FrozenLaunchInputs, finish_spec
        shared.provision_helpers(lease, helper_assets)
        provider = app.state.services.get('provider')
        if options.initialize_new:
            snapshot = authority.activation_snapshot()
            if any(snapshot[key] is not None for key in ('effective', 'requested', 'activating')):
                raise _invalid()
            await provider.connect_go(_CREDENTIAL, select=True)
            provider.select('opencode-go', MODEL)
        connection = provider.configuration_connection()
        if connection is None or connection.provider != 'opencode-go' or connection.selected_model != MODEL:
            raise _invalid()
        route = await provider.prepare_harness_route()
        registry_hash = await _registry_hash(app.state.services, lease, options)
        lease.require_predecessor(lease.predecessor)
        provider.require_configuration_connection(connection)
        frozen = FrozenLaunchInputs(boot_settings={}, connection=connection,
            roles=tuple(RolePolicy(purpose=purpose, enabled=purpose == 'explain', model_id=MODEL,
                output_tokens=64, dispatch_limit=2 if purpose == 'explain' else 0)
                for purpose in sorted(PURPOSES)), inputs=(), capabilities=('text', 'tools'),
            context=ContextPolicy(requested_window_tokens=640, reserve_tokens=8),
            attempts=AttemptPolicy(foreground_dispatches=2, standalone_dispatches=0, title_dispatches=0, retries=0),
            children=ChildPolicy(max_depth=0, concurrency=0))
        spec = finish_spec(frozen, registry_hash)
        if options.initialize_new:
            store.save(frozen)
        else:
            effective = authority.activation_snapshot()['effective']
            if effective is None or authority.configuration(effective) != spec or store.load(frozen.sha256) != frozen:
                raise _invalid()
        fixture.provider, fixture.authority, fixture.route = provider, authority, route
        fixture.evidence = DeploymentEvidence('synthetic_learning_account_v1', route,
            RouteLimits(input_tokens=512, output_tokens=64, window_tokens=640), ('text', 'tools'),
            'synthetic_learning_immutable_limits_v1', 'synthetic_learning_capabilities_v1',
            'synthetic_learning_inclusive_count_v1', fixture.count)
        fixture.server = await asyncio.start_server(fixture.serve, '127.0.0.1', 0, limit=65536)
        fixture.port = fixture.server.sockets[0].getsockname()[1]
        # Dependencies drain in reverse registration order. Owner is installed
        # later, so it drains native/registry work before this listener joins.
        app.state.services.on_shutdown_dependencies.append(fixture.close)
        return spec if options.initialize_new else None

    def factory(resolve_run):
        from renulus.runtime.harness_gateway import GatewayBounds
        from renulus.runtime.harness_model_registry import HarnessModelRegistry, ModelRegistryBounds
        fixture.require_route(fixture.route)
        return HarnessModelRegistry(fixture.provider, fixture.authority, resolve_run=resolve_run,
            evidence=lambda route: fixture.evidence if replace(route, catalogue_listed=None)
                == replace(fixture.route, catalogue_listed=None) else None, http_transport=fixture.transport,
            gateway_bounds=GatewayBounds(max_request_bytes=32768, max_response_bytes=8192, timeout_seconds=20),
            bounds=ModelRegistryBounds(max_runs=1, max_plans_per_run=2, max_owned=1,
                max_retained_bytes=500000, max_manifest_bytes=32768, max_frame_bytes=65536))

    app = create_managed_app(options, token=token, source_root=SOURCE, prepare_startup=prepare,
        provider_http_transport=httpx.MockTransport(catalogue), model_registry_factory=factory,
        collection_root=profile / 'library/collection')
    app.state.learning_fixture = fixture
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--harness-startup', type=Path, required=True)
    parser.add_argument('--harness-startup-sha256', required=True)
    parser.add_argument('--helper-assets', type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get('RENULUS_SESSION_TOKEN')
    if not token or not 0 < args.port < 65536:
        raise SystemExit('The owned learning-v1 fixture session is invalid.')
    app = create_fixture_app(args.harness_startup, args.harness_startup_sha256,
        profile=args.profile, helper_assets=args.helper_assets, token=token)
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False, log_level='warning')


if __name__ == '__main__':
    main()
