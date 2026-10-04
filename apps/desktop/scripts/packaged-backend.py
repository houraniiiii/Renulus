"""Packaged Renulus entry: provision declared local helpers, then controlled API."""
import argparse
import json
import os
from pathlib import Path

def windows_io_path(value):
    """Atomic .copying suffixes must work without a machine registry change."""
    if os.name != "nt":
        return value
    text = str(value)
    if text.startswith("\\\\?\\"):
        return value
    return Path("\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text)

def main():
    from helper_copy import copy_assets
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--profile", required=True)
    options, _ = parser.parse_known_args()
    profile = Path(options.profile).resolve()
    if not Path(options.profile).is_absolute() or profile == Path(profile.anchor):
        raise SystemExit("An explicit app-owned profile is required")
    root = Path(__file__).resolve().parent
    reviewed = json.loads((root / "packaging/runtime/helper-assets.json").read_text(encoding="utf-8-sig"))
    acquired = json.loads((root / "helper-assets/manifest.json").read_text(encoding="utf-8-sig"))
    if reviewed != acquired:
        raise SystemExit("The packaged helper manifest differs from the reviewed source contract")
    copy_assets(windows_io_path(root / "helper-assets"), windows_io_path(profile / "helpers"))
    from renulus.server import main as serve
    serve()

if __name__ == "__main__":
    main()
