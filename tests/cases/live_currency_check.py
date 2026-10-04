"""Synthetic Cases preview using the real parent currency read projection."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

from renulus.server import create_app

if __package__:
    from .conftest import ContentFixture, TEACHING
else:
    from conftest import ContentFixture, TEACHING


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--updates-source", required=True)
    parser.add_argument("--port", type=int, default=8882)
    args = parser.parse_args()
    profile = Path(args.profile).resolve()
    if ".local/runtime/" not in profile.as_posix():
        raise SystemExit("Use an explicit isolated development profile")
    import renulus
    source = Path(args.updates_source).resolve()
    renulus.__path__.append(str(source / "runtime/renulus"))
    from renulus.updates.impact import AffectedVersions
    import renulus.updates.impact as producer
    root = Path(producer.__file__).resolve().parent
    if not root.is_relative_to(source):
        raise SystemExit("The configured parent currency producer is required")
    app = create_app(profile, token="synthetic-cases-currency-preview")
    services = app.state.services
    services.registry["content"] = ContentFixture()
    services.db.apply_migration("cases-check-updates-base", (root / "schema.sql").read_text(encoding="utf-8"))
    services.db.apply_migration("cases-check-updates-review", (root / "migrations/003-reviewed-source-status.sql").read_text(encoding="utf-8"))
    affected = AffectedVersions(services.db)
    services.registry["updates"] = SimpleNamespace(affected=affected)
    services.db.execute("CREATE TABLE IF NOT EXISTS content_case_versions(case_id TEXT,version INTEGER,body_json TEXT,PRIMARY KEY(case_id,version))")
    original = deepcopy(TEACHING)
    original["source_records"] = [{"id": "synthetic-source", "register_id": "K03", "url": "https://example.invalid/synthetic-source.pdf"}]
    original["stages"][1]["sources"] = [{"source_id": "synthetic-source", "locator": "Synthetic hidden stage reference"}]
    services.db.execute("INSERT OR IGNORE INTO content_case_versions VALUES(?,?,?)", (original["id"], original["version"], json.dumps(original)))
    services.db.execute("INSERT OR IGNORE INTO update_entries(id,source_id,external_id,title,url,kind,discovered_at,review_state,summary,source_metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("synthetic-correction", "K03", "synthetic-correction", "Synthetic correction to a cited source", "https://example.invalid/synthetic-correction.pdf",
         "correction", "2026-10-04T18:00:00+00:00", "pending", "Synthetic source correction for currency review", "{}"))
    with services.db.transaction() as conn:
        affected.record(conn, "synthetic-correction", {"register_id": "K03", "pinned_source_id": "synthetic-source"},
                        "2026-10-04T18:00:00+00:00", "synthetic-correction")
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
