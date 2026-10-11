# SPDX-License-Identifier: MIT
"""Public H04 routes; trusted parent assembly supplies the sole controller.

Register it as services.registry["harness_configuration_controller"] and mount
create_router(services) once under /api/v1. snapshot/activate return the Settings
snapshot; stage_roles returns version plus requested/effective/failed/failure_code
and admission_open. Existing immutable specs can supply the two configurations.
The controller owns subscription selection, current allowed catalogue IDs,
staging and activation. Response projections expose only Settings fields.
"""
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from renulus.contracts import ApiError
from .harness_configuration import RolePolicy


class HarnessConfigurationController(Protocol):
    """The parent owns the instance and all authority/lifecycle decisions."""

    async def snapshot(self) -> dict: ...

    async def stage_roles(self, roles: tuple[RolePolicy, ...]) -> dict: ...

    async def activate(self, version: str) -> dict: ...


_Version = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]


class _PublicModel(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)


class _PublicRole(RolePolicy):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)


class _PublicAttempts(_PublicModel):
    foreground_dispatches: int
    standalone_dispatches: int
    title_dispatches: int
    retries: int


class _PublicConfiguration(_PublicModel):
    roles: list[_PublicRole] = Field(strict=False)
    attempts: _PublicAttempts


class _PublicStatus(_PublicModel):
    requested: _Version | None
    effective: _Version | None
    failed: _Version | None
    failure_code: str | None
    admission_open: bool


class _PinnedRun(_PublicModel):
    run_id: str
    purpose: str
    version: _Version


class _PublicSnapshot(_PublicStatus):
    configuration: _PublicConfiguration | None
    requested_configuration: _PublicConfiguration | None
    pinned_runs: list[_PinnedRun] = Field(strict=False)
    catalogue: list[str] = Field(strict=False)


class _PublicStaged(_PublicStatus):
    version: _Version


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _StageRoles(_Input):
    roles: list[RolePolicy] = Field(min_length=1, max_length=14)

    @model_validator(mode="after")
    def unique_purposes(self):
        if len({role.purpose for role in self.roles}) != len(self.roles):
            raise ValueError("Use one policy per purpose")
        return self


class _Activate(_Input):
    version: _Version


def create_router(services) -> APIRouter:
    """Mount once under /api/v1 after the parent registers its controller."""
    def no_store(response: Response):
        response.headers["Cache-Control"] = "no-store"

    router = APIRouter(prefix="/runtime/harness/configuration", tags=["runtime"],
        dependencies=[Depends(no_store)])

    def controller() -> HarnessConfigurationController:
        value = services.registry.get("harness_configuration_controller")
        if value is None:
            raise ApiError("harness_configuration_unavailable",
                "Harness configuration is not available yet.", 503, True)
        return value

    @router.get("", response_model=_PublicSnapshot)
    async def snapshot():
        return await controller().snapshot()

    @router.post("", response_model=_PublicStaged)
    async def stage(request: _StageRoles):
        return await controller().stage_roles(tuple(request.roles))

    @router.post("/activate", response_model=_PublicSnapshot)
    async def activate(request: _Activate):
        return await controller().activate(request.version)

    return router
