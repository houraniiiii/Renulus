"""Explicit lane-local verification server; never a doctor startup path."""
import argparse
import importlib.util
from pathlib import Path

from renulus.server import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--helper-module", required=True)
    parser.add_argument("--port", type=int, default=8796)
    parser.add_argument("--catalogue", action="store_true")
    args = parser.parse_args()
    root = Path(args.profile).resolve()
    if ".local/runtime" not in root.as_posix():
        raise SystemExit("Use an explicit isolated development profile")
    app = create_app(root, token="library-synthetic-verification", source_root=Path(args.helper_module).parents[3])
    spec = importlib.util.spec_from_file_location("library_helper_verification", args.helper_module)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    services = app.state.services
    services.registry["helpers"] = module.HelperAssets(services.paths)
    if args.catalogue:
        print(services.registry["knowledge_catalogue"].register(), flush=True)
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
