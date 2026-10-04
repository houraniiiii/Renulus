"""Explicit key-free public topic metadata probe, never a pytest/live vendor test."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import httpx

from renulus.content.repository import ContentRepository
from renulus.contracts import ApiError, ContextScope, Scope
from renulus.retrieval.service import RetrievalService
from renulus.services import Services
from renulus.storage import AppPaths, Database


class StatusTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self.inner = None
        self.requests = []

    async def handle_async_request(self, request):
        assert request.url.host in ("www.ebi.ac.uk", "eutils.ncbi.nlm.nih.gov")
        assert "api_key" not in request.url.params and "authorization" not in request.headers
        if self.inner is None:
            self.inner = httpx.AsyncHTTPTransport(trust_env=False, retries=0)
        response = await self.inner.handle_async_request(request)
        self.requests.append({"host": request.url.host, "path": request.url.path, "status": response.status_code})
        return response

    async def aclose(self):
        if self.inner is not None:
            await self.inner.aclose()
            self.inner = None


async def probe(profile):
    root = Path(__file__).resolve().parents[2]
    # Refuse a connection-bearing profile without opening any secret record.
    for namespace in ("runtime", "retrieval"):
        if (profile / "state" / namespace / "connections.dpapi").exists():
            raise RuntimeError("Use a fresh public-probe profile without connections")
    paths = AppPaths.create(profile, root)
    db = Database(paths.database)
    for module in ("content", "retrieval"):
        db.apply_migration(module + "-001", (root / "runtime/renulus" / module / "schema.sql").read_text(encoding="utf-8"))
    services = Services(paths, db)
    content = ContentRepository(db, root / "content/packs")
    content.install_pack(root / "content/packs/renulus-foundations/1.0.0")
    services.registry["content"] = content
    transport = StatusTransport()
    service = RetrievalService(services, transport=transport)
    checks = []
    for provider, topic_id in (("europe-pmc", "T21"), ("europe-pmc", "T19"), ("pubmed", "T21")):
        start = time.monotonic()
        try:
            result = await service.discover(topic_id, scope=ContextScope(kind=Scope.STUDY), provider=provider, limit=3)
            checks.append({"provider": provider, "topic_id": topic_id, "topic_label": result["topic_label"],
                "queried_at": result["queried_at"], "returned": len(result["records"]),
                "record_ids": [row["id"] for row in result["records"]], "latest_final_verified": False,
                "passage_evidence": False, "seconds": round(time.monotonic() - start, 3)})
        except ApiError as error:
            checks.append({"provider": provider, "topic_id": topic_id, "topic_label": service.topic(topic_id)["label"],
                "error": {"code": error.code, "message": error.message}, "seconds": round(time.monotonic() - start, 3)})
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "python": sys.version.split()[0],
            "profile": str(profile), "scope": "installed_public_topic_metadata_only",
            "keys_used": False, "model_calls": 0, "billed_tool_calls": 0,
            "fulltext_imports": 0, "requests": transport.requests, "checks": checks}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(probe(args.profile.resolve())), indent=2))
