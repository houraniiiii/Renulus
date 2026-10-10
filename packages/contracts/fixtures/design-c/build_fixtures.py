# SPDX-License-Identifier: MIT
"""Build fictional fixtures using the baseline backend, without provider calls.

Run once with explicit scratch profile. Only this reserved directory receives
fixture JSON; databases/originals/ZIP receipts stay beneath contracts scratch.
"""
import argparse
import hashlib
import json
from pathlib import Path

from renulus.assessment.contracts import AnswerRequest, HelpRequest, StartRequest
from renulus.assessment.generated_contracts import GenerateRequest, GeneratedBatch
from renulus.cases.models import StartCase
from renulus.design_c_contracts import (
    CONTRACT_VERSION, RELATION_PROPOSALS, TABLE_COLUMNS, MIGRATION_RESERVATIONS,
    QuestionSnapshot, SavedTestVersion, validate_fictional_artifact, TestAttempt,
    AttemptDraft, PersistedAttemptPin, Job, UNAVAILABLE_REFERENCE_COLUMNS,
)
from renulus.server import create_app
from renulus.storage.backup import export_records, eligible_table, validate_records

ROOT = Path(__file__).resolve().parent
SCRATCH = Path("C:/Renulus/scratch/design-c/contracts").resolve()
DATE = "2026-10-10T12:00:00Z"


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def fictional_questions():
    topics = ("ckd", "dialysis", "transplantation", "glomerular", "electrolytes")
    return tuple(QuestionSnapshot(
        item_id=f"fiction_item_{index}", question_id=f"fiction_question_{index}",
        question_version="1", key_version="1", family_id=f"fiction_family_{index}",
        family_version="1", topic_id=topic,
        stem=f"Fictional learning scenario about {topic}: which action preserves source provenance?",
        options=({"id": "a", "text": "Keep the source revision and its locator"},
                 {"id": "b", "text": "Infer a missing source location"}),
        correct_option_ids=("a",), explanation="A citation pins the source revision and observed locator.",
    ) for index, topic in enumerate(topics, 1))


def derived_fixtures():
    version = SavedTestVersion.model_validate_json((ROOT / "saved-test-version.json").read_text(encoding="utf-8"))
    write("relations-and-rows.json", {"contract_version": CONTRACT_VERSION,
        "migration_reservations": MIGRATION_RESERVATIONS,
        "relations": [edge.model_dump(mode="json") for edge in RELATION_PROPOSALS],
        "unavailable_reference_columns": UNAVAILABLE_REFERENCE_COLUMNS, "table_columns": TABLE_COLUMNS})
    attempt = TestAttempt(id="attempt_fiction_1", version={"id": version.id}, mode="test",
        status="active", draft_revision=2, timing={"kind": "timed", "duration_seconds": 600,
            "started_at": DATE, "deadline_at": "2026-10-10T12:10:00Z", "last_reconciled_at": DATE})
    draft = AttemptDraft(attempt_id=attempt.id, version_id=version.id, revision=2, position=1,
        answers=({"item_id": version.items[0].item_id, "option_ids": ["a"], "marked": False},
                 {"item_id": version.items[1].item_id, "option_ids": [], "marked": True}))
    write("attempt-and-draft.json", {"attempt": attempt.model_dump(mode="json"), "draft": draft.model_dump(mode="json"),
        "study_committed": [{"item_id": version.items[0].item_id, "option_ids": ["a"],
            "committed_at": DATE, "correct": True, "assisted": True, "repeat": False}],
        "study_result": {"item_count": 5, "answered_count": 1, "unanswered_count": 4,
            "excluded_count": 0, "scored_count": 1, "correct_count": 1, "completed_at": DATE},
        "exposure": {"id": "exposure_fiction_1", "attempt_id": attempt.id, "version_id": version.id,
            "item_id": version.items[0].item_id, "question_id": version.items[0].question_id,
            "question_version": "1", "key_version": "1", "family_id": version.items[0].family_id,
            "family_version": "1", "kind": "presented", "created_at": DATE}})
    pin = PersistedAttemptPin(attempt_id=attempt.id, version_id=version.id, live_version_id=None, version_snapshot=version)
    write("unavailable-references.json", {"attempt_pin": pin.model_dump(mode="json"),
        "report": {"version_id": version.id, "live_version_id": None, "attempt_id": attempt.id,
            "live_attempt_id": None, "item_id": version.items[0].item_id,
            "question_id": version.items[0].question_id, "question_version": "1", "key_version": "1",
            "family_id": version.items[0].family_id, "family_version": "1"},
        "job_outcome": {"published_version_id": version.id, "live_published_version_id": None}})
    job = Job(id="job_fiction_1", operation="generate_test", idempotency_key="fiction-job-01",
        state="running", settings_revision=1, policy_revision=1, context_epoch=3, requested_count=5, validated_count=5,
        inputs=({"kind": "memory", "dependency": {"target": {"type": "memory_revision", "id": "memory_revision_fiction_1"},
            "expected_revision": "2"}},))
    write("job.json", job.model_dump(mode="json"))
    names = ("legacy-schema1-records.json", "legacy-schema1-inventory.json",
             "conversation.json", "saved-test-version.json", "fictional-artifact.json",
             "locators.json", "attempt-and-draft.json", "unavailable-references.json",
             "job.json", "relations-and-rows.json")
    for name in names:
        path = ROOT / name
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    write("fixture-manifest.json", {"contract_version": CONTRACT_VERSION,
        "source_baseline": "1b30a896", "provider_calls": 0,
        "files": {name: {"bytes": len((ROOT / name).read_bytes()),
                         "sha256": hashlib.sha256((ROOT / name).read_bytes()).hexdigest()} for name in names}})


def build(profile: Path):
    profile = profile.resolve()
    if not profile.is_relative_to(SCRATCH) or profile.exists():
        raise ValueError("Use a fresh owned contracts scratch profile")
    services = create_app(profile).state.services
    learn = services.registry["learn"].create_thread("Synthetic CKD study", "ckd")
    cases = services.registry["cases"]
    case = cases.start(StartCase(title="Fictional dialysis discussion",
                                text="Entirely fictional case used for contract ownership checks."))
    cases.save(case["id"], case["revision"])
    temporary = cases.start(StartCase(title="Volatile check", text="DC02_VOLATILE_INPUT_OMITTED"))
    services.registry["knowledge"].import_text("Synthetic transplantation study note.",
        title="Synthetic Library note", process=False)
    assessment = services.registry["assessment"]
    session = assessment.start(StartRequest(count=3, idempotency_key="dc02-fixture-start"))
    item = session["current_item"]
    assessment.help(session["id"], HelpRequest(item_id=item["id"], kind="sources",
                                             idempotency_key="dc02-fixture-help"))
    assessment.answer(session["id"], AnswerRequest(item_id=item["id"],
        option_ids=[item["options"][0]["id"]], idempotency_key="dc02-fixture-answer"))
    questions = fictional_questions()
    practice = services.registry["generated_practice"]
    run, _ = practice.prepare(GenerateRequest(prompt="Fictional source-provenance practice",
        count=3, context="study", idempotency_key="dc02-fixture-practice"))
    batch = GeneratedBatch(items=[{"stem": q.stem, "options": [o.model_dump() for o in q.options],
        "correct_option_id": "a", "explanation": q.explanation} for q in questions[:3]])
    generated = practice.publish(run, batch, [])  # Validated local batch; no provider is invoked.
    current = generated["session"]["current_item"]
    practice.answer(generated["session"]["id"], AnswerRequest(item_id=current["id"],
        option_ids=["a"], idempotency_key="dc02-fixture-practice-answer"))
    snapshot = export_records(services)
    # The fixtures pin local records only. Installed bank content is already
    # shipped, and assessment owns its original immutable question snapshots.
    snapshot["records"] = {name: rows for name, rows in snapshot["records"].items()
                           if not name.startswith("content_")}
    assert temporary["id"] not in json.dumps(snapshot)
    assert "DC02_VOLATILE_INPUT_OMITTED" not in json.dumps(snapshot)
    with services.db.connect() as conn:
        validate_records(conn, snapshot)
        columns = {row[0]: [col["name"] for col in conn.execute(f'PRAGMA table_info("{row[0]}")')]
                   for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                   if eligible_table(row[0])}
    write("legacy-schema1-records.json", snapshot)
    write("legacy-schema1-inventory.json", {"source_baseline": "1b30a896", "schema_version": 1,
        "columns": columns, "migration_ledger": services.db.fetch_all(
            "SELECT name,checksum FROM migration_ledger ORDER BY name")})
    version = SavedTestVersion(id="test_version_fiction_1", test_id="test_fiction", ordinal=1,
        origin="generated", review_quality="personal", status="ready", items=questions,
        terms="Synthetic contract fixture only; no clinical efficacy or bank-review claim.", created_at=DATE)
    write("saved-test-version.json", version.model_dump(mode="json"))
    artifact = validate_fictional_artifact(questions, artifact_id="fiction_artifact_1",
        validation_id="synthetic_review_1", privacy_check=lambda items: all(
            item.stem.startswith("Fictional learning scenario") for item in items),
        forbidden_fragments=(temporary["id"], "DC02_VOLATILE_INPUT_OMITTED"))
    write("fictional-artifact.json", artifact.model_dump(mode="json"))
    write("conversation.json", {"identity": {"type": "learn_thread", "id": learn["id"]},
        "kind": "learning", "retention": "saved", "lifecycle": "active", "revision": 1,
        "title": learn["title"], "project_id": None, "created_at": learn["created_at"],
        "updated_at": learn["updated_at"]})
    write("locators.json", [
        {"target": {"type": "library_revision", "id": "rev_fiction_pdf"},
         "locator": {"kind": "pdf", "physical_page": 3, "printed_label": "ii"}},
        {"target": {"type": "library_revision", "id": "rev_fiction_docx"},
         "locator": {"kind": "text", "item_ref": "#/texts/2", "section": "Dialysis", "start": 0, "end": 26}},
        {"target": {"type": "attachment", "id": "attachment_fiction_csv"},
         "locator": {"kind": "table", "format": "csv", "first_row": 2, "last_row": 3, "first_column": 1, "last_column": 4}},
        {"target": {"type": "library_revision", "id": "rev_fiction_xlsx"},
         "locator": {"kind": "table", "format": "xlsx", "sheet_name": "Fictional study", "first_row": 1, "last_row": 4, "first_column": 2, "last_column": 3}},
        {"target": {"type": "attachment", "id": "attachment_fiction_tiff"},
         "locator": {"kind": "image", "frame": 2, "bounds": [0.1, 0.2, 0.8, 0.9]}},
    ])
    derived_fixtures()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--derived-only", action="store_true")
    args = parser.parse_args()
    if args.derived_only:
        derived_fixtures()
    elif args.profile is not None:
        build(args.profile)
    else:
        parser.error("Supply --profile or --derived-only")
