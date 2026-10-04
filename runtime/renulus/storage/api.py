"""Explicit records-only JSON and verified full ZIP recovery operations."""
import asyncio

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError
from starlette.background import BackgroundTask

from ..contracts import ApiError
from .backup import export_records
from .recovery import Recovery
from .recovery_archive import canonical_json, strict_json
from .recovery_files import remove_owned_tree


class Restore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bundle: dict
    confirm_backup_date: StrictBool = False
    confirmed_exported_at: str | None = Field(default=None, max_length=64)


class RestoreBackup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_token: str = Field(pattern=r"^[0-9a-f]{32}$")
    confirmed_exported_at: str = Field(max_length=64)
    acknowledge_deletion_limits: StrictBool = False


async def read_bounded(request, bound, *, destination=None):
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isascii() or not declared.isdecimal():
            raise ApiError("backup_size", "The backup upload has an invalid content length")
        if len(declared) > 20 or int(declared) > bound:
            raise ApiError("backup_limit", "The selected backup exceeds the upload size limit", 413)
    size, parts = 0, []
    async for block in request.stream():
        size += len(block)
        if size > bound:
            raise ApiError("backup_limit", "The backup upload exceeds its size limit", 413)
        if destination is None:
            parts.append(block)
        else:
            destination.write(block)
    return b"".join(parts) if destination is None else None


def create_router(services):
    router = APIRouter(prefix="/data", tags=["data"])
    recovery = Recovery(services)
    services.registry["data_recovery"] = recovery

    def queue_rebuild(result, tasks):
        identifier, state, start = recovery.request_rebuild()
        if start:
            tasks.add_task(recovery.rebuild, identifier)
        return {**result, "rebuild": state}

    @router.get("/export")
    def export():
        with recovery.mutation():
            data = canonical_json(export_records(services))
        if len(data) > recovery.limits.json_bytes:
            raise ApiError("backup_limit", "The records-only JSON exceeds 16 MiB; this bounded export cannot include this profile", 413)
        return Response(data, media_type="application/json", headers={
            "Content-Disposition": 'attachment; filename="renulus-records-only.json"',
            "X-Renulus-Data-Kind": "records-only", "Cache-Control": "no-store"})

    @router.post("/restore")
    async def restore(request: Request, tasks: BackgroundTasks):
        # A manual bounded JSON read rejects oversized/duplicate-key bodies before parsing.
        raw = await read_bounded(request, recovery.limits.json_bytes + 4096)
        try:
            body = Restore.model_validate(strict_json(raw))
        except ValidationError:
            raise ApiError("backup_request", "Choose a canonical JSON export and confirm its backup date", 422) from None
        result = await asyncio.to_thread(recovery.restore_json, body.bundle,
            confirm_backup_date=body.confirm_backup_date, confirmed_exported_at=body.confirmed_exported_at)
        return queue_rebuild(result, tasks)

    @router.get("/backup")
    def backup():
        directory, manifest = recovery.backup()
        return FileResponse(directory / "backup.zip", media_type="application/zip",
            filename="renulus-backup-" + manifest["exported_at"][:10] + ".zip",
            headers={"Cache-Control": "no-store", "X-Renulus-Data-Kind": "full-backup"},
            background=BackgroundTask(remove_owned_tree, services.paths, directory))

    @router.post("/backup/preview")
    async def preview(request: Request):
        identifier, directory = recovery.begin_preview()
        keep = False
        try:
            with (directory / "input.zip").open("xb") as output:
                await read_bounded(request, recovery.limits.archive_bytes, destination=output)
            result = await asyncio.to_thread(recovery.complete_preview, identifier, directory)
            keep = True
            return result
        finally:
            recovery.end_upload(directory, keep=keep)

    @router.delete("/backup/preview/{preview_token}", status_code=204)
    def discard(preview_token: str):
        recovery.discard_preview(preview_token)
        return Response(status_code=204)

    @router.post("/backup/restore")
    def restore_backup(body: RestoreBackup, tasks: BackgroundTasks):
        result = recovery.restore_preview(body.preview_token, body.confirmed_exported_at,
                                          body.acknowledge_deletion_limits)
        return queue_rebuild(result, tasks)

    @router.get("/recovery")
    def status():
        return recovery.status()

    @router.post("/rebuild", status_code=202)
    def rebuild(tasks: BackgroundTasks):
        identifier, state, start = recovery.request_rebuild()
        if start:
            tasks.add_task(recovery.rebuild, identifier)
        return state

    return router
