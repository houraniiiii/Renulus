# SPDX-License-Identifier: MIT
import shutil

import pytest

from renulus.content.api import create_router
from renulus.content.repository import ContentRepository
from renulus.services import Services
from renulus.storage import AppPaths
from .helpers import PACK, read, refresh, write


@pytest.fixture
def pack_root(tmp_path):
    root = tmp_path / "bundles"
    shutil.copytree(PACK.parent, root / "renulus-foundations")
    return root


def boot(database, tmp_path, root=PACK.parent.parent, selection=None):
    services = Services(AppPaths.create(tmp_path / "isolated-profile"), database)
    services.registry["content_pack_root"] = root
    if selection is not None:
        services.registry["content_pack_selection"] = selection
    create_router(services)
    return services.registry["content"], services.registry["content_bootstrap"]


def make_release(root, version, *, identity="renulus-foundations"):
    """Only synthetic release metadata; original content bytes are test inputs."""
    path = root / identity / version
    shutil.copytree(PACK.parent / "1.1.0", path)
    manifest = read(path, "manifest.json")
    manifest.update(id=identity, version=version)
    write(path, "manifest.json", manifest)
    refresh(path)
    return path


def private_snapshots(repository):
    return {q["id"]: repository.get_question_version(q["id"], q["version"])
            for q in repository.list_question_summaries()}


@pytest.mark.parametrize("prior", ["1.0.0", "1.0.1"])
def test_bootstrap_upgrades_actual_predecessor_and_preserves_every_pin(database, tmp_path, prior):
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(PACK.parent / prior)
    pinned = private_snapshots(repository)
    repository, outcome = boot(database, tmp_path)
    assert outcome["status"] == "activated" and outcome["reason"] == "newer_bundled_release"
    assert repository.active_manifest()["version"] == "1.1.0"
    assert len(repository.list_question_summaries()) == 160
    assert len(repository.list_cases()) == 26
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 2
    for identity, snapshot in pinned.items():
        assert repository.get_question_version(identity, 1) == snapshot
    before = private_snapshots(repository)
    repository, outcome = boot(database, tmp_path)
    assert outcome["reason"] == "active_version_not_older"
    assert private_snapshots(repository) == before
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 2


def test_withdrawn_prior_does_not_become_an_implicitly_fresh_profile(database, tmp_path):
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(PACK)
    original = repository.get_question_version("RN-CKD-001", 1)
    repository.withdraw_pack("renulus-foundations", "1.0.0", "Synthetic review hold")
    repository, outcome = boot(database, tmp_path)
    assert outcome["reason"] == "historical_profile_inactive"
    assert repository.active_manifest() is None and repository.list_questions() == []
    assert repository.get_question_version("RN-CKD-001", 1) == {**original, "current_version": None}
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 1


@pytest.mark.parametrize("withdraw_target", [False, True])
def test_installed_inactive_or_withdrawn_target_is_not_reselected(database, tmp_path, withdraw_target):
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(PACK.parent / "1.1.0")
    if withdraw_target:
        repository.withdraw_pack("renulus-foundations", "1.1.0", "Synthetic review hold")
    repository.install_pack(PACK.parent / "1.0.1")
    before = private_snapshots(repository)
    repository, outcome = boot(database, tmp_path)
    assert outcome["reason"] == "target_previously_installed"
    assert repository.active_manifest()["version"] == "1.0.1"
    assert private_snapshots(repository) == before
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 2


def test_newer_active_version_is_not_downgraded_to_bundled_release(database, tmp_path):
    path = make_release(tmp_path / "external-test-bundle", "2.0.0")
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(path)
    before = private_snapshots(repository)
    repository, outcome = boot(database, tmp_path)
    assert outcome["reason"] == "active_version_not_older"
    assert repository.active_manifest()["version"] == "2.0.0"
    assert private_snapshots(repository) == before
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 1


def test_other_active_lineage_is_preserved(database, tmp_path):
    path = make_release(tmp_path / "external-test-bundle", "1.0.0", identity="synthetic-other")
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(path)
    repository, outcome = boot(database, tmp_path)
    assert outcome["reason"] == "different_active_lineage"
    assert repository.active_manifest()["id"] == "synthetic-other"
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 1


def test_latest_published_selection_uses_numeric_order_and_ignores_draft(database, tmp_path, pack_root):
    make_release(pack_root, "1.9.0")
    make_release(pack_root, "1.10.0")
    draft = make_release(pack_root, "2.0.0")
    manifest = read(draft, "manifest.json")
    manifest["state"] = "draft"
    write(draft, "manifest.json", manifest)
    (pack_root / "renulus-foundations/9.0.0").mkdir()
    (pack_root / "renulus-foundations/10.0.0-preview").mkdir()
    repository, outcome = boot(database, tmp_path, pack_root)
    assert outcome["status"] == "activated"
    assert repository.active_manifest()["version"] == "1.10.0"
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 1


@pytest.mark.parametrize("prior", [None, "1.0.1"])
def test_corrupt_latest_fails_without_fallback_or_partial_install(database, tmp_path, pack_root, prior):
    repository = ContentRepository(database, pack_root)
    if prior:
        repository.install_pack(pack_root / "renulus-foundations" / prior)
    before = private_snapshots(repository)
    path = make_release(pack_root, "1.2.0")
    questions = read(path, "questions.json")
    questions[-1]["stem"] += " Synthetic hash tampering."
    write(path, "questions.json", questions)
    repository, outcome = boot(database, tmp_path, pack_root)
    assert outcome["status"] == "unavailable"
    assert outcome["error"]["code"] == "invalid_content_pack"
    active = repository.active_manifest()
    assert (active["version"] if active else None) == prior
    assert private_snapshots(repository) == before
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == int(prior is not None)


@pytest.mark.parametrize("field,value", [("id", "synthetic-wrong-id"), ("version", "8.0.0")])
def test_bundled_manifest_must_match_directory_identity(database, tmp_path, pack_root, field, value):
    repository = ContentRepository(database, pack_root)
    repository.install_pack(pack_root / "renulus-foundations/1.0.1")
    path = make_release(pack_root, "1.2.0")
    manifest = read(path, "manifest.json")
    manifest[field] = value
    write(path, "manifest.json", manifest)
    repository, outcome = boot(database, tmp_path, pack_root)
    assert outcome["error"]["code"] == "invalid_content_pack"
    assert repository.active_manifest()["version"] == "1.0.1"
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 1


def test_install_conflict_rolls_back_and_reports_failure_without_losing_pins(database, tmp_path, pack_root):
    repository = ContentRepository(database, pack_root)
    repository.install_pack(pack_root / "renulus-foundations/1.0.1")
    before = private_snapshots(repository)
    path = make_release(pack_root, "1.2.0")
    sources = read(path, "sources.json")
    sources[0]["check_note"] += " Synthetic mutation of pinned source evidence."
    write(path, "sources.json", sources)
    refresh(path)
    repository, outcome = boot(database, tmp_path, pack_root)
    assert outcome["error"]["code"] == "content_conflict"
    assert repository.active_manifest()["version"] == "1.0.1"
    assert private_snapshots(repository) == before
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 1
    assert database.fetch_one("SELECT COUNT(*) n FROM content_question_versions")["n"] == 106


def test_withdrawn_question_blocks_automatic_upgrade_and_preserves_old_evidence(database, tmp_path):
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(PACK.parent / "1.0.1")
    repository.withdraw_question("RN-CKD-001", 1, "Synthetic item review hold")
    pinned = repository.get_question_version("RN-CKD-001", 1)
    repository, outcome = boot(database, tmp_path)
    assert outcome["error"]["code"] == "content_conflict"
    assert repository.active_manifest()["version"] == "1.0.1"
    assert len(repository.list_question_summaries()) == 105
    assert repository.get_question_version("RN-CKD-001", 1) == pinned
    assert database.fetch_one("SELECT COUNT(*) n FROM content_question_versions")["n"] == 106
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 1


def test_integrator_can_select_exact_bundled_version_for_fresh_profile(database, tmp_path):
    repository, outcome = boot(database, tmp_path, selection={
        "id": "renulus-foundations", "version": "1.0.1", "upgrade_from": ["1.0.0"],
    })
    assert outcome["status"] == "activated"
    assert repository.active_manifest()["version"] == "1.0.1"
    assert len(repository.list_question_summaries()) == 106


@pytest.mark.parametrize("allowed,version", [(["1.0.0"], "1.1.0"), (["1.0.1"], "1.0.0")])
def test_explicit_upgrade_allowlist_is_honored(database, tmp_path, allowed, version):
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(PACK)
    repository, outcome = boot(database, tmp_path, selection={
        "id": "renulus-foundations", "version": "1.1.0", "upgrade_from": allowed,
    })
    assert repository.active_manifest()["version"] == version
    assert outcome["status"] == ("activated" if version == "1.1.0" else "preserved")


@pytest.mark.parametrize("selection", [
    {"id": "../../outside"}, {"version": "1.2.0-preview"},
    {"upgrade_from": ["not-a-version"]}, {"unexpected": "synthetic"},
])
def test_invalid_registry_selection_preserves_active_data(database, tmp_path, selection):
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(PACK)
    before = private_snapshots(repository)
    repository, outcome = boot(database, tmp_path, selection=selection)
    assert outcome["status"] == "unavailable" and outcome["error"]["code"] == "invalid_content_pack"
    assert repository.active_manifest()["version"] == "1.0.0"
    assert private_snapshots(repository) == before


def test_missing_bundle_leaves_fresh_content_unavailable(database, tmp_path):
    repository, outcome = boot(database, tmp_path, tmp_path / "missing-bundles")
    assert outcome["error"]["code"] == "content_not_found"
    assert repository.active_manifest() is None and repository.list_topics() == []
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 0


def test_explicit_older_selection_cannot_downgrade_active_bundle(database, tmp_path):
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(PACK.parent / "1.1.0")
    repository, outcome = boot(database, tmp_path, selection={"version": "1.0.0"})
    assert outcome["reason"] == "active_version_not_older"
    assert repository.active_manifest()["version"] == "1.1.0"
