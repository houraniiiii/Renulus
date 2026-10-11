"""Narrow local product API. Hermes is the sole generative agent foundation."""
import argparse
import importlib
import os
from pathlib import Path
import secrets
from contextlib import asynccontextmanager
import inspect
import asyncio
import json
import re

from anyio import BrokenResourceError, ClosedResourceError, EndOfStream
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import __version__
from .contracts import API_VERSION, ApiError
from .services import Services
from .storage import AppPaths, Database
from .storage.database import SUPPORTED_SCHEMA
from .storage.assessment_policy import policy_snapshot, require_assistance

MODULE_ORDER = ("runtime", "content", "knowledge", "retrieval", "learn", "cases",
                "assessment", "memory", "study", "updates")
SHUTDOWN_CONTROL_PATHS = frozenset(('/api/v1/health', '/api/v1/meta',
    '/api/v1/runtime/status', '/api/v1/runtime/shutdown'))


class _RequestOwnership:
    """Keep admitted handlers alive through real work after a client leaves."""
    def __init__(self, app, services):
        self.app, self.services = app, services

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'] in SHUTDOWN_CONTROL_PATHS:
            return await self.app(scope, receive, send)
        interrupted = False
        disconnected = False
        receivers = set()

        def interrupt():
            nonlocal interrupted
            interrupted = True
            for receiver in tuple(receivers):
                receiver.cancel()

        async def owned_receive():
            if interrupted:
                return {'type': 'http.disconnect'}
            receiver = asyncio.current_task()
            receivers.add(receiver)
            try:
                # Preserve Request.is_disconnected()'s nonblocking receive.
                return await receive()
            except asyncio.CancelledError:
                if interrupted:
                    return {'type': 'http.disconnect'}
                raise
            except (BrokenResourceError, ClosedResourceError, EndOfStream):
                return {'type': 'http.disconnect'}
            finally:
                receivers.discard(receiver)

        async def owned_send(message):
            nonlocal disconnected
            if not disconnected:
                try:
                    await send(message)
                except (BrokenResourceError, ClosedResourceError, OSError):
                    disconnected = True
                    interrupt()

        try:
            task = self.services.admit_request(lambda: self.app(scope, owned_receive, owned_send), interrupt)
        except ApiError as error:
            response = JSONResponse({'error': {'code': error.code, 'message': error.message,
                'retryable': error.retryable}}, status_code=error.status, headers={'Cache-Control': 'no-store'})
            return await response(scope, receive, send)
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            disconnected = True
            interrupt()
            raise  # Only the observer leaves; Services still owns the handler.


def create_app(profile: str | Path, token: str | None = None, source_root=None) -> FastAPI:
    paths = AppPaths.create(profile, source_root)
    # Check the complete installed migration inventory before repositories or
    # startup hooks can write feature records. The ledger is also a compatibility
    # boundary within schema 2, not merely an idempotency mechanism.
    inventory = {"storage-recovery-001": (Path(__file__).parent / "storage" /
        "recovery_schema.sql").read_text(encoding="utf-8")}
    for name in MODULE_ORDER:
        module_path = Path(__file__).parent / name
        schema = module_path / "schema.sql"
        if schema.exists():
            inventory[f"{name}-001"] = schema.read_text(encoding="utf-8")
        for migration in sorted((module_path / "migrations").glob("*.sql")):
            inventory[f"{name}-{migration.stem}"] = migration.read_text(encoding="utf-8")
    services = Services(paths, Database(paths.database, migration_inventory=inventory))
    @asynccontextmanager
    async def lifespan(app):
        for callback in services.on_startup:
            result = callback()
            if inspect.isawaitable(result):
                await result
        try:
            yield
        finally:
            await services.finish_shutdown()

    app = FastAPI(title="Renulus local API", version=__version__, docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.services = services
    app.state.session_token = token
    # Inside authentication/policy middleware, outside the actual route handler.
    app.add_middleware(_RequestOwnership, services=services)

    def reconcile_attempts():
        owner = services.registry.get("whole_attempts")
        if owner is not None:
            owner.reconcile_all()

    def needs_assistance(request):
        path = request.url.path
        if path in ("/api/v1/health", "/api/v1/meta", "/api/v1/assessment/policy",
                    "/api/v1/runtime/status", "/api/v1/runtime/shutdown",
                    "/api/v1/data/recovery", "/api/v1/home/preferences"):
            return False
        if path in ("/api/v1/nightly", "/api/v1/nightly/preferences") and request.method in {"GET", "PUT"}:
            return False  # Safe settings/status allow Off while a Test is active.
        if path.startswith(("/api/v1/connections", "/api/v1/retrieval/connections",
                            "/api/v1/assessment/test-attempts")):
            return False  # Attempt owner gates every help/replay operation.
        if request.method == "DELETE" and path.startswith(("/api/v1/runtime/runs/", "/api/v1/data/backup/preview/")):
            return False
        if request.method == "POST" and re.fullmatch(
                r"/api/v1/conversations/(?:learning|case)/[A-Za-z0-9_-]{1,128}/runs/[A-Za-z0-9_-]{1,128}/cancel", path):
            return False
        if request.method == "POST" and re.fullmatch(
                r"/api/v1/assessment/generation/jobs/[A-Za-z0-9_-]{1,128}/cancel", path):
            return False  # Owner always returns only {id, state}, even on replay.
        if request.method == "POST" and re.fullmatch(
                r"/api/v1/assessment/imports/[A-Za-z0-9_-]{1,128}/cancel", path):
            return False  # The import owner returns only {id, state}.
        if request.method == "POST" and re.fullmatch(
                r"/api/v1/nightly/jobs/[A-Za-z0-9_-]{1,128}/cancel", path):
            return False
        if request.method == "GET" and re.fullmatch(
                r"/api/v1/conversations/(?:learning|case)/[A-Za-z0-9_-]{1,128}/runs", path):
            return False  # List contains only run IDs, states and a bounded cursor.
        if request.method == "GET" and request.query_params.get("neutral") == "true" and re.fullmatch(
                r"/api/v1/conversations/(?:learning|case)/[A-Za-z0-9_-]{1,128}/runs/[A-Za-z0-9_-]{1,128}", path):
            return False  # Producer guarantees exactly {run_id, state}.
        if request.method in {"GET", "POST"} and re.fullmatch(
                r"/api/v1/conversations/test-drafts/runs/[A-Za-z0-9_-]{1,128}"
                + (r"/cancel" if request.method == "POST" else ""), path):
            return False  # Volatile producer always returns exactly {run_id, state}.
        return path.startswith("/api/v1/")

    def captured_policy(expected=None):
        with services.db.transaction() as conn:
            return require_assistance(conn, expected_revision=expected)

    def captured_help(context):
        from .storage.study_help import require_context_in
        with services.db.transaction() as conn:
            return require_context_in(services, conn, context)

    def policy_error(error):
        return JSONResponse({"error": {"code": error.code, "message": error.message,
            "retryable": error.retryable}}, status_code=error.status, headers={"Cache-Control": "no-store"})

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        host = (request.headers.get("host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost", "testserver"):
            return JSONResponse({"error": {"code": "invalid_host", "message": "Local access only",
                                           "retryable": False}}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != "null":
            from urllib.parse import urlparse
            if urlparse(origin).hostname not in ("localhost", "127.0.0.1"):
                return JSONResponse({"error": {"code": "invalid_origin",
                    "message": "Local app origin required", "retryable": False}}, status_code=403)
        if (token and request.url.path != "/api/v1/health") or request.url.path == '/api/v1/runtime/shutdown':
            supplied = request.headers.get("x-renulus-token", "")
            if not token or not secrets.compare_digest(supplied, token):
                return JSONResponse({"error": {"code": "invalid_session",
                    "message": "Reconnect the application", "retryable": True}}, status_code=401)
        if request.url.path in SHUTDOWN_CONTROL_PATHS:
            return await call_next(request)
        if services.stopping:
            return policy_error(ApiError('runtime_stopping',
                'Renulus is closing this profile. Wait for local work to finish', 503, True))
        await asyncio.to_thread(reconcile_attempts)
        guarded = needs_assistance(request)
        try:
            revision = await asyncio.to_thread(captured_policy) if guarded else None
            from .storage.study_help import parse_context, require_context_in
            help_context = parse_context(request.headers.get('x-renulus-study-context') if guarded else None)
            if help_context is not None:
                await asyncio.to_thread(captured_help, help_context)
        except ApiError as error:
            return policy_error(error)
        from .storage.publication import bind_publication_guard
        if help_context is not None:
            with bind_publication_guard(services.db, lambda conn: require_context_in(services, conn, help_context)):
                response = await call_next(request)
        else:
            response = await call_next(request)
        if guarded:
            try:
                await asyncio.to_thread(captured_policy, revision)
                if help_context is not None:
                    await asyncio.to_thread(captured_help, help_context)
            except ApiError as error:
                await response.body_iterator.aclose()
                return policy_error(error)
            iterator = response.body_iterator
            async def guarded_body():
                try:
                    async for chunk in iterator:
                        try:
                            await asyncio.to_thread(captured_policy, revision)
                            if help_context is not None:
                                await asyncio.to_thread(captured_help, help_context)
                        except ApiError as error:
                            if response.headers.get("content-type", "").startswith("text/event-stream"):
                                yield ("event: error\ndata: " + json.dumps({"type": "error", "payload": {"code": error.code, "message": error.message, "retryable": error.retryable}}) + "\n\n").encode()
                            return
                        yield chunk
                finally:
                    await iterator.aclose()
            response.body_iterator = guarded_body()
        return response

    @app.exception_handler(ApiError)
    async def product_error(request: Request, error: ApiError):
        return JSONResponse({"error": {"code": error.code, "message": error.message,
            "retryable": error.retryable}}, status_code=error.status, headers={"Cache-Control": "no-store"})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        # Validation errors can include the submitted case payload; expose only field names.
        fields = [".".join(str(x) for x in item["loc"]) for item in error.errors()]
        return JSONResponse({"error": {"code": "invalid_request",
            "message": "Check the submitted fields: " + ", ".join(fields),
            "retryable": False}}, status_code=422, headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/health")
    def health():
        return {"status": "ready", "version": __version__, "api_version": API_VERSION,
                "schema_version": SUPPORTED_SCHEMA, "modules": services.capabilities}

    @app.get("/api/v1/meta")
    def meta():
        return {"version": __version__, "api_version": API_VERSION,
                "modules": services.capabilities}

    @app.get("/api/v1/assessment/policy")
    def assessment_policy():
        reconcile_attempts()
        with services.db.transaction() as conn:
            return policy_snapshot(conn)

    from .storage.api import create_router as data_router
    app.include_router(data_router(services), prefix="/api/v1")

    for name in MODULE_ORDER:
        module_path = Path(__file__).parent / name
        api_path = module_path / "api.py"
        if not api_path.exists():
            services.capabilities[name] = {"status": "not-installed"}
            continue
        schema = module_path / "schema.sql"
        if schema.exists():
            services.db.apply_migration(f"{name}-001", schema.read_text(encoding="utf-8"))
        migrations = module_path / "migrations"
        if migrations.is_dir():
            for migration in sorted(migrations.glob("*.sql")):
                if not migration.stem[:3].isdigit() or migration.stem[:3] == "001":
                    raise RuntimeError(f"Use a numbered additive migration after 001: {migration.name}")
                services.db.apply_migration(f"{name}-{migration.stem}", migration.read_text(encoding="utf-8"))
        module = importlib.import_module(f"renulus.{name}.api")
        router = module.create_router(services)
        if name == "knowledge":
            # Retained support is reconciled when Memory opens, so its local
            # source resolver must exist before that module is constructed.
            from .runtime.harness_library import HarnessLibrary
            library = services.registry.setdefault("harness_library", HarnessLibrary(services.get("knowledge")))
            services.registry.setdefault("memory_dependency_resolvers", {})["library_revision"] = library
        app.include_router(router, prefix="/api/v1")
        services.capabilities[name] = {"status": "installed"}
    # Separate feature routers preserve the existing module/legacy APIs. Their
    # schemas have already been checked and applied before any startup backfill.
    for name in ("runtime.harness_configuration_api", "learn.conversation_api", "study.project_api", "study.home_api", "study.nightly_api",
                 "assessment.test_api", "assessment.attempt_api", "assessment.generation_api", "assessment.import_api", "learn.chat_test_api", "knowledge.reader_api", "knowledge.attachment_api", "knowledge.note_api", "storage.workspace_api", "storage.search_api", "storage.study_help_api"):
        path = Path(__file__).parent.joinpath(*name.split(".")).with_suffix(".py")
        if path.exists():
            feature = importlib.import_module("renulus." + name)
            app.include_router(feature.create_router(services), prefix="/api/v1")
    from .storage.attachment_cleanup import drain as drain_attachment_cleanup
    services.on_startup.insert(0, lambda: drain_attachment_cleanup(services))
    # Its router lifespan also stops this worker. The explicit desktop drain
    # must join it before acknowledging settlement or releasing offline helpers.
    if 'knowledge_worker' in services.registry:
        services.on_stopping.append(lambda: services.registry['knowledge_worker'].stop(0))
        services.on_shutdown.append(lambda: asyncio.to_thread(
            services.registry['knowledge_worker'].stop, None))
    return app


def main():
    parser = argparse.ArgumentParser(description="Renulus local backend")
    parser.add_argument("--profile", required=True, help="Explicit isolated writable profile")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--source-root")
    args = parser.parse_args()
    import uvicorn
    token = os.environ.get("RENULUS_SESSION_TOKEN")
    if not token:
        raise SystemExit("RENULUS_SESSION_TOKEN is required for standalone startup")
    uvicorn.run(create_app(args.profile, token, args.source_root), host="127.0.0.1",
                port=args.port, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
