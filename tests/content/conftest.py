# SPDX-License-Identifier: MIT
from pathlib import Path
import pytest

from renulus.content.repository import ContentRepository
from renulus.storage import Database

ROOT = Path(__file__).parents[2]
PACK = ROOT / "content/packs/renulus-foundations/1.0.0"


@pytest.fixture
def database(tmp_path):
    db = Database(tmp_path / "isolated/state/renulus.sqlite3")
    db.apply_migration("content-001", (ROOT / "runtime/renulus/content/schema.sql").read_text(encoding="utf-8"))
    return db


@pytest.fixture
def repository(database):
    return ContentRepository(database, PACK.parent.parent)


@pytest.fixture
def installed(repository):
    repository.install_pack(PACK)
    return repository
