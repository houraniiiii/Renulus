from pathlib import Path

import pytest

from renulus.storage import AppPaths


@pytest.fixture
def app_paths(tmp_path):
    return AppPaths.create(tmp_path / "profile", Path(__file__).resolve().parents[2])
