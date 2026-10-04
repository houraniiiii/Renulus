from __future__ import annotations

from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from renulus.contracts import ContextScope
from .service import RetrievalService

Tool = Literal["ncbi", "brave", "tavily", "exa"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Configure(Input):
    api_key: str | None = Field(default=None, max_length=8192, repr=False)
    enabled: bool = False
    daily_request_limit: int = Field(default=100, ge=0, le=10000)
    daily_credit_limit: int = Field(default=20, ge=0, le=10000)


class Select(Input):
    provider: Tool | None


class Discovery(Input):
    topic_id: str = Field(min_length=1, max_length=128)
    scope: ContextScope
    provider: Literal["europe-pmc", "pubmed", "selected-tool", "ncbi", "brave", "tavily", "exa"] = "europe-pmc"
    limit: int = Field(default=5, ge=1, le=20)


class ArticleImport(Input):
    topic_id: str = Field(min_length=1, max_length=128)
    pmcid: str = Field(pattern=r"^PMC[1-9][0-9]{0,10}$")
    scope: ContextScope
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")


def create_router(services) -> APIRouter:
    if "retrieval" not in services.registry:
        services.registry["retrieval"] = RetrievalService(services)
    service = services.registry["retrieval"]
    router = APIRouter(prefix="/retrieval", tags=["retrieval"])

    @router.get("/connections")
    def connections():
        return service.status()

    @router.put("/connections/{provider}")
    async def configure(provider: Tool, body: Configure):
        return await service.configure(provider, **body.model_dump())

    @router.post("/connections/select")
    async def select(body: Select):
        return await service.select(body.provider)

    @router.delete("/connections/{provider}")
    async def disconnect(provider: Tool):
        return await service.disconnect(provider)

    @router.post("/discover")
    async def discover(body: Discovery):
        return await service.discover(**body.model_dump(exclude={"scope"}), scope=body.scope)

    @router.post("/articles/import")
    async def import_article(body: ArticleImport):
        return await service.import_article(**body.model_dump(exclude={"scope"}), scope=body.scope)

    return router
