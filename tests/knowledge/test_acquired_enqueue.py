"""Acquired canonical enqueue stays independent of serial CPU extraction."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from test_acquired import Case, offline
from test_repository import repository


def test_acquired_batch_and_replay_finish_before_blocked_extraction_releases(repository, tmp_path):
    case = Case(tmp_path / "collection")
    for version in range(2, 6):
        case.items.extend(Case(case.root, version=version).items)
    collection = case.register(repository)
    assert len(case.selected) == 5
    originals = {item["local_path"]: (case.root / item["local_path"]).read_bytes() for item in case.items}
    started, release = Event(), Event()
    extractor = repository.extractor

    class Blocked:
        def extract_file(self, path, title):
            output = extractor.extract_file(path, title)
            started.set()
            assert release.wait(20)
            return output

    repository.extractor = Blocked()
    background = repository.import_text("Synthetic CPU extraction in progress", process=False)
    with ThreadPoolExecutor(max_workers=2) as pool:
        extracting = pool.submit(repository.run_job, background["job"]["id"])
        try:
            assert started.wait(10)
            adopted = pool.submit(collection.import_next, limit=5).result(timeout=10)
            assert not release.is_set() and not extracting.done()
            assert adopted["queued"] == 5
            assert adopted["newly_queued"] == 5 and adopted["done"]
            jobs = {result["job"]["id"] for result in adopted["results"]}
            assert len(jobs) == 5
            assert all(repository.get_job(job)["state"] == "queued" for job in jobs)
            replayed = pool.submit(collection.import_selected, case.selected).result(timeout=10)
            assert {result["job"]["id"] for result in replayed["results"]} == jobs
            assert len(repository.list_documents()["documents"]) == 6
            repository.update_source_status({"contract_version": 1, "event_id": "restriction-during-extraction",
                "source_id": "L02", "identity": {"pmcid": "PMC90001"}, "scope": {},
                "changes": {"retracted": True}, "evidence": [{"inspected": True}]})
            denied = pool.submit(collection.import_selected, case.selected).result(timeout=10)
            assert denied["queued"] == 0
            assert all(result["code"] == "article_status_unavailable" for result in denied["results"])
            assert not release.is_set() and not extracting.done()
            assert len(repository.list_documents()["documents"]) == 6
        finally:
            release.set()
        assert extracting.result(timeout=10)["state"] == "ready"
    assert originals == {path: (case.root / path).read_bytes() for path in originals}
