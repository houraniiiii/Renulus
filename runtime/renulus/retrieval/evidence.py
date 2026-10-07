"""Run-scoped, key-free, licensed research evidence; no Library import."""
import asyncio
from datetime import date, datetime, timezone
import hashlib
import re

from renulus.contracts import ApiError, Scope
from renulus.knowledge.models import Rights, SourceMetadata
from renulus.storage import utc_now
from .literature import metadata_licence_permitted


MAX_CANDIDATES = 5
# Only article-local ineligibility permits checking the next distinct candidate.
# Network/budget failures, malformed responses/XML and identity mismatches stop.
CANDIDATE_INELIGIBLE = frozenset({
    "article_permission_required", "article_attribution_required", "article_retracted",
    "article_review_required", "article_date_required", "article_text_unavailable",
    "source_evidence_excluded", "article_unavailable",
})


def selection_disclosure(acquisition):
    checks = acquisition["checks"]
    summary = (f"Europe PMC evidence selection checked {len(checks)} of "
               f"{acquisition['records_received']} returned candidates (limit {MAX_CANDIDATES}).")
    for row in checks:
        identity = row["pmcid"] or row["record_id"]
        if row["outcome"] != "selected":
            summary += f" Candidate {row['rank']} ({identity}) {row['outcome']}: {row['code']}. {row['message']}"
    if acquisition.get("selected_pmcid"):
        summary += f" Selected {acquisition['selected_pmcid']}; later candidates were not checked."
    else:
        summary += " No public body passage acquired."
    return summary


def publication_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}(?:-\d{2})?(?:-\d{2})?", value):
        raise ApiError("article_date_required", "The full text has no usable publication date.", 422)
    parts = value.split("-")
    try:
        observed = date(int(parts[0]), int(parts[1]) if len(parts) > 1 else 1,
                        int(parts[2]) if len(parts) > 2 else 1)
        if observed > datetime.now(timezone.utc).date():
            raise ValueError()
    except ValueError:
        raise ApiError("article_date_required", "The full-text publication date is invalid or in the future.", 422) from None
    return value


async def acquire_evidence(service, topic_id, *, scope):
    scope = service._scope(scope)
    if scope.kind != Scope.STUDY:
        raise ApiError("retrieval_scope_blocked", "Automatic evidence is available only in ordinary study.", 403)
    topic = service.topic(topic_id)
    knowledge = service.services.registry.get("knowledge")
    check = getattr(knowledge, "check_evidence", None)
    if not callable(check):
        raise ApiError("source_status_unavailable", "Current source restrictions could not be checked.", 503, True)
    discovered = await service.discover(topic_id, scope=scope, provider="europe-pmc", limit=MAX_CANDIDATES,
                                        _evidence_candidates=True)
    candidates = discovered["records"][:MAX_CANDIDATES]
    acquisition = {"provider": "europe-pmc", "max_candidates": MAX_CANDIDATES,
                   "records_received": len(candidates), "checks": [], "selected_pmcid": None}
    seen = set()
    last_error = None
    for rank, selected in enumerate(candidates, 1):
        # Deliver cancellation before starting another candidate, even when a
        # supplied transport completes without yielding to the event loop.
        await asyncio.sleep(0)
        pmcid = selected.get("pmcid")
        attempt = {"rank": rank, "record_id": selected["id"], "pmcid": pmcid,
                   "stage": "discovery-metadata"}
        acquisition["checks"].append(attempt)
        if not pmcid or not selected.get("open_access"):
            error = ApiError("no_eligible_public_evidence", "No public full-text candidate is available.", 404)
        elif pmcid in seen:
            error = ApiError("duplicate_candidate", "This article was already considered; it was not requested again.", 409)
        elif selected.get("retracted"):
            error = ApiError("article_retracted", "Metadata reports a retraction; this candidate was skipped.", 409)
        elif not metadata_licence_permitted(selected.get("metadata_licence")):
            error = ApiError("article_permission_required", "Metadata does not supply an eligible CC BY or CC0 licence.", 403)
        else:
            seen.add(pmcid)
            attempt["stage"] = "article-gateway"
            try:
                fetched = await service.fetch_article(pmcid)
                passages = dated_passages(fetched, topic, check, scope)
            except ApiError as error:
                attempt.update(outcome="skipped" if error.code in CANDIDATE_INELIGIBLE else "failed",
                               code=error.code, message=error.message)
                if error.code not in CANDIDATE_INELIGIBLE:
                    raise_selection_failure(service, error, acquisition)
                last_error = error
                continue
            attempt["outcome"] = "selected"
            acquisition["selected_pmcid"] = pmcid
            acquisition["disclosure"] = selection_disclosure(acquisition)
            # Existing citation details and model source context both expose
            # attribution. Keep skipped acquisitions visible without a UI seam.
            for passage in passages:
                passage["metadata"]["notes"].append(acquisition["disclosure"])
                passage["rights"]["attribution"] += " " + acquisition["disclosure"]
            service._health("europe-pmc")
            return {"passages": passages, "discovery": discovered, "acquisition": acquisition,
                    "verification": "dated-research", "latest_final_verified": False}
        if pmcid:
            seen.add(pmcid)
        attempt.update(outcome="skipped", code=error.code, message=error.message)
        if error.code != "duplicate_candidate":
            last_error = error
    # Preserve the specific last rejection for existing Learn failure messages.
    error = last_error or ApiError("no_eligible_public_evidence", "No eligible public full text was discovered for this topic.", 404)
    raise_selection_failure(service, error, acquisition)


def raise_selection_failure(service, error, acquisition):
    acquisition["disclosure"] = selection_disclosure(acquisition)
    failure = ApiError(error.code, error.message + " " + acquisition["disclosure"], error.status, error.retryable)
    failure.acquisition = acquisition
    service._health("europe-pmc", failure)
    raise failure from None


def dated_passages(fetched, topic, check, scope):
    article, status = fetched["article"], fetched["status"]
    if status["comment_corrections"] or any(any(term in value.lower() for term in
            ("preprint", "draft", "correction", "erratum", "expression of concern", "expression-of-concern"))
            for value in [*status["article_types"], article["article_type"]]):
        raise ApiError("article_review_required", "This article has a notice or preliminary status requiring review.", 409)
    published = publication_date(article["publication_date"])
    url = "https://europepmc.org/articles/" + article["pmcid"]
    metadata = SourceMetadata(source_id="L03", source_owner=article["publisher"], canonical_url=url,
        access_class="open-licensed", original_sha256=fetched["sha256"], publication_date=published,
        retrieved_at=utc_now(), checked_at=utc_now(), topic_ids=[topic["id"]],
        doi=article["doi"], pmid=article["pmid"], pmcid=article["pmcid"],
        notes=["Dated licensed research, not latest-final verified guidance.",
               "Retraction absence is not certified by metadata."])
    attribution = ". ".join(filter(None, (article["title"], "; ".join(article["authors"]),
        article["copyright_statement"], article["copyright_holder"], url,
        article["licence"] + " " + article["licence_url"],
        "Text extracted; figures, tables, media, quotations and supplements omitted.")))
    # Only display, citation retention, model context and explanation
    # derivation are used. No original caching, index or embedding operation.
    rights = Rights(display=True, cache=True, model_input=True, derivation=True,
        licence=article["licence"], permission_reference=article["licence_url"], attribution=attribution)
    passages = []
    for block in article["passages"][:3]:
        excerpt = block["text"][:3000]
        locator = {**block["locator"], "char_end": len(excerpt)}
        identifier = "public_" + hashlib.sha256((fetched["sha256"] + locator["item_id"]).encode()).hexdigest()[:32]
        passages.append({"id": identifier, "source_kind": "public-article", "source_id": "L03",
            "title": article["title"], "text": excerpt, "canonical_url": url,
            "publication_date": published, "retrieved_at": metadata.retrieved_at,
            "locators": [locator], "metadata": metadata.model_dump(), "rights": rights.model_dump(),
            "verification": "dated-research", "latest_final_verified": False})
    if not passages:
        raise ApiError("article_text_unavailable", "The article supplied no eligible body passage.", 422)
    allowed = check(passages, scope=scope, topic_id=topic["id"], current_only=False)
    passages = [{**row, "metadata": allowed["metadata"].get(row["id"], row["metadata"])}
                for row in passages if row["id"] in allowed["eligible_ids"]]
    if not passages:
        raise ApiError("source_evidence_excluded", "Reviewed source restrictions exclude this article.", 409)
    return passages
