from pathlib import Path

import pytest

from renulus.storage import AppPaths


@pytest.fixture
def app_paths(tmp_path):
    return AppPaths.create(tmp_path / "profile", Path(__file__).resolve().parents[2])


@pytest.fixture
def synthetic_go_approval(monkeypatch):
    """Simulate future approval only in synthetic protocol tests.

    No production/user switch exists. Default-policy tests never use this
    fixture and must deny Go learning traffic. No model allowlist is changed.
    """
    from renulus.runtime import policy
    monkeypatch.setattr(policy, "GO_LEARNING_ELIGIBILITY", "confirmed")
