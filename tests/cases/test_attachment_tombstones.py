# SPDX-License-Identifier: MIT
"""A removed saved Case original stays removed through real older ZIP restore."""
import shutil

import pytest

from renulus.cases.models import StartCase
from renulus.cases.repository import CaseRepository
from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.storage.recovery_archive import backup_to
from renulus.storage.recovery_segmented import backup_segmented_to

from .test_saved_originals import synthetic_original


@pytest.mark.parametrize("format_version", [1, 2])
def test_removed_saved_attachment_survives_older_zip_restore(tmp_path, format_version):
    services = create_app(tmp_path / "case-removal-profile").state.services
    cases = services.registry["cases"]
    original = synthetic_original(marker="FICTIONAL_REMOVED_SAVED_ORIGINAL")
    case = cases.start(StartCase(text="Fictional saved original removal check"))
    case = cases.attach(case["id"], case["revision"], original)
    saved = cases.save(case["id"], case["revision"])
    archive = services.paths.cache / f"older-case-{format_version}.zip"
    writer = backup_to if format_version == 1 else backup_segmented_to
    writer(services, archive)
    removed = cases.remove_attachment(case["id"], original["id"], saved["revision"])
    assert not services.db.is_deleted("case_attachment", original["id"])
    cases.save(case["id"], removed["revision"])
    assert services.db.is_deleted("case_attachment", original["id"])
    recovery = services.registry["data_recovery"]
    identifier, directory = recovery.begin_preview()
    keep = False
    try:
        shutil.copyfile(archive, directory / "input.zip")
        preview = recovery.complete_preview(identifier, directory)
        keep = True
    finally:
        recovery.end_upload(directory, keep=keep)
    recovery.restore_preview(identifier, preview["exported_at"], True)
    restarted = CaseRepository(services)
    assert restarted.get(case["id"])["attachments"] == []
    with pytest.raises(ApiError) as unavailable:
        restarted.original(case["id"], original["id"])
    assert unavailable.value.status == 404
    assert not services.db.fetch_all("SELECT * FROM case_attachment_parts WHERE attachment_id=?", (original["id"],))
