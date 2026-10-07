from types import SimpleNamespace

import pytest

from renulus.assessment.generated_repository import GeneratedPracticeRepository
from renulus.assessment.generated_streaming import safe_error
from renulus.contracts import ApiError
from renulus.runtime.policy import learning_usage


@pytest.mark.parametrize("selected,eligibility,available", [
    ("opencode-go", learning_usage("opencode-go"), True),
    ("opencode-go", None, False),
    ("opencode-go", {"generation_allowed": False}, False),
    ("codex", None, True),
    ("codex", {"generation_allowed": True}, True),
])
def test_app_approved_go_enables_practice_and_old_disabled_runtime_remains_honest(selected, eligibility, available):
    row = {"provider": selected, "status": "connected", "models": [{"availability": "available"}]}
    if eligibility is not None:
        row["learning_use"] = eligibility
    provider = SimpleNamespace(status=lambda: {"selected_provider": selected, "connections": [row]})
    repo = GeneratedPracticeRepository(SimpleNamespace(registry={"provider": provider}, db=None))
    result = repo.capabilities()
    assert result["available"] is available
    assert result["live_provider_verified"] is False
    if not available:
        assert result["code"] == "learning_use_unverified"
        assert result["retryable"] is False
        assert "paused" in result["reason"]


def test_provider_gate_during_generation_preserves_public_code_without_private_message():
    result = safe_error(ApiError("learning_use_unverified", "PRIVATE_SYNTHETIC_DETAIL", 403, False))
    assert result["code"] == "learning_use_unverified" and result["retryable"] is False
    assert "PRIVATE_SYNTHETIC_DETAIL" not in result["message"]
