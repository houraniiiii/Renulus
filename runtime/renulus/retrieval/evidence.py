"""Run-scoped, key-free, licensed research evidence; no Library import."""
from datetime import date, datetime, timezone
import hashlib
import re

from renulus.contracts import ApiError, Scope
from renulus.knowledge.models import Rights, SourceMetadata
from renulus.storage import utc_now


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
    discovered = await service.discover(topic_id, scope=scope, provider="europe-pmc", limit=5)
    # Select at most one candidate. No provider rotation or hidden retry loop.
    candidates = [row for row in discovered["records"] if row.get("pmcid")
                  and row.get("open_access") and not row.get("retracted")]
    if not candidates:
        error = ApiError("no_eligible_public_evidence", "No eligible public full text was discovered for this topic.", 404)
        service._health("europe-pmc", error)
        raise error
    selected = candidates[0]
    try:
        fetched = await service.fetch_article(selected["pmcid"])
        article, record, status = (fetched[key] for key in ("article", "record", "status"))
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
        service._health("europe-pmc")
        return {"passages": passages, "discovery": discovered, "verification": "dated-research",
                "latest_final_verified": False}
    except ApiError as error:
        service._health("europe-pmc", error)
        raise
