"""Narrow local product API. Hermes is the sole generative agent foundation."""
import argparse
import importlib
import os
from pathlib import Path
import secrets
from contextlib import asynccontextmanager
import inspect

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import __version__
from .contracts import API_VERSION, ApiError
from .services import Services
from .storage import AppPaths, Database

MODULE_ORDER = ("runtime", "content", "knowledge", "retrieval", "learn", "cases",
                "assessment", "memory", "study", "updates")


def create_app(profile: str | Path, token: str | None = None, source_root=None) -> FastAPI:
    paths = AppPaths.create(profile, source_root)
    services = Services(paths, Database(paths.database))
    @asynccontextmanager
    async def lifespan(app):
        for callback in services.on_startup:
            result = callback()
            if inspect.isawaitable(result):
                await result
        try:
            yield
        finally:
            for callback in reversed(services.on_shutdown):
                result = callback()
                if inspect.isawaitable(result):
                    await result

    app = FastAPI(title="Renulus local API", version=__version__, docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.services = services
    app.state.session_token = token

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
        if token and request.url.path != "/api/v1/health":
            supplied = request.headers.get("x-renulus-token", "")
            if not secrets.compare_digest(supplied, token):
                return JSONResponse({"error": {"code": "invalid_session",
                    "message": "Reconnect the application", "retryable": True}}, status_code=401)
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def product_error(request: Request, error: ApiError):
        return JSONResponse({"error": {"code": error.code, "message": error.message,
            "retryable": error.retryable}}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        # Validation errors can include the submitted case payload; expose only field names.
        fields = [".".join(str(x) for x in item["loc"]) for item in error.errors()]
        return JSONResponse({"error": {"code": "invalid_request",
            "message": "Check the submitted fields: " + ", ".join(fields),
            "retryable": False}}, status_code=422)

    @app.get("/api/v1/health")
    def health():
        return {"status": "ready", "version": __version__, "api_version": API_VERSION,
                "schema_version": 1, "modules": services.capabilities}

    @app.get("/api/v1/meta")
    def meta():
        return {"version": __version__, "api_version": API_VERSION,
                "modules": services.capabilities}

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
        app.include_router(router, prefix="/api/v1")
        services.capabilities[name] = {"status": "installed"}
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
