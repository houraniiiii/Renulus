from datetime import date
import json
import re
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
import pytest

from renulus.server import create_app
from renulus.updates.topic_queries import topic_expression
from test_updates import SequenceFetcher, SYNTHETIC_EVIDENCE
from test_publications import insert_entries


ARTICLE = {"id": "111111", "source": "MED", "doi": "10.5555/synthetic-original",
           "title": "Synthetic old publication, not real research", "firstPublicationDate": "2010-01-01",
           "pubTypeList": {"pubType": ["Journal Article"]}, "isOpenAccess": "Y"}


def result(*articles, hits=None):
    return json.dumps({"hitCount": len(articles) if hits is None else hits,
                       "resultList": {"result": list(articles)}}).encode()


@pytest.fixture
def check_date(monkeypatch):
    class CheckDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 7)
    monkeypatch.setattr("renulus.updates.literature.date", CheckDate)


def matches_topic_expression(expression, title, abstract=""):
    """Offline Boolean/phrase request oracle, not Europe PMC's server parser.

    Accept only explicitly scoped phrases, AND/OR and balanced parentheses.
    Each phrase must fit within a title or abstract; AND may span those fields.
    No stemming, synonyms, implicit operators or full-text matches are assumed.
    """
    tokens = re.findall(r'TITLE_ABS:"(?:\\.|[^"\\])*"|\(|\)|AND|OR', expression)
    # Check gaps separately: whitespace inside quoted phrases is significant.
    assert not re.sub(r'TITLE_ABS:"(?:\\.|[^"\\])*"|\(|\)|AND|OR|\s+', '', expression)
    position = 0
    fields = [" " + " ".join(re.findall(r"\w+", value.casefold())) + " "
              for value in (title, abstract)]

    def primary():
        nonlocal position
        token = tokens[position]
        position += 1
        if token == "(":
            value = disjunction()
            assert tokens[position] == ")"
            position += 1
            return value
        assert token.startswith('TITLE_ABS:"')
        phrase = json.loads(token[len("TITLE_ABS:"):])
        words = " " + " ".join(re.findall(r"\w+", phrase.casefold())) + " "
        return any(words in field for field in fields)

    def conjunction():
        nonlocal position
        value = primary()
        while position < len(tokens) and tokens[position] == "AND":
            position += 1
            right = primary()
            value = value and right
        return value

    def disjunction():
        nonlocal position
        value = conjunction()
        while position < len(tokens) and tokens[position] == "OR":
            position += 1
            right = conjunction()
            value = value or right
        return value

    matched = disjunction()
    assert position == len(tokens)
    return matched


# Synthetic relevance contrasts cover every translated heading. They exercise
# meaning/field boundaries rather than reproducing the runtime's term table.
TOPIC_EXAMPLES = [
    ("T01", "Tubular transport in renal epithelial cells", "Lung histology and physiology"),
    ("T02", "Diagnostic yield of a kidney biopsy", "Lung biopsy for interstitial disease"),
    ("T03", "Hyponatraemia and renal water handling", "Sodium storage in battery electrodes"),
    ("T04", "Hyperkalemia in chronic kidney disease", "Acidosis in exercising skeletal muscle"),
    ("T05", "Hyperparathyroidism in haemodialysis", "Bone disorder after traumatic fracture"),
    ("T06", "Recovery after acute kidney injury", "Acute lung injury in critical care"),
    ("T07", "Kidney support during sepsis", "Intensive care for isolated brain injury"),
    ("T09", "Hypertension in chronic kidney disease", "Pulmonary hypertension after embolism"),
    ("T11", "Drug associated acute interstitial nephritis", "Kidney function in interstitial lung disease"),
    ("T12", "Risk assessment in polycystic kidney disease", "Cystic fibrosis and inherited lung disease"),
    ("T13", "Prevention of recurrent kidney stones", "Gallbladder stones and intestinal obstruction"),
    ("T14", "Progression of diabetic nephropathy", "Diabetes with retinal complications"),
    ("T15", "Renal injury in thrombotic microangiopathy", "Complement activation in retinal degeneration"),
    ("T16", "Biopsy findings in lupus nephritis", "Systemic sclerosis affecting the skin"),
    ("T17", "Vaccination during peritoneal dialysis", "Respiratory infection in school children"),
    ("T18", "Monoclonal gammopathy of renal significance", "Paraproteins in isolated bone marrow disease"),
    ("T19", "Preventing drug induced nephrotoxicity", "Medicines causing liver toxicity"),
    ("T20", "Outcomes during peritoneal dialysis", "Extracorporeal support for isolated lung failure"),
    ("T22", "Bleeding risk after renal biopsy", "Liver biopsy and portal interventions"),
    ("T23", "Plasma exchange for renal disease", "Apheresis for neurological disease"),
    ("T24", "Pregnancy in chronic kidney disease", "Frailty after hip fracture"),
    ("T25", "Nutrition and exercise during hemodialysis", "Nutrition and rehabilitation after stroke"),
    ("T26", "Conservative management of kidney failure", "Palliative care for isolated lung cancer"),
    ("T27", "Recognition of hepatorenal syndrome", "Interfaces between cardiac and respiratory care"),
]


@pytest.mark.asyncio
async def test_installed_compound_headings_retrieve_scoped_concepts(tmp_path, check_date):
    service = create_app(tmp_path).state.services.registry["updates"]
    titles = {topic["id"]: topic["title"] for topic in service.services.registry["content"].list_topics()}
    examples = iter(TOPIC_EXAMPLES)
    requests = []

    class ConceptReplay:
        async def fetch(self, url, hosts, limit=2_000_000):
            topic_id, relevant, irrelevant = next(examples)
            parsed = urlparse(url)
            assert (parsed.scheme, parsed.netloc, parsed.path) == (
                "https", "www.ebi.ac.uk", "/europepmc/webservices/rest/search")
            assert hosts == {"www.ebi.ac.uk"} and limit == 2_000_000
            params = parse_qs(parsed.query)
            query = params.pop("query")[0]
            assert params == {"format": ["json"], "resultType": ["core"], "pageSize": ["25"]}
            suffix = " AND FIRST_PDATE:[2026-09-07 TO 2026-10-07] sort_date:y"
            assert query.endswith(suffix)
            expression = query[:-len(suffix)]
            # The root grouping keeps the date bound on every alternative.
            assert expression.startswith("(") and expression.endswith(")")
            assert f'TITLE_ABS:"{titles[topic_id]}"' not in expression
            assert matches_topic_expression(expression, relevant), topic_id
            assert matches_topic_expression(expression, "Synthetic follow-up", relevant), topic_id
            assert not matches_topic_expression(expression, irrelevant), topic_id
            assert not matches_topic_expression(expression, "Synthetic kidney imaging observations"), topic_id
            requests.append(query)
            return result({"id": str(800000 + len(requests)), "source": "MED",
                           "title": "Synthetic follow-up", "firstPublicationDate": "2026-10-07",
                           "abstractText": relevant + " SYNTHETIC_ABSTRACT_NOT_RETAINED",
                           "fullText": "SYNTHETIC_BODY_NOT_RETAINED"}), {}, url

    service.fetcher = ConceptReplay()
    topic_ids = [example[0] for example in TOPIC_EXAMPLES]
    for offset in range(0, len(topic_ids), 5):
        selected = topic_ids[offset:offset + 5]
        checked = await service.check_literature(selected, days=30)
        assert checked["state"] == "checked", checked
        assert checked["discovered"] == len(selected)
        assert all(item["records_checked"] == 1 and not item["truncated"] for item in checked["checks"])
    assert len(requests) == len(TOPIC_EXAMPLES) == 24
    assert {row["topic_ids"][0] for row in service.list_entries()} == set(topic_ids)
    assert all(row["review_state"] == "pending" for row in service.list_entries())
    with service.db.connect() as conn:
        dump = "\n".join(conn.iterdump())
    assert "SYNTHETIC_ABSTRACT_NOT_RETAINED" not in dump and "SYNTHETIC_BODY_NOT_RETAINED" not in dump


@pytest.mark.parametrize(("topic_id", "title", "abstract", "expected"), [
    ("T11", "Synthetic interstitial nephritis follow-up", "", True),
    ("T11", "Synthetic renal tubular disorders", "", True),
    ("T11", "Synthetic study", "Acquired Fanconi syndrome with tubular dysfunction", True),
    ("T11", "Synthetic study", "Chronic tubulointerstitial nephritis", True),
    ("T11", "Synthetic renal tubular acidosis", "", True),
    ("T11", "Synthetic Fanconi anemia", "Kidney measurements were normal", False),
    ("T11", "Interstitial lung disease and renal function", "Tubular adenoma", False),
    ("T11", "Interstitial", "Nephritis", False),
    ("T06", "Synthetic acute kidney disease follow-up", "", True),
    ("T03", "Synthetic hyponatremia follow-up", "Renal water handling was studied", True),
    ("T03", "Synthetic hyponatremia follow-up", "No organ specified", False),
    ("T15", "Synthetic complement activation", "Renal inflammation was studied", True),
    ("T15", "Synthetic complement activation", "Retinal inflammation was studied", False),
    ("T23", "Synthetic plasma exchange", "Renal disease was studied", True),
    ("T23", "Synthetic extracorporeal therapy", "Isolated respiratory disease", False),
])
def test_concept_alternatives_keep_renal_relevance(topic_id, title, abstract, expected):
    # Literal installed titles keep this semantic test independent of the map.
    labels = {"T11": "Tubular and interstitial disease", "T06": "Acute kidney injury and acute kidney disease",
              "T03": "Sodium, water and volume", "T15": "Thrombotic microangiopathy and complement",
              "T23": "Extracorporeal therapies and apheresis"}
    assert matches_topic_expression(topic_expression(topic_id, labels[topic_id]), title, abstract) is expected


@pytest.mark.asyncio
async def test_mapping_requires_both_exact_installed_identity_and_title(tmp_path, check_date):
    service = create_app(tmp_path).state.services.registry["updates"]
    pairs = [("T11", "Tubular and interstitial disease "), ("custom", "Tubular and interstitial disease"),
             ("T11", "tubular and interstitial disease"), ("T11", 'Custom "renal" topic'),
             ("T08", "Chronic kidney disease"), ("T10", "Glomerular diseases"),
             ("T21", "Kidney transplantation")]
    class Topics:
        def list_topics(self):
            return [{"id": topic_id, "title": title}]
    service.services.registry["content"] = Topics()
    service.fetcher = SequenceFetcher([result()] * len(pairs))
    for topic_id, title in pairs:
        checked = await service.check_literature([topic_id], days=30)
        assert checked["state"] == "checked" and checked["discovered"] == 0
        escaped = title.replace('"', '\\"')
        query = parse_qs(urlparse(service.fetcher.urls[-1]).query)["query"][0]
        assert query == f'TITLE_ABS:"{escaped}" AND FIRST_PDATE:[2026-09-07 TO 2026-10-07] sort_date:y'


def test_mapped_requests_reject_private_text_and_keep_caps(tmp_path, check_date):
    app = create_app(tmp_path)
    service = app.state.services.registry["updates"]
    client = TestClient(app)
    service.fetcher = SequenceFetcher([result(), result(*[
        {**ARTICLE, "id": str(700000 + index)} for index in range(25)], hits=26), RuntimeError("offline")])
    endpoint = "/api/v1/updates/literature/check"
    for extra in ("prompt", "case_text", "query"):
        response = client.post(endpoint, json={"topic_ids": ["T11"], extra: "SYNTHETIC_PRIVATE_TEXT"})
        assert response.status_code == 422
    for body in ({"topic_ids": ["T11", "SYNTHETIC_PRIVATE_TEXT"]},
                 {"topic_ids": ["T11"] * 6}, {"topic_ids": ["T11"], "days": 0},
                 {"topic_ids": ["T11"], "days": 91}):
        assert client.post(endpoint, json=body).status_code in (400, 422)
    assert service.fetcher.urls == []
    empty = client.post(endpoint, json={"topic_ids": ["T11"], "days": 1}).json()
    assert empty["state"] == "checked" and empty["checks"][0]["hit_count"] == 0
    assert empty["checks"][0]["truncated"] is False
    bounded = client.post(endpoint, json={"topic_ids": ["T11", "T11"], "days": 90}).json()
    assert bounded["state"] == "checked" and bounded["discovered"] == 25
    assert bounded["checks"] == [{"topic_id": "T11", "state": "checked", "discovered": 25,
                                  "records_checked": 25, "hit_count": 26, "truncated": True}]
    success = service.literature.checks()[0]["last_success_at"]
    failed = client.post(endpoint, json={"topic_ids": ["T11"]}).json()
    assert failed["state"] == "failed" and failed["checks"][0]["error_code"] == "literature_fetch_failed"
    assert service.literature.checks()[0]["last_success_at"] == success
    assert len(service.fetcher.urls) == 3  # no pagination, retries or duplicate-topic request
    queries = [parse_qs(urlparse(url).query) for url in service.fetcher.urls]
    assert "FIRST_PDATE:[2026-10-06 TO 2026-10-07] sort_date:y" in queries[0]["query"][0]
    assert "FIRST_PDATE:[2026-07-09 TO 2026-10-07] sort_date:y" in queries[1]["query"][0]
    assert all(params["pageSize"] == ["25"] and set(params) == {"query", "format", "resultType", "pageSize"}
               for params in queries)
    assert "SYNTHETIC_PRIVATE_TEXT" not in "".join(service.fetcher.urls)


@pytest.mark.asyncio
async def test_t21_query_scopes_recorded_unrelated_results_and_deduplicates(tmp_path, check_date):
    service = create_app(tmp_path).state.services.registry["updates"]
    # Titles from the parent's 035098b4 T21 UI receipt (updates-visible),
    # connected/connected-source-02/result.json. IDs are synthetic; no bodies
    # or live response are copied. This is a request-contract replay, not a
    # Europe PMC parser or proof of the corrected live result set.
    unrelated_titles = [
        "Codonopsis pilosula inulin-type fructan CPA ameliorates diarrhea-predominant "
        "irritable bowel syndrome via regulation of ER stress-induced autophagy and "
        "modulation of gut microbiota",
        "From molecular correction to functional rescue: delivery, tissue state, and "
        "immunobiology as the principal constraints on dystrophin-restoring therapy "
        "in Duchenne muscular dystrophy",
        "GULP1 Fuels Resistance to PD-1 Blockade through Lipid-Mediated Metabolic "
        "Reprogramming of Tumor-Associated Macrophages in Gastric Cancer",
    ]
    unrelated = [{"id": str(900001 + index), "source": "MED", "title": title}
                 for index, title in enumerate(unrelated_titles)]
    title_match = {"id": "900004", "source": "MED",
                   "title": "Synthetic kidney transplantation follow-up",
                   "firstPublicationDate": "2026-10-07"}
    abstract_match = {"id": "900005", "source": "MED",
                      "title": "Synthetic graft follow-up",
                      "firstPublicationDate": "2026-10-06",
                      "abstractText": "SYNTHETIC_ABSTRACT_ONLY kidney transplantation",
                      "fullText": "SYNTHETIC_BODY_MUST_NOT_PERSIST"}
    scoped_query = ('TITLE_ABS:"Kidney transplantation" AND '
                    'FIRST_PDATE:[2026-09-07 TO 2026-10-07] sort_date:y')
    legacy_query = '(Kidney transplantation) FIRST_PDATE:[2026-09-07 TO 2026-10-07]'

    class QueryReplay:
        def __init__(self):
            self.requests = []

        async def fetch(self, url, hosts, limit=2_000_000):
            parsed = urlparse(url)
            assert parsed.scheme == "https" and parsed.netloc == "www.ebi.ac.uk"
            assert parsed.path == "/europepmc/webservices/rest/search"
            assert hosts == {"www.ebi.ac.uk"} and limit == 2_000_000
            params = parse_qs(parsed.query)
            self.requests.append(params)
            responses = {legacy_query: result(*unrelated),
                         scoped_query: result(title_match, abstract_match, hits=40)}
            return responses[params["query"][0]], {"content-type": "application/json"}, url

    service.fetcher = QueryReplay()
    first = await service.check_literature(["T21", "T21"], days=30)
    entries = service.list_entries()
    assert {entry["external_id"] for entry in entries} == {"epmc:MED:900004", "epmc:MED:900005"}
    assert first["state"] == "checked" and first["discovered"] == 2
    assert first["checks"] == [{"topic_id": "T21", "state": "checked", "discovered": 2,
                                "records_checked": 2, "hit_count": 40, "truncated": True}]
    assert (await service.check_literature(["T21"], days=30))["discovered"] == 0
    assert service.fetcher.requests == [{"query": [scoped_query], "format": ["json"],
                                        "resultType": ["core"], "pageSize": ["25"]}] * 2
    assert len(service.list_entries()) == 2 and service.list_entries(reviewed_only=True) == []
    for entry in entries:
        assert entry["topic_ids"] == ["T21"] and entry["review_state"] == "pending"
        assert entry["source_metadata"]["reported_publication_status"] == "unknown"
    with service.db.connect() as conn:
        dump = "\n".join(conn.iterdump())
    assert "SYNTHETIC_ABSTRACT_ONLY" not in dump
    assert "SYNTHETIC_BODY_MUST_NOT_PERSIST" not in dump


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "phrase"), [
    ("chronic kidney disease", '"chronic kidney disease"'),
    ('Kidney "graft" follow-up', r'"Kidney \"graft\" follow-up"'),
    ('Tubular\\interstitial\\', r'"Tubular\\interstitial\\"'),
    ('Kidney\\" OR *:* OR TITLE_ABS:"cancer', r'"Kidney\\\" OR *:* OR TITLE_ABS:\"cancer"'),
    ('IgA & complement (C3): α/β + follow-up?', '"IgA & complement (C3): α/β + follow-up?"'),
])
async def test_canonical_topic_phrase_escaping_and_url_round_trip(tmp_path, check_date, label, phrase):
    service = create_app(tmp_path).state.services.registry["updates"]
    class Topics:
        def list_topics(self):
            return [{"id": "synthetic-topic", "title": label}]
    service.services.registry["content"] = Topics()
    service.fetcher = SequenceFetcher([result()])
    checked = await service.check_literature(["synthetic-topic"], days=7)
    assert checked["state"] == "checked" and checked["discovered"] == 0
    params = parse_qs(urlparse(service.fetcher.urls[0]).query)
    assert params == {"query": [f'TITLE_ABS:{phrase} AND FIRST_PDATE:[2026-09-30 TO 2026-10-07] sort_date:y'],
                      "format": ["json"], "resultType": ["core"], "pageSize": ["25"]}


@pytest.mark.asyncio
async def test_exact_refresh_older_than_100_retains_review_and_queues_changed_metadata(tmp_path):
    app = create_app(tmp_path)
    service = app.state.services.registry["updates"]
    original = service.literature.record(ARTICLE, ["T08"], "2010-01-02T00:00:00+00:00")
    old_id = original["entry_id"]
    service.review(old_id, "Synthetic prior review", ["T08"], "learner", "reviewed", evidence=SYNTHETIC_EVIDENCE)
    insert_entries(service, 251)
    assert old_id not in {row["id"] for row in service.list_entries()}
    changed = {**ARTICLE, "pubTypeList": {"pubType": ["Retracted Publication"]},
               "commentCorrectionList": {"commentCorrection": [{"id": "999999", "source": "MED", "type": "Retraction in"}]}}
    service.fetcher = SequenceFetcher([result(changed), result(changed), RuntimeError("offline"), result()])
    refreshed = await service.refresh_entry(old_id)
    assert refreshed["state"] == "changed"
    assert refreshed["entry"]["id"] == old_id and refreshed["entry"]["review_state"] == "reviewed"
    latest = refreshed["latest_entry"]
    assert latest["id"] != old_id and latest["review_state"] == "pending" and latest["kind"] == "retraction"
    assert latest["publication_date"] == "2010-01-01"
    assert service.affected.for_entry(latest["id"])["total"] == 0
    query = parse_qs(urlparse(service.fetcher.urls[0]).query)
    assert query["query"] == ["EXT_ID:111111 AND SRC:MED"]
    assert query["resultType"] == ["core"] and query["pageSize"] == ["1"]
    assert "sort" not in query
    assert "FIRST_PDATE" not in query["query"][0]
    assert (await service.refresh_entry(old_id))["state"] == "unchanged"
    prior = service.db.fetch_one("SELECT * FROM update_literature_records WHERE external_id='epmc:MED:111111'")
    failed = await service.refresh_entry(old_id)
    assert failed["state"] == "failed" and failed["entry"]["review_state"] == "reviewed"
    missing = await service.refresh_entry(old_id)
    assert missing["error"]["code"] == "literature_record_unavailable"
    current = service.db.fetch_one("SELECT * FROM update_literature_records WHERE external_id='epmc:MED:111111'")
    assert current["last_success_at"] == prior["last_success_at"]
    assert current["fingerprint"] == prior["fingerprint"]
    assert current["state"] == "failed"
    assert TestClient(app).get(f"/api/v1/updates/entries/{old_id}").json()["review_state"] == "reviewed"


@pytest.mark.asyncio
async def test_topic_checks_report_partial_failure_limits_and_no_case_egress(tmp_path, check_date):
    service = create_app(tmp_path).state.services.registry["updates"]
    class Topics:
        def list_topics(self):
            return [{"id": "ckd", "title": "chronic kidney disease"}, {"id": "dialysis", "title": "dialysis"}]
    service.services.registry["content"] = Topics()
    service.fetcher = SequenceFetcher([result(ARTICLE, hits=1000), RuntimeError("offline"), RuntimeError("offline")])
    with pytest.raises(Exception):
        await service.check_literature(["ckd", "SYNTHETIC_PATIENT_DETAILS"])
    assert not service.fetcher.urls
    checked = await service.check_literature(["ckd", "dialysis"])
    assert checked["state"] == "partial" and checked["discovered"] == 1
    assert checked["checks"][0]["truncated"] is True
    assert checked["checks"][0]["records_checked"] == 1
    assert checked["checks"][1]["state"] == "failed"
    assert [parse_qs(urlparse(url).query)["query"][0] for url in service.fetcher.urls] == [
        'TITLE_ABS:"chronic kidney disease" AND FIRST_PDATE:[2026-09-30 TO 2026-10-07] sort_date:y',
        'TITLE_ABS:"dialysis" AND FIRST_PDATE:[2026-09-30 TO 2026-10-07] sort_date:y',
    ]
    previous = next(row for row in service.literature.checks() if row["topic_id"] == "ckd")
    assert (await service.check_literature(["ckd"]))["state"] == "failed"
    current = next(row for row in service.literature.checks() if row["topic_id"] == "ckd")
    assert current["last_success_at"] == previous["last_success_at"]
    assert "SYNTHETIC_PATIENT_DETAILS" not in "".join(service.fetcher.urls)
    assert service.list_entries()[0]["source_metadata"]["reported_publication_status"] == "unknown"


@pytest.mark.asyncio
async def test_malformed_or_truncated_metadata_does_not_claim_no_results(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    topic = service.services.registry["content"].list_topics()[0]["id"]
    service.fetcher = SequenceFetcher([b'{"error":"synthetic malformed result"}', result(*[ARTICLE] * 26)])
    for expected in ("literature_metadata_invalid", "literature_metadata_invalid"):
        checked = await service.check_literature([topic])
        assert checked["state"] == "failed" and checked["checks"][0]["error_code"] == expected
    assert service.list_entries() == []


@pytest.mark.asyncio
async def test_old_001_metadata_can_fail_refresh_without_advancing_success(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    service.db.execute("INSERT INTO update_entries(id,source_id,external_id,title,url,kind,discovered_at,review_state,summary,source_metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("old", "L03", "epmc:MED:111111", "Synthetic old metadata", "https://europepmc.org/article/MED/111111",
         "research", "2010-01-01", "reviewed", "Synthetic dated review", json.dumps(ARTICLE)))
    service.fetcher = SequenceFetcher([RuntimeError("offline")])
    refreshed = await service.refresh_entry("old")
    assert refreshed["state"] == "failed" and refreshed["entry"]["review"] is None
    current = service.db.fetch_one("SELECT * FROM update_literature_records WHERE external_id='epmc:MED:111111'")
    assert current["state"] == "failed" and current["last_success_at"] is None
