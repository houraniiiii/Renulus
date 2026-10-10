# SPDX-License-Identifier: MIT
"""H01 public contract validation with independent synthetic JSON examples."""
import json
from pathlib import Path

from pydantic import ValidationError
from jsonschema import Draft202012Validator
import pytest

from renulus.harness_contracts import PairedStoreManifest
from renulus.design_c_contracts import Conversation


FIXTURES = Path(__file__).resolve().parents[2] / "packages/contracts/fixtures/harness"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def active_pair():
    value = fixture("paired-store-prepared.json")
    value["state"] = "active"
    value["domain_store"]["validation"] = "valid"
    value["runtime_store"]["validation"] = "valid"
    return PairedStoreManifest.model_validate(value)


def test_prepared_pair_preserves_existing_schema_and_distinct_store_identities():
    manifest = PairedStoreManifest.model_validate(fixture("paired-store-prepared.json"))
    assert manifest.domain_store.schema_version == 2
    assert manifest.domain_store.store_id == "synthetic-domain-store"
    assert manifest.runtime_store.store_id == "synthetic-runtime-store"
    assert manifest.snapshot_generation == 1
    assert manifest.state == "prepared"


@pytest.mark.parametrize("pending", ["domain_store", "runtime_store"])
def test_active_pair_requires_both_store_validations(pending):
    value = fixture("paired-store-prepared.json")
    value["state"] = "active"
    value["domain_store"]["validation"] = "valid"
    value["runtime_store"]["validation"] = "valid"
    assert PairedStoreManifest.model_validate(value).state == "active"
    value[pending]["validation"] = "pending"
    with pytest.raises(ValidationError, match="both stores"):
        PairedStoreManifest.model_validate(value)


@pytest.mark.parametrize("store", ["domain_store", "runtime_store"])
def test_mixed_snapshot_generations_cannot_form_a_pair(store):
    value = fixture("paired-store-prepared.json")
    value[store]["generation"] = 2
    with pytest.raises(ValidationError, match="snapshot generation"):
        PairedStoreManifest.model_validate(value)


@pytest.mark.parametrize("path", [
    "", "../other.sqlite3", "runtime/../domain.sqlite3", "./runtime.db",
    "/runtime.db", "C:/private/runtime.db", "C:runtime.db", "runtime\\store.db",
    "//server/share/store.db", "runtime//store.db", "runtime/db:stream",
    "runtime/store.db.", "runtime/store.db ", "runtime/%2e%2e/store.db",
    "runtime/NUL", "runtime/con.sqlite3", "runtime/COM1.db", "runtime/LPT9.db",
])
def test_store_paths_cannot_escape_or_alias_owned_windows_paths(path):
    value = fixture("paired-store-prepared.json")
    value["runtime_store"]["path"] = path
    with pytest.raises(ValidationError):
        PairedStoreManifest.model_validate(value)


@pytest.mark.parametrize(("field", "alias"), [
    ("store_id", "synthetic-domain-store"),
    ("path", "domain/renulus.sqlite3"), ("path", "DOMAIN/Renulus.sqlite3"),
    ("path", "domain"), ("path", "domain/renulus.sqlite3/other.db"),
])
def test_pair_keeps_domain_and_runtime_stores_distinct(field, alias):
    value = fixture("paired-store-prepared.json")
    value["runtime_store"][field] = alias
    with pytest.raises(ValidationError, match="distinct"):
        PairedStoreManifest.model_validate(value)


@pytest.mark.parametrize(("field", "other"), [
    ("profile_id", "other-profile"), ("domain_store_id", "other-domain"),
    ("runtime_store_id", "other-runtime"), ("snapshot_generation", 2),
])
def test_consuming_a_pair_requires_the_callers_exact_store_selection(field, other):
    from renulus.harness_contracts import validate_paired_store_manifest

    value = fixture("paired-store-prepared.json")
    value["state"] = "active"
    value["domain_store"]["validation"] = "valid"
    value["runtime_store"]["validation"] = "valid"
    expected = dict(profile_id="synthetic-profile", domain_store_id="synthetic-domain-store",
                    runtime_store_id="synthetic-runtime-store", snapshot_generation=1)
    assert validate_paired_store_manifest(value, **expected).state == "active"
    with pytest.raises(ValueError, match="selection"):
        validate_paired_store_manifest(value, **{**expected, field: other})
    value["state"] = "prepared"
    with pytest.raises(ValueError, match="active"):
        validate_paired_store_manifest(value, **expected)


def test_saved_runtime_mapping_preserves_existing_typed_conversation_identities():
    from renulus.harness_contracts import HarnessEngineReference, map_saved_conversation

    reference = HarnessEngineReference.model_validate(fixture("engine-reference.json"))
    mappings = [map_saved_conversation(Conversation.model_validate(value), reference,
                                       manifest=active_pair())
                for value in fixture("saved-conversations.json")]
    assert [mapping.conversation.key for mapping in mappings] == [
        ("learn_thread", "existing-chat"), ("case", "existing-chat")]
    assert mappings[0].runtime.session_id == "ses_synthetic_saved"
    assert mappings[1].retention == "saved"


@pytest.mark.parametrize(("field", "value"), [
    ("retention", "temporary"), ("lifecycle", "deleted"),
])
def test_temporary_or_deleted_conversation_cannot_gain_a_durable_runtime_mapping(field, value):
    from renulus.harness_contracts import HarnessEngineReference, map_saved_conversation

    raw = fixture("saved-conversations.json")[0]
    raw[field] = value
    conversation = Conversation.model_validate(raw)
    reference = HarnessEngineReference.model_validate(fixture("engine-reference.json"))
    with pytest.raises(ValueError, match="live saved"):
        map_saved_conversation(conversation, reference, manifest=active_pair())


@pytest.mark.parametrize(("field", "value"), [
    ("profile_id", "other-profile"), ("store_id", "synthetic-domain-store"),
    ("store_id", "other-runtime-store"),
])
def test_runtime_mapping_requires_the_active_profile_runtime_store(field, value):
    from renulus.harness_contracts import HarnessEngineReference, map_saved_conversation

    conversation = Conversation.model_validate(fixture("saved-conversations.json")[0])
    raw = fixture("engine-reference.json")
    raw[field] = value
    reference = HarnessEngineReference.model_validate(raw)
    with pytest.raises(ValueError, match="active runtime store"):
        map_saved_conversation(conversation, reference, manifest=active_pair())
    reference = HarnessEngineReference.model_validate(fixture("engine-reference.json"))
    prepared = PairedStoreManifest.model_validate(fixture("paired-store-prepared.json"))
    with pytest.raises(ValueError, match="active runtime store"):
        map_saved_conversation(conversation, reference, manifest=prepared)


def test_command_outcomes_preserve_all_five_ipc_admission_and_settlement_meanings():
    from renulus.harness_contracts import HarnessCommandOutcome

    outcomes = [HarnessCommandOutcome.model_validate(value)
                for value in fixture("command-outcomes.json")]
    assert [reply.outcome for reply in outcomes] == [
        "rejected_before_admission", "accepted_pending", "committed_reference",
        "cancelled_settled", "uncertain_after_disconnect",
    ]
    assert outcomes[1].generation == "process-one"
    assert outcomes[2].result == {"session_id": "ses_synthetic_saved"}
    assert outcomes[4].error.code == "disconnected"


@pytest.mark.parametrize("field", [
    "profile_id", "store_id", "generation", "operation_id", "attempt_id", "request_id",
])
def test_reply_from_another_process_or_request_cannot_settle_this_command(field):
    from renulus.harness_contracts import HarnessCommandIdentity, validate_command_outcome

    expected = HarnessCommandIdentity.model_validate({
        "protocol": "renulus-harness/1", "profile_id": "synthetic-profile",
        "store_id": "synthetic-runtime-store", "generation": "process-one",
        "operation_id": "operation-one", "attempt_id": "attempt-one",
        "request_id": "request-three",
    })
    reply = fixture("command-outcomes.json")[2]
    assert validate_command_outcome(reply, expected=expected).outcome == "committed_reference"
    reply[field] = "other-identity"
    with pytest.raises(ValueError, match="identity"):
        validate_command_outcome(reply, expected=expected)


def test_checked_schema_accepts_the_independent_host_and_ipc_examples():
    schema = json.loads((FIXTURES.parents[1] / "harness.schema.json").read_text("utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(fixture("paired-store-prepared.json"))
    reference_schema = {**schema, "$ref": "#/$defs/HarnessEngineReference"}
    Draft202012Validator(reference_schema).validate(fixture("engine-reference.json"))
    reply_schema = {**schema, "$ref": "#/$defs/HarnessCommandOutcome"}
    for reply in fixture("command-outcomes.json"):
        Draft202012Validator(reply_schema).validate(reply)


@pytest.mark.parametrize("pending", ["domain_store", "runtime_store"])
def test_portable_schema_also_requires_both_validations_for_activation(pending):
    schema = json.loads((FIXTURES.parents[1] / "harness.schema.json").read_text("utf-8"))
    value = fixture("paired-store-prepared.json")
    value["state"] = "active"
    value["domain_store"]["validation"] = "valid"
    value["runtime_store"]["validation"] = "valid"
    Draft202012Validator(schema).validate(value)
    value[pending]["validation"] = "pending"
    assert not Draft202012Validator(schema).is_valid(value)


@pytest.mark.parametrize("rejection", fixture("manifest-rejections.json"))
def test_python_and_portable_schema_refuse_the_published_incompatible_examples(rejection):
    schema = json.loads((FIXTURES.parents[1] / "harness.schema.json").read_text("utf-8"))
    value = fixture("paired-store-prepared.json")
    target = value
    for key in rejection["path"][:-1]:
        target = target[key]
    target[rejection["path"][-1]] = rejection["value"]
    with pytest.raises(ValidationError):
        PairedStoreManifest.model_validate(value)
    assert not Draft202012Validator(schema).is_valid(value)


def test_terminal_reply_requires_a_result_or_structured_error():
    from renulus.harness_contracts import HarnessCommandOutcome

    reply = fixture("command-outcomes.json")[2]
    del reply["result"]
    with pytest.raises(ValidationError, match="result or error"):
        HarnessCommandOutcome.model_validate(reply)
    schema = json.loads((FIXTURES.parents[1] / "harness.schema.json").read_text("utf-8"))
    assert not Draft202012Validator({**schema, "$ref": "#/$defs/HarnessCommandOutcome"}).is_valid(reply)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), -float("inf")])
def test_command_result_cannot_silently_convert_nonfinite_numbers_to_null(number):
    from renulus.harness_contracts import HarnessCommandOutcome

    reply = fixture("command-outcomes.json")[2]
    reply["result"] = {"nested": [1.25, {"value": number}]}
    with pytest.raises(ValidationError, match="finite"):
        HarnessCommandOutcome.model_validate(reply)
    with pytest.raises(ValidationError, match="finite"):
        HarnessCommandOutcome.model_validate_json(json.dumps(reply))
