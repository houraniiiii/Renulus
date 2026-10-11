# SPDX-License-Identifier: MIT
"""Legacy public writer cannot reopen a harness-owned saved transcript."""
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.server import create_app


@pytest.mark.parametrize("native_session", [None, "synthetic-native-session"])
def test_legacy_prepare_rejects_pending_and_committed_native_mapping(tmp_path, native_session):
    services = create_app(tmp_path).state.services
    learn = services.get("learn")
    thread = learn.create_thread("Synthetic kidney physiology")
    # Explicit reference-only owner fixture. Actual mapping/store acceptance
    # belongs to the bridge's connected SDK receipt.
    if not services.db.fetch_one("SELECT 1 FROM sqlite_master WHERE name='learn_harness_mappings'"):
        services.db.apply_migration("synthetic-native-owner",
            "CREATE TABLE learn_harness_mappings(thread_id TEXT PRIMARY KEY,session_id TEXT,mapping_json TEXT,profile_id TEXT,store_id TEXT,create_request_id TEXT,process_generation TEXT);")
    services.db.execute("INSERT INTO learn_harness_mappings(thread_id,session_id,mapping_json,profile_id,store_id,create_request_id,process_generation) VALUES(?,?,?,?,?,?,?)",
        (thread["id"], native_session, "{}" if native_session else None,
         "synthetic-profile", "synthetic-runtime", None, None))
    with pytest.raises(ApiError) as error:
        learn.prepare("Explain renal perfusion", ContextScope(kind=Scope.STUDY),
            thread["id"], None, "direct", "second-owner")
    assert error.value.code == "harness_owned_thread"
    reopened = learn.get_thread(thread["id"])
    assert reopened["messages"] == [] and reopened["runs"] == []
