"""Explicit opt-in proof: two registered PDF checks and one free metadata query.

Not run by pytest. No source educational review or provider/model call is made.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime"))

from renulus import server
from renulus.updates.fetch import SourceFetcher


class ThreeChecks(SourceFetcher):
    def __init__(self):
        super().__init__()
        self.checks = 0

    async def fetch(self, url, allowed_hosts, limit=2_000_000):
        if self.checks >= 3:
            raise RuntimeError("Live proof is capped to three free official checks")
        self.checks += 1
        return await super().fetch(url, allowed_hosts, limit)


async def run():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    profile = ROOT / ".local/runtime" / ("updates-official-" + stamp)
    server.MODULE_ORDER = ("content", "updates")
    service = server.create_app(profile, source_root=ROOT).state.services.registry["updates"]
    fetcher = ThreeChecks()
    service.fetcher = fetcher
    candidate = next(item for item in service.publications.candidates("K01") if item["url"].endswith(".pdf"))
    publication = service.publications.track("K01", candidate["url"],
        "docs/SOURCES.md — public KDIGO digest/currency check only; downloaded bytes discarded, no redistribution or educational review")
    first = await service.publications.check(publication["id"], force=True)
    second = await service.publications.check(publication["id"], force=True) if first["state"] != "failed" else None
    # Metadata only, chosen from the actual installed topic catalogue.
    topics = service.services.registry["content"].list_topics()
    topic = next((item for item in topics if "chronic kidney" in item["title"].lower()), topics[0])
    literature = await service.check_literature([topic["id"]], days=30)
    def observation(value):
        if not value:
            return None
        return {key: value.get(key) for key in ("state", "digest", "fetch_metadata", "last_checked_at", "last_success_at", "error_code")}
    proof = {"checked_at": datetime.now(timezone.utc).isoformat(), "register_id": "K01", "url": candidate["url"],
             "first": observation(first), "second": observation(second), "literature": literature,
             "free_official_checks": fetcher.checks, "paid_providers_enabled": False,
             "educational_review_performed": False, "whole_app_or_installer_proof": False}
    (profile / "network-proof.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"proof_path": str(profile / "network-proof.json"), **proof}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-free-official", action="store_true", required=True)
    parser.parse_args()
    asyncio.run(run())
