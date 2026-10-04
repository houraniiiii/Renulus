"""Real pack and Updates for renderer tests; publisher bytes are synthetic."""
import argparse
from pathlib import Path

import renulus.server as server
import uvicorn

from test_source_currency import currency_app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--token", default="currency-fixture-session")
    args = parser.parse_args()
    server.MODULE_ORDER = ("content", "updates", "assessment")
    app = currency_app(Path(args.profile).resolve(), token=args.token)
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning")
