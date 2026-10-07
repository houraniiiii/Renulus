"""Read-only exact selected-source extraction probe; no original distribution."""
import argparse
import importlib.util
from pathlib import Path
import sqlite3

from renulus.knowledge.engines import DoclingExtractor, OfflineAssets
from renulus.services import Services
from renulus.storage import AppPaths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--helper-module", required=True)
    parser.add_argument("--catalogue-db", required=True)
    parser.add_argument("--entry-id", required=True)
    args = parser.parse_args()
    paths = AppPaths.create(args.profile, source_root=Path(args.helper_module).parents[3])
    spec = importlib.util.spec_from_file_location("probe_helpers", args.helper_module)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    services = Services(paths, None)
    services.registry["helpers"] = module.HelperAssets(paths)
    connection = sqlite3.connect(Path(args.catalogue_db).resolve().as_uri() + "?mode=ro", uri=True)
    entry = connection.execute("SELECT collection_path,eligibility,reserved FROM knowledge_catalogue WHERE id=?", (args.entry_id,)).fetchone()
    if not entry or entry[1] != "eligible" or entry[2]:
        raise SystemExit("Select a catalogued eligible resource explicitly")
    root = Path("C:/Users/karol/Documents/Renulus-data").resolve()
    source = (root / entry[0]).resolve()
    if not source.is_relative_to(root):
        raise SystemExit("Source leaves the authorised collection")
    result = DoclingExtractor(OfflineAssets(services)).extract_file(source, "Selected corpus extraction probe")
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(paths.helpers / "fastembed/bge-small-en-v1.5/tokenizer.json"))
    tokenizer.no_truncation()
    lengths = [len(tokenizer.encode(p["context_text"], add_special_tokens=False).ids) for p in result.passages]
    print({"entry_id": args.entry_id, "status": "extracted", "passages": len(lengths), "max_context_tokens": max(lengths),
        "pages": len(result.document.get("pages", {})), "all_located": all(p["locators"] for p in result.passages)}, flush=True)


if __name__ == "__main__":
    main()
