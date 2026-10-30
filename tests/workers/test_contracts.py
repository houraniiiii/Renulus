import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from renulus.worker_contracts import COMMAND, Reply, LaunchConfig
from renulus.workers.generate import generated_files, schema_document
from .support import ROOT, command, output


def test_generated_files_are_exactly_current_and_valid_json_schema():
    for name, value in generated_files().items():
        assert (ROOT / "packages" / "contracts" / name).read_text(encoding="utf-8") == value
    Draft202012Validator.check_schema(schema_document())
    value = command("embedding.embed", {"texts":["Synthetic AKI note"],"query":False,"output":output()})
    COMMAND.validate_python(value)
    Draft202012Validator(schema_document()).validate(value)


@pytest.mark.parametrize("mutate", [
    lambda v: v.update(extra="not accepted"),
    lambda v: v.update(authority_epoch=True),
    lambda v: v.update(grant_revision=1.5),
    lambda v: v.update(context_epoch=float("nan")),
    lambda v: v.update(request_id="bad\n"),
    lambda v: v.update(protocol="renulus-worker/2"),
    lambda v: v.update(command="arbitrary.sql"),
    lambda v: v["input"].update(path="C:/private"),
    lambda v: v["input"].update(texts=["x"]*65),
])
def test_strict_command_rejects_unknown_unsafe_and_nonfinite_values(mutate):
    value = command("embedding.embed", {"texts":["Synthetic CKD note"],"query":False,"output":output()})
    mutate(value)
    with pytest.raises(ValidationError):
        COMMAND.validate_python(value)


def test_every_object_schema_is_closed_and_each_outcome_is_declared():
    schema = schema_document()
    for name, node in schema["$defs"].items():
        if node.get("type") == "object":
            assert node["additionalProperties"] is False, name
    assert set(schema["$defs"]["Reply"]["properties"]["outcome"]["enum"]) == {
        "rejected_before_admission", "accepted_pending", "committed_reference",
        "cancelled_settled", "uncertain_after_disconnect"}


def test_shared_base_reexports_and_optional_launch_are_compatible():
    from renulus import worker_contracts
    from renulus.workers import contract_base
    from .support import config
    for name in ("Model", "ProcessIdentity", "Identity", "Revisions", "OutputGrant", "ArtifactResult"):
        assert getattr(worker_contracts, name) is getattr(contract_base, name)
    value = config().model_dump(exclude={"derived"})
    assert LaunchConfig.model_validate(value).derived is None
    schema = schema_document()
    Draft202012Validator({"$ref": "#/$defs/LaunchConfig", "$defs": schema["$defs"]}).validate(value)
