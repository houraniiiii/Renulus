"""Explicit synthetic UI-test server. Never part of production startup."""
import argparse
from pathlib import Path

from conftest import SyntheticContentRepository
from renulus.server import create_app
import uvicorn


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--token", default="assessment-fixture-session")
    args = parser.parse_args()
    profile = Path(args.profile).resolve()
    app = create_app(profile, token=args.token)
    app.state.services.registry["content"] = SyntheticContentRepository()
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning")
