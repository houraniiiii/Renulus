import json

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from .backup import export_records, restore_records


class Restore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bundle: dict
    confirm_backup_date: bool = False


def create_router(services):
    router = APIRouter(prefix="/data", tags=["data"])

    @router.get("/export")
    def export():
        data = json.dumps(export_records(services), ensure_ascii=False, indent=2)
        return Response(data, media_type="application/json", headers={
            "Content-Disposition": 'attachment; filename="renulus-learning-export.json"',
            "Cache-Control": "no-store"})

    @router.post("/restore")
    def restore(body: Restore):
        return restore_records(services, body.bundle, confirm_older=body.confirm_backup_date)

    return router
