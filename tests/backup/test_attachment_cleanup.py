# SPDX-License-Identifier: MIT
"""Actual transaction/crash boundaries for chat-owned original cleanup."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.storage import attachment_cleanup
from renulus.storage.backup import export_records
from .test_design_c_attachments import seed_attachment


def deletion_in(conn, services, identifier):
    for row in conn.execute("SELECT id FROM knowledge_attachment_originals WHERE attachment_id=?", (identifier,)):
        services.db.mark_deleted("attachment_original", row["id"], conn)
    services.db.mark_deleted("attachment", identifier, conn)
    conn.execute("DELETE FROM knowledge_attachments WHERE id=?", (identifier,))
    attachment_cleanup.enqueue_in(conn, [{"attachment_id": identifier,
                                         "relative_directory": "library/attachments/" + identifier}])


def test_rollback_preserves_original_and_journal_never_exports(tmp_path):
    services = create_app(tmp_path / "rollback").state.services
    _, identifier, original, payload = seed_attachment(services)
    path = Path(services.db.fetch_one("SELECT original_path FROM knowledge_attachment_originals WHERE id=?", (original,))["original_path"])
    with pytest.raises(RuntimeError):
        with services.db.transaction() as conn:
            deletion_in(conn, services, identifier)
            raise RuntimeError("SYNTHETIC commit failure")
    assert path.read_bytes() == payload
    assert services.db.fetch_one("SELECT id FROM knowledge_attachments WHERE id=?", (identifier,))
    assert attachment_cleanup.drain(services) == {"removed": 0, "pending": 0}
    with services.db.transaction() as conn:
        deletion_in(conn, services, identifier)
    assert path.exists()  # Commit does not touch files.
    assert attachment_cleanup.JOURNAL not in str(export_records(services))
    reopened_app = create_app(services.paths.root)
    reopened = reopened_app.state.services
    with TestClient(reopened_app):
        assert not path.exists()  # Real app startup drains the committed journal.
    assert not path.exists()
    assert attachment_cleanup.drain(reopened) == {"removed": 0, "pending": 0}


def test_failed_file_cleanup_remains_journalled_for_restart(tmp_path, monkeypatch):
    services = create_app(tmp_path / "retry").state.services
    _, identifier, _, _ = seed_attachment(services)
    with services.db.transaction() as conn:
        deletion_in(conn, services, identifier)
    with monkeypatch.context() as patch:
        patch.setattr(attachment_cleanup, "remove_owned_tree", lambda *_: (_ for _ in ()).throw(OSError("SYNTHETIC locked file")))
        assert attachment_cleanup.drain(services) == {"removed": 0, "pending": 1}
    assert attachment_cleanup.drain(services) == {"removed": 1, "pending": 0}


def test_cleanup_refuses_live_originals_and_unsafe_paths(tmp_path):
    services = create_app(tmp_path / "bounds").state.services
    _, identifier, original, _ = seed_attachment(services)
    path = Path(services.db.fetch_one("SELECT original_path FROM knowledge_attachment_originals WHERE id=?", (original,))["original_path"])
    with services.db.transaction() as conn:
        services.db.mark_deleted("attachment", identifier, conn)
        attachment_cleanup.enqueue_in(conn, [{"attachment_id": identifier,
                                             "relative_directory": "library/attachments/" + identifier}])
    assert attachment_cleanup.drain(services) == {"removed": 0, "pending": 1}
    assert path.exists()
    for entry in ({"attachment_id": identifier, "relative_directory": "library/knowledge"},
                  {"attachment_id": "..", "relative_directory": "library/attachments/.."}):
        with pytest.raises(ApiError):
            with services.db.transaction() as conn:
                attachment_cleanup.enqueue_in(conn, [entry])
