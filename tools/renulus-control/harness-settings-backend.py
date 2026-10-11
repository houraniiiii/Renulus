# SPDX-License-Identifier: MIT
"""Fixed, source-only Settings fixture. Account/catalogue evidence is synthetic."""
from __future__ import annotations

import hashlib
import argparse
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import shutil
from uuid import uuid4

from renulus.contracts import ApiError

SOURCE = Path(__file__).resolve().parents[2]
NODE = Path('C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe').resolve()
MAX_DOCUMENT_BYTES = 262144


def _invalid():
    return ApiError('harness_settings_fixture_invalid', 'The fixed Settings fixture inputs are invalid.', 409)


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
    """Validate controller-derived metadata without provisioning a profile."""
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
        identity = 'synthetic-settings-' + directory.name
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


def provision_helpers(lease, helper_assets: Path, *, source_root: Path = SOURCE):
    """Provision reviewed bytes only under this process's actual issuer."""
    from renulus.runtime.harness_profile_owner import ProfileOwnerLease
    if type(lease) is not ProfileOwnerLease:
        raise _invalid()
    lease.require_predecessor(lease.predecessor)
    try:
        target = lease.scope.root / 'helpers'
        if (not isinstance(helper_assets, Path) or not isinstance(source_root, Path)
                or helper_assets.resolve() != helper_assets or source_root.resolve() != source_root
                or helper_assets.is_relative_to(lease.scope.root)
                or lease.scope.root.is_relative_to(helper_assets)):
            raise _invalid()
        expected_file = source_root / 'packaging/runtime/helper-assets.json'
        acquired_file = helper_assets / 'manifest.json'
        _no_links(expected_file)
        _no_links(acquired_file)
        _no_links(target, missing=True)
        expected, acquired = (_manifest(file) for file in (expected_file, acquired_file))
        if (json.dumps(expected, sort_keys=True) != json.dumps(acquired, sort_keys=True)
                or type(expected.get('version')) is not int or expected['version'] != 1
                or set(expected.get('groups', {})) != {'embedding', 'docling', 'ocr'}):
            raise _invalid()
        records, names, totals = [], set(), {}
        for name, group in expected['groups'].items():
            if not group.get('revision') or not group.get('source_url', '').startswith('https://') or not group.get('files'):
                raise _invalid()
            totals[name] = {'files': len(group['files']), 'bytes': 0, 'revision': group['revision']}
            for record in group['files']:
                relative = record.get('path')
                if (type(relative) is not str or not re.fullmatch(r'[A-Za-z0-9._/-]+', relative)
                        or any(part in ('', '.', '..') for part in relative.split('/'))
                        or relative.casefold() in names or type(record.get('size')) is not int
                        or record['size'] <= 0 or not re.fullmatch(r'[a-f0-9]{64}', record.get('sha256', ''))):
                    raise _invalid()
                names.add(relative.casefold())
                original, destination = helper_assets / relative, target / relative
                _no_links(original)
                _no_links(destination, missing=True)
                if not original.is_file() or original.stat().st_size != record['size'] or _digest(original) != record['sha256']:
                    raise _invalid()
                records.append((original, destination, record))
                totals[name]['bytes'] += record['size']
        # Every source is validated before the first destination write. Only
        # these retained reviewed records are copied, never a reloaded manifest.
        for original, destination, record in records:
            lease.require_predecessor(lease.predecessor)
            if destination.is_file() and destination.stat().st_size == record['size'] and _digest(destination) == record['sha256']:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging = destination.with_name(destination.name + '.copying')
            _no_links(staging, missing=True)
            shutil.copyfile(original, staging)
            if staging.stat().st_size != record['size'] or _digest(staging) != record['sha256']:
                raise _invalid()
            staging.replace(destination)
        staging = target / 'manifest.json.copying'
        _no_links(staging, missing=True)
        _no_links(target / 'manifest.json', missing=True)
        lease.require_predecessor(lease.predecessor)
        staging.write_text(json.dumps(expected, indent=2), encoding='utf-8')
        staging.replace(target / 'manifest.json')
        return {'status': 'copied-and-verified', 'groups': totals, 'target': str(target)}
    except ApiError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise _invalid() from None


def _manifest(file):
    with file.open('rb') as stream:
        raw = stream.read(MAX_DOCUMENT_BYTES + 1)
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise _invalid()
    value = json.loads(raw, object_pairs_hook=_unique,
        parse_constant=lambda value: (_ for _ in ()).throw(_invalid()))
    if type(value) is not dict:
        raise _invalid()
    return value


def _digest(file):
    digest = hashlib.sha256()
    with file.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def create_fixture_app(file: Path, digest: str, *, profile: Path, helper_assets: Path, token: str):
    """Use the original managed app and provider; substitute catalogue HTTP only."""
    import httpx
    from renulus.runtime.harness_startup import create_managed_app
    options = load_fixture_launch(file, digest, profile=profile, helper_assets=helper_assets)
    # The controller deliberately forwards no personal home. Import-time
    # default paths must remain in this session's sibling desktop namespace.
    os.environ['USERPROFILE'] = str(profile.parent / 'd/home')
    for name in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY', 'DO_NOT_TRACK'):
        os.environ[name] = '1'

    def catalogue(request):
        if request.method != 'GET' or not request.url.path.endswith('/models'):
            return httpx.Response(403, json={'error': {'code': 'synthetic_catalogue_only'}})
        return httpx.Response(200, json={'data': [{'id': 'mimo-v2.6-pro'}, {'id': 'deepseek-v4.1-flash'}]})

    async def prepare(app, lease, authority, store):
        provision_helpers(lease, helper_assets)
        if not options.initialize_new:
            return None
        snapshot = authority.activation_snapshot()
        if any(snapshot[key] is not None for key in ('effective', 'requested', 'activating')):
            raise _invalid()
        provider = app.state.services.get('provider')
        await provider.connect_go('synthetic_settings_fixture_never_networked_v1', select=True)
        provider.select('opencode-go', 'mimo-v2.6-pro')
        route = await provider.prepare_harness_route()
        registry_hash = await _inspect_initial_registry(app.state.services, lease, options)
        from renulus.runtime.harness_configuration import (PURPOSES, RolePolicy, ConnectionReference,
            ContextPolicy, AttemptPolicy, ChildPolicy)
        from renulus.runtime.harness_launch import FrozenLaunchInputs, finish_spec
        frozen = FrozenLaunchInputs(boot_settings={},
            connection=ConnectionReference(provider=route.provider_id, credential_reference=route.credential_ref,
                credential_revision=route.credential_epoch, selected_model=route.catalog_model_id),
            roles=tuple(RolePolicy(purpose=purpose, enabled=purpose != 'title', output_tokens=64)
                for purpose in sorted(PURPOSES)), inputs=(), capabilities=('text', 'tools'),
            context=ContextPolicy(requested_window_tokens=640, reserve_tokens=8),
            attempts=AttemptPolicy(foreground_dispatches=3, retries=0), children=ChildPolicy())
        spec = finish_spec(frozen, registry_hash)
        lease.require_predecessor(lease.predecessor)
        provider.require_configuration_connection(spec.connection)
        store.save(frozen)
        return spec

    return create_managed_app(options, token=token, source_root=SOURCE,
        prepare_startup=prepare, provider_http_transport=httpx.MockTransport(catalogue))


async def _inspect_initial_registry(services, lease, options):
    """Read the actual closed native registry, then retain it through settlement."""
    from renulus.runtime.harness_process import ManagedHarnessProcess
    process = ManagedHarnessProcess()
    suffix = uuid4().hex
    config = replace(options.config, profile_root=options.candidate_root / ('initial-' + suffix),
        profile_id='initial-' + suffix, store_id='initial-runtime-' + suffix,
        domain_store_id='initial-domain-' + suffix)
    draining = None

    async def settle():
        while True:
            await process.close(1)
            if ((await process.settlement(1))['state'] == 'settled'
                    and process.domain_status()['active'] == 0):
                return

    async def drain():
        nonlocal draining
        if draining is None:
            draining = asyncio.create_task(settle())
        cancelled = False
        while not draining.done():
            try:
                await asyncio.shield(draining)
            except asyncio.CancelledError:
                cancelled = True
            except BaseException:
                break
        if cancelled:
            if not draining.cancelled():
                draining.exception()
            raise asyncio.CancelledError
        draining.result()

    services.on_shutdown_dependencies.append(drain)
    try:
        lease.require_predecessor(lease.predecessor)
        await process.start(config)
        identity = process.native_identity()
        lease.register_native(identity.pid, generation=identity.generation)
        deadline = asyncio.get_running_loop().time() + options.attempt_timeout
        try:
            async with asyncio.timeout_at(deadline):
                result = await process.request('host.inspect', {}, 'settings-metadata-' + suffix, '1', options.attempt_timeout)
                while result['outcome'] == 'accepted_pending':
                    await asyncio.sleep(.02)
                    result = await process.query_result(result['request_id'])
                if result['outcome'] != 'committed_reference':
                    raise _invalid()
                await process.release_observation(result['request_id'])
        except TimeoutError:
            raise _invalid() from None
        observed = result['result']
        if (type(observed.get('registry_hash')) is not str
                or not re.fullmatch(r'[a-f0-9]{64}', observed['registry_hash'])
                or any(observed.get(key) is not False for key in ('generation_open', 'recovery_open',
                    'package_acquisition_open', 'mcp_startup_open', 'live_store_writer'))):
            raise _invalid()
        lease.require_predecessor(lease.predecessor)
        if asyncio.get_running_loop().time() >= deadline:
            raise _invalid()
        return observed['registry_hash']
    finally:
        await drain()


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
        raise SystemExit('The owned Settings fixture session is invalid.')
    app = create_fixture_app(args.harness_startup, args.harness_startup_sha256,
        profile=args.profile, helper_assets=args.helper_assets, token=token)
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False, log_level='warning')


if __name__ == '__main__':
    main()
