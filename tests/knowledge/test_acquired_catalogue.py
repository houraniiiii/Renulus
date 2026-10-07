"""SQLite-only catalogue selection, including a large synthetic receipt count."""
from pathlib import Path

import pytest

from renulus.contracts import ApiError
from renulus.knowledge.collection import CollectionCatalogue
from test_acquired import Case, offline
from test_repository import repository


ROWS = [
    ("ready-b", "L02", "Kidney study", "eligible"),
    ("ready-a", "L02", "Kidney study", "eligible"),
    ("pending-b", "L02", r"Dialysis 100%_proof\route", "inspection_required"),
    ("pending-a", "L02", r"Dialysis 100%_proof\route", "inspection_required"),
    ("reserved", "E02", "Kidney 100% examination", "reserved"),
    ("nc", "L02", "Kidney NC", "article_permission_required"),
    ("metadata", "L02", "Kidney metadata", "acquired_payload_unavailable"),
    ("notice", "L03", "Kidney notice", "article_status_unavailable"),
    ("teaching", "R01", "Kidney teaching", "eligible"),
    ("other-pending", "L03", "Kidney pending", "inspection_required"),
]


def seed(repository, rows):
    with repository.db.transaction() as conn:
        conn.executemany("INSERT INTO knowledge_catalogue(id,collection_path,source_id,title,reserved,eligibility,metadata_json,rights_json,checked_at) VALUES(?,?,?,?,?,?,?,?,?)",
            [(identifier, "raw/" + source + "/" + identifier + ".xml", source, title,
              int(eligibility == "reserved"), eligibility, "{}", "{}", "2026-10-04T12:00:00Z")
             for identifier, source, title, eligibility in rows])


@pytest.fixture
def catalogue(repository, tmp_path):
    seed(repository, ROWS)
    return CollectionCatalogue(repository, tmp_path / "unopened-collection")


@pytest.mark.parametrize("eligibility,expected", [
    ("eligible", ["ready-a", "ready-b", "teaching"]),
    ("inspection_required", ["pending-a", "pending-b", "other-pending"]),
    ("reserved", ["reserved"]),
    ("unavailable", ["nc", "metadata", "notice"]),
])
def test_category_pages_count_all_matches_before_offset_and_keep_stable_order(catalogue, eligibility, expected):
    first = catalogue.list(eligibility=eligibility, limit=1)
    assert set(first) == {"entries", "total", "offset"}
    assert first["total"] == len(expected) and first["offset"] == 0
    assert [entry["id"] for entry in first["entries"]] == expected[:1]
    rest = catalogue.list(eligibility=eligibility, limit=250, offset=1)
    assert rest["total"] == len(expected) and rest["offset"] == 1
    assert [entry["id"] for entry in rest["entries"]] == expected[1:]
    empty = catalogue.list(eligibility=eligibility, offset=len(expected))
    assert empty["total"] == len(expected) and empty["entries"] == []


def test_no_filter_shape_source_filter_and_id_ties_remain_compatible(catalogue):
    result = catalogue.list()
    assert set(result) == {"entries", "total", "offset"} and result["total"] == len(ROWS)
    expected = sorted(ROWS, key=lambda row: (row[1], row[2], row[0]))
    assert [entry["id"] for entry in result["entries"]] == [row[0] for row in expected]
    assert all(entry["metadata"] == entry["rights"] == {} for entry in result["entries"])
    assert all(entry["processing_status"] == "acquired" for entry in result["entries"])
    filtered = catalogue.list(source_id="L02", eligibility="eligible", query="Kidney", offset=1)
    assert filtered["total"] == 2 and filtered["offset"] == 1
    assert [entry["id"] for entry in filtered["entries"]] == ["ready-b"]


@pytest.mark.parametrize("query,expected", [
    ("%", ["reserved", "pending-a", "pending-b"]),
    ("_", ["pending-a", "pending-b"]),
    ("\\", ["pending-a", "pending-b"]),
    (r"100%_proof\route", ["pending-a", "pending-b"]),
    ("' OR 1=1 --", []),
    (" dialysis ", []),
    (" L02 ", []),
    ("x" * 200, []),
])
def test_title_search_is_a_bounded_literal_substring(catalogue, query, expected):
    result = catalogue.list(query=query)
    assert result["total"] == len(expected)
    assert [entry["id"] for entry in result["entries"]] == expected


@pytest.mark.parametrize("kwargs", [{"eligibility": "failed"}, {"eligibility": ""},
    {"eligibility": ["eligible"]}, {"query": "x" * 201}, {"query": None}, {"query": 1}])
def test_invalid_filters_are_explained_before_database_access(catalogue, monkeypatch, kwargs):
    def unexpected(*args, **kwargs):
        raise AssertionError("Invalid filters must not query the catalogue")
    monkeypatch.setattr(catalogue.db, "fetch_one", unexpected)
    with pytest.raises(ApiError) as caught:
        catalogue.list(**kwargs)
    assert caught.value.code == "invalid_collection_filter" and caught.value.status == 422


def test_large_catalogue_filters_and_pages_without_registration_or_file_reads(repository, tmp_path, monkeypatch):
    count = 178558
    # No body/manifest exists. Every row is explicitly synthetic catalogue data.
    with repository.db.transaction() as conn:
        conn.execute("""WITH RECURSIVE receipts(n) AS (
            VALUES(1) UNION ALL SELECT n+1 FROM receipts WHERE n<?)
            INSERT INTO knowledge_catalogue(id,collection_path,source_id,title,reserved,
                eligibility,metadata_json,rights_json,checked_at)
            SELECT printf('synthetic_%06d',n),printf('raw/L02/%06d.xml',n),'L02',
                'Repeated synthetic JATS candidate',n%5=2,
                CASE n%5 WHEN 0 THEN 'eligible' WHEN 1 THEN 'inspection_required'
                    WHEN 2 THEN 'reserved' WHEN 3 THEN 'article_permission_required'
                    ELSE 'acquired_payload_unavailable' END,
                '{}','{}','2026-10-04T12:00:00Z' FROM receipts""", (count,))
    collection = CollectionCatalogue(repository, tmp_path / "unopened-collection")
    def unexpected(*args, **kwargs):
        raise AssertionError("Listing must not register, inspect or open collection files")
    monkeypatch.setattr(collection, "register", unexpected)
    monkeypatch.setattr(collection, "preview", unexpected)
    monkeypatch.setattr(Path, "open", unexpected)
    full = collection.list(limit=1001)
    assert full["total"] == count and len(full["entries"]) == 1000
    assert [entry["id"] for entry in full["entries"]] == [f"synthetic_{n:06d}" for n in range(1, 1001)]
    expected = [f"synthetic_{n:06d}" for n in range(1, count + 1, 5)]
    filters = {"source_id": "L02", "eligibility": "inspection_required", "query": "JATS"}
    offset, limit = 12345, 75
    first = collection.list(**filters, offset=offset, limit=limit)
    second = collection.list(**filters, offset=offset + limit, limit=limit)
    assert first["total"] == second["total"] == len(expected)
    assert [entry["id"] for entry in first["entries"]] == expected[offset:offset + limit]
    assert [entry["id"] for entry in second["entries"]] == expected[offset + limit:offset + 2 * limit]
    assert not {entry["id"] for entry in first["entries"]} & {entry["id"] for entry in second["entries"]}
    tail = collection.list(**filters, offset=len(expected) - 4, limit=limit)
    assert tail["total"] == len(expected) and [entry["id"] for entry in tail["entries"]] == expected[-4:]
    assert collection.list(**filters, offset=len(expected))["entries"] == []
    unavailable = collection.list(eligibility="unavailable", limit=1)
    assert unavailable["total"] == sum(n % 5 in (3, 4) for n in range(1, count + 1))


def test_filtered_listing_after_import_uses_persisted_state_and_never_recatalogues(repository, tmp_path, monkeypatch):
    case = Case(tmp_path / "collection")
    for item in case.items:
        item["topics"] = [{"topic_id": "T21", "topic": "Kidney transplantation"}]
    collection = case.register(repository)
    pending = collection.list(eligibility="inspection_required", query="Synthetic")
    assert pending["total"] == 1 and pending["entries"][0]["id"] == case.selected[0]
    assert pending["entries"][0]["metadata"]["topic_ids"] == ["T21"]
    assert not pending["entries"][0]["metadata"]["content_reviewed"]
    imported = collection.import_selected(case.selected)["results"][0]
    assert imported["status"] == "queued"
    def unexpected(*args, **kwargs):
        raise AssertionError("A filtered page must use the persisted catalogue")
    monkeypatch.setattr(collection, "register", unexpected)
    monkeypatch.setattr(collection, "preview", unexpected)
    monkeypatch.setattr(Path, "open", unexpected)
    assert collection.list(eligibility="inspection_required")["total"] == 0
    ready = collection.list(source_id="L02", eligibility="eligible", query="transplant")
    assert ready["total"] == 1 and ready["entries"][0]["processing_status"] == "queued"
    assert ready["entries"][0]["job_id"] == imported["job"]["id"]
    assert ready["entries"][0]["metadata"]["original_sha256"] == case.items[0]["sha256"]
    assert ready["entries"][0]["metadata"]["topic_ids"] == ["T21"]
    assert collection.list(eligibility="unavailable")["total"] == 1
