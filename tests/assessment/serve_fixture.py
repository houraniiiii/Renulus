"""Explicit synthetic UI-test server. Never part of production startup."""
import argparse
from pathlib import Path

from conftest import SyntheticContentRepository
import renulus.server as server
from renulus.server import create_app
import uvicorn
import json
import re


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--token", default="assessment-fixture-session")
    parser.add_argument("--generated-provider", action="store_true")
    args = parser.parse_args()
    profile = Path(args.profile).resolve()
    server.MODULE_ORDER = ("content", "updates", "assessment")
    app = create_app(profile, token=args.token)
    app.state.services.registry["content"] = SyntheticContentRepository()
    if args.generated_provider:
        from test_generated import SyntheticProvider, SyntheticKnowledge, output
        class OriginalFixtureProvider(SyntheticProvider):
            async def stream(self, messages, *, scope, run_id, model=None, system=None, purpose="explain"):
                amount = int(re.search(r"Produce exactly (\d+) questions", system).group(1))
                batch = json.dumps(output(amount, source_indices=[0] if scope.persistent else []))
                yield batch[:30]
                yield batch[30:]
        app.state.services.registry.update(provider=OriginalFixtureProvider(), knowledge=SyntheticKnowledge())
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning")
