# SPDX-License-Identifier: MIT
"""Owned synthetic Home checks; no live inference, credentials or owner profile."""
import json

import pytest
from pydantic import ValidationError

from renulus.study.home_models import HomePreferences, SuggestionBundle


def bundle():
    return {kind: [f"Synthetic {kind} learning prompt {i}" for i in range(5)]
            for kind in ("explain", "case", "practice")}


def test_absent_name_and_normalised_chosen_name():
    assert HomePreferences().doctor_name is None
    assert HomePreferences(doctor_name="   ").doctor_name is None
    assert HomePreferences(doctor_name="  Ada  ").doctor_name == "Ada"


@pytest.mark.parametrize("name", [12, False, [], {}, "x" * 81, "Ada\nByron", "Ada\u202eByron", "Ada\x00Byron"])
def test_name_rejects_types_lengths_controls_and_bidi(name):
    with pytest.raises(ValidationError):
        HomePreferences(doctor_name=name)


@pytest.mark.parametrize("change", ["missing", "extra", "short", "long", "empty", "number", "duplicate", "control"])
def test_whole_bundle_validation_rejects_partial_or_unsafe_output(change):
    value = bundle()
    if change == "missing":
        del value["practice"]
    elif change == "extra":
        value["answer_key"] = "not allowed"
    elif change == "short":
        value["case"].pop()
    elif change == "long":
        value["case"].append("sixth")
    elif change == "empty":
        value["explain"][0] = "   "
    elif change == "number":
        value["explain"][0] = 1
    elif change == "duplicate":
        value["case"][0] = value["explain"][0].upper()
    elif change == "control":
        value["case"][0] = "control\u202e"
    with pytest.raises(ValidationError):
        SuggestionBundle.model_validate_json(json.dumps(value))


def test_whole_bundle_has_exactly_fifteen_prompts():
    valid = SuggestionBundle.model_validate_json(json.dumps(bundle()))
    assert len(valid.explain + valid.case + valid.practice) == 15
