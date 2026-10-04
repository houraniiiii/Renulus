"""Opt-in development preview with actual offline engines and no provider."""

import argparse
from contextlib import asynccontextmanager
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

from renulus.server import create_app
from renulus.storage import AppPaths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--knowledge-source", required=True)
    parser.add_argument("--helper-module", required=True)
    parser.add_argument("--helper-profile", required=True)
    parser.add_argument("--port", type=int, default=8880)
    args = parser.parse_args()
    profile = Path(args.profile).resolve()
    if ".local/runtime/" not in profile.as_posix():
        raise SystemExit("Use an explicit isolated development profile")
    import renulus
    renulus.__path__.append(str(Path(args.knowledge_source).resolve() / "runtime/renulus"))
    from renulus.knowledge.repository import KnowledgeRepository
    helper_path = Path(args.helper_module).resolve()
    package_name = "cases_preview_helpers"
    package = ModuleType(package_name)
    package.__path__ = [str(helper_path.parent)]
    sys.modules[package_name] = package
    spec = importlib.util.spec_from_file_location(package_name + ".helpers", helper_path)
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper
    spec.loader.exec_module(helper)

    class ReadOnlyAssetPaths(AppPaths):
        @property
        def helpers(self):
            # Only already validated public artifacts are shared for this check.
            return Path(args.helper_profile).resolve() / "helpers"

    app = create_app(profile, token="synthetic-cases-attachment-preview")
    services = app.state.services
    services.paths = ReadOnlyAssetPaths(services.paths.root, helper_path.parents[3])
    assets = helper.HelperAssets(services.paths)
    services.registry["helpers"] = assets
    services.registry["knowledge"] = KnowledgeRepository(services)

    @asynccontextmanager
    async def lifespan(app):
        # Identical approved startup runs before accepting any HTTP payload.
        await assets.startup.start()
        try:
            yield
        finally:
            assets.startup.close()

    app.router.lifespan_context = lifespan
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
