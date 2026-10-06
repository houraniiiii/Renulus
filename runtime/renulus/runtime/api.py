"""Module-owned local connection and runtime routes; no second product server."""
from __future__ import annotations

from contextlib import aclosing
from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from renulus.contracts import ContextScope
from .helpers import HelperAssets
from .inputs import MessageInput
from .manager import ProviderManager
from .policy import validate_messages

if TYPE_CHECKING:
    from renulus.services import Services


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GoConnection(_Input):
    api_key: str = Field(min_length=1, max_length=8192, repr=False)
    select: bool = False


class LoginRequest(_Input):
    select: bool = False


class SelectRequest(_Input):
    provider: Literal["codex", "opencode-go"]
    model: str | None = None


class RunRequest(_Input):
    run_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    messages: list[MessageInput] = Field(min_length=1, max_length=200)
    scope: ContextScope
    model: str | None = None
    system: str | None = None
    purpose: str = "explain"


class CompactRequest(_Input):
    run_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    messages: list[MessageInput] = Field(min_length=1, max_length=200)
    scope: ContextScope
    model: str | None = None
    system: str | None = None


def register(services: Services) -> ProviderManager:
    if "provider" not in services.registry:
        services.registry["provider"] = ProviderManager(services.paths)
        services.on_shutdown.append(services.registry["provider"].close)
    if "helpers" not in services.registry:
        services.registry["helpers"] = HelperAssets(services.paths)
        services.on_startup.append(services.registry["helpers"].startup.start)
        # Shutdown runs in reverse order: retain controlled temp/offline settings
        # until provider streams and all module workers have been stopped.
        services.on_shutdown.insert(0, services.registry["helpers"].startup.close)
    if "context" not in services.registry:
        services.registry["context"] = services.registry["provider"].context
    return services.registry["provider"]


def create_router(services: Services) -> APIRouter:
    manager = register(services)

    router = APIRouter()
    connections = APIRouter(prefix="/connections", tags=["connections"])
    runtime = APIRouter(prefix="/runtime", tags=["runtime"])

    @connections.get("")
    def list_connections():
        return manager.connections()

    @connections.post("/opencode-go")
    async def connect_go(request: GoConnection):
        return await manager.connect_go(request.api_key, select=request.select)

    @connections.post("/select")
    def select(request: SelectRequest):
        return manager.select(request.provider, request.model)

    @connections.post("/codex/login")
    async def start_login(request: LoginRequest):
        return await manager.auth.start(select=request.select)

    @connections.get("/codex/login/{login_id}")
    def login_status(login_id: str):
        return manager.auth.status(login_id)

    @connections.delete("/codex/login/{login_id}")
    async def cancel_login(login_id: str):
        return await manager.auth.cancel(login_id)

    @connections.post("/{provider}/refresh")
    async def refresh(provider: str):
        return await manager.refresh(provider)

    @connections.delete("/{provider}")
    async def disconnect(provider: str):
        return await manager.disconnect(provider)

    @runtime.get("/status")
    def status():
        return {**manager.status(), "helpers": services.registry["helpers"].status(),
                "helper_startup": services.registry["helpers"].startup.status(),
                "context": services.registry["context"].status()}

    @runtime.post("/context/compact")
    async def compact(request: CompactRequest):
        return await manager.compact([message.model_dump() for message in request.messages],
            scope=request.scope, run_id=request.run_id, model=request.model, system=request.system)

    @runtime.post("/runs")
    async def run(request: RunRequest):
        messages = [message.model_dump() for message in request.messages]
        validate_messages(messages)
        async def events():
            async with aclosing(manager.events(messages, scope=request.scope,
                run_id=request.run_id, model=request.model, system=request.system,
                purpose=request.purpose)) as stream:
                async for event in stream:
                    yield "data: " + event.model_dump_json() + "\n\n"
        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @runtime.delete("/runs/{run_id}")
    async def cancel(run_id: str):
        return {"run_id": run_id, "cancelled": await manager.cancel(run_id)}

    router.include_router(connections)
    router.include_router(runtime)
    return router
