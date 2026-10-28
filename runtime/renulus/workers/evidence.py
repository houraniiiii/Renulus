# SPDX-License-Identifier: MIT
"""BF03 selected evidence providers inside the protected broker.

Fixed official endpoints, one explicitly chosen provider per request, no fallback and no redirect
following. The host reserves usage before the call and settles it with the exact request count;
every hop is admitted through the capability transport's credit callback. Parsing, rights gating
and licensed-text extraction reuse `renulus.retrieval`; `RetrievalService.fetch_article` is run
unchanged over a brokered HTTP collaborator. Discovery records are never passage evidence.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode, urlsplit

from renulus.contracts import ApiError
from renulus.retrieval.connections import RetrievalConnections
from renulus.retrieval.evidence import dated_passages
from renulus.retrieval.http import public_link
from renulus.retrieval.literature import EUROPE, PUBMED, europe_records, pubmed_records
from renulus.retrieval.service import RetrievalService
from renulus.storage.database import utc_now

OFFICIAL = {
    "europe-pmc": ("www.ebi.ac.uk", EUROPE),
    "pubmed": ("eutils.ncbi.nlm.nih.gov", PUBMED),
    "brave": ("api.search.brave.com", "https://api.search.brave.com/res/v1/web/search"),
    "tavily": ("api.tavily.com", "https://api.tavily.com/search"),
    "exa": ("api.exa.ai", "https://api.exa.ai/search"),
}
KEYED = ("brave", "tavily", "exa")
SECRET_HEADERS = {"brave": lambda key: {"X-Subscription-Token": key},
                  "tavily": lambda key: {"Authorization": "Bearer " + key},
                  "exa": lambda key: {"x-api-key": key}}
SEARCH_BYTES, ARTICLE_BYTES = 2 * 1024 * 1024, 6 * 1024 * 1024
NCBI_INTERVAL_SECONDS = 0.35
PROVIDER_STATUS = {301: "retrieval_redirect_blocked", 302: "retrieval_redirect_blocked", 303: "retrieval_redirect_blocked",
                   307: "retrieval_redirect_blocked", 308: "retrieval_redirect_blocked",
                   401: "retrieval_authentication_required", 403: "retrieval_authentication_required",
                   404: "article_unavailable", 429: "retrieval_provider_limit"}


class Failure(Exception):
    """Closed public code. `answered` means the provider replied, so no effect is uncertain."""
    def __init__(self, code: str, answered: bool = False):
        self.code, self.answered = code, answered
        super().__init__(code)


def dump(value) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def _connections(profile_root, state_root) -> RetrievalConnections:
    return RetrievalConnections(SimpleNamespace(root=Path(profile_root), state=Path(state_root)))


def _revision(provider: str, record: dict) -> int:
    seed = f"Renulus.retrieval.revision:{provider}:{record.get('api_key', '')}:{bool(record.get('enabled'))}"
    return int.from_bytes(hashlib.sha256(seed.encode()).digest()[:6], "big")


def status(profile_root, state_root) -> dict:
    """Connection state of the doctor lanes. The key itself never leaves the DPAPI record."""
    connections = _connections(profile_root, state_root)
    rows = []
    for provider in OFFICIAL:
        record = connections.config(provider)
        keyed = provider in KEYED
        rows.append({"provider": provider, "key_required": keyed, "configured": bool(record.get("api_key")),
            "enabled": record["enabled"] if keyed else True,
            "selected": connections.settings["selected_provider"] == provider,
            "credential_ref": "retrieval:" + provider if keyed else None,
            "credential_revision": _revision(provider, record) if keyed else None,
            "daily_request_limit": record["daily_request_limit"], "daily_credit_limit": record["daily_credit_limit"]})
    return {"connections": rows}


def credential_headers(profile_root, state_root, provider: str, ref: str, revision: int, url: str, host: str) -> dict:
    """Secret headers for exactly the saved, enabled, selected key at its current revision."""
    if provider not in KEYED or ref != "retrieval:" + provider or urlsplit(url).hostname != host:
        raise Failure("credential_endpoint_denied")
    connections = _connections(profile_root, state_root)
    record = connections.config(provider)
    key = record.get("api_key")
    if (not key or not record["enabled"] or connections.settings["selected_provider"] != provider
            or _revision(provider, record) != revision):
        raise Failure("retrieval_connection_changed")
    return SECRET_HEADERS[provider](key)


def credential_callback(profile_root, state_root, plan):
    """The CapabilityTransport credential resolver for one evidence plan (broker passes it at construction)."""
    async def resolve(ref, revision, url):
        return credential_headers(profile_root, state_root, plan.provider, ref, revision, url, plan.endpoint.host)
    return resolve


def check_endpoint(provider: str, endpoint, base: str | None) -> str:
    """The provider's base URL. Official providers match the fixed table; anything else needs the host's private grant."""
    official_host, official_base = OFFICIAL[provider]
    url = urlsplit(base) if base else None
    if (endpoint is None or url is None or url.hostname != endpoint.host or url.username or url.password
            or url.query or url.fragment or url.scheme not in ("http", "https")
            or (url.port or (443 if url.scheme == "https" else 80)) != endpoint.port):
        raise Failure("evidence_endpoint_denied")
    official = endpoint.host == official_host and endpoint.port == 443 and base == official_base
    if not official and not endpoint.private_network:
        raise Failure("evidence_endpoint_denied")
    return base


class Hops:
    """Brokered stand-in for the two OfficialHTTP calls the retrieval code makes."""
    def __init__(self, transport, plan, attempt, base: str):
        self.transport, self.plan, self.attempt, self.base = transport, plan, attempt, base

    def _url(self, url: str, params) -> str:
        if url.startswith(EUROPE):
            url = self.base + url[len(EUROPE):]
        elif url.startswith(PUBMED):
            url = self.base + url[len(PUBMED):]
        return url + ("?" + urlencode(params) if params else "")

    async def request(self, method, url, *, params=None, body=None, headers=None, max_bytes=SEARCH_BYTES) -> bytes:
        if self.attempt.requests >= self.plan.max_requests:
            raise Failure("evidence_request_budget")
        payload = b"" if body is None else dump(body)
        # Mark before the await: a failure after this point may have left a remote effect.
        self.attempt.started = True
        self.attempt.requests += 1
        headers = {"accept": "*/*", **({"content-type": "application/json"} if body is not None else {})}
        credential = self.plan.credential
        stream = await self.transport.http(url=self._url(url, params), method=method, headers=headers,
            body=payload, body_sha256=hashlib.sha256(payload).hexdigest(),
            credential_ref=credential.ref if credential else None,
            credential_revision=credential.revision if credential else None)
        try:
            known = PROVIDER_STATUS.get(stream.status)
            if known or stream.status >= 400:
                raise Failure(known or "retrieval_failed", True)
            data = bytearray()
            while (chunk := await stream.read()) is not None:
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise Failure("retrieval_size_limit", True)
            return bytes(data)
        finally:
            await stream.close()

    async def json(self, method, url, **kwargs) -> dict:
        try:
            result = json.loads(await self.request(method, url, **kwargs))
        except ValueError:
            raise Failure("retrieval_invalid_response", True) from None
        if not isinstance(result, dict):
            raise Failure("retrieval_invalid_response", True)
        return result


class _Gateway:
    """The collaborators `RetrievalService.fetch_article` uses; usage was reserved by the host."""
    def __init__(self, http):
        self.http = http

    def _reserve(self, provider, requests, credits):
        pass


def _tool_records(provider: str, data: dict, limit: int) -> list[dict]:
    """Same record shape as retrieval.hermes.normalize, which needs the legacy Hermes plugin tree."""
    envelope = data.get("web") if provider == "brave" else data
    rows = envelope.get("results") if isinstance(envelope, dict) else None
    snippet = {"brave": "description", "tavily": "content"}.get(provider)
    if (not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get("title"), str)
            or not isinstance(row.get("url"), str) or snippet and not isinstance(row.get(snippet, ""), str) for row in rows)):
        raise Failure("retrieval_invalid_response", True)
    return [{"id": f"{provider}:{index}", "title": row["title"][:1000], "url": row["url"],
             "snippet": (row.get(snippet, "") if snippet else "")[:1500],
             "publication_date": row.get("publishedDate") or row.get("published_date") or row.get("page_age"),
             "snippet_source": "vendor_search_result", "record_type": "discovery", "passage_evidence": False,
             "latest_final_verified": False, "fulltext_licence": "unverified"}
            for index, row in enumerate(rows[:limit], 1) if len(row["url"]) <= 4096 and public_link(row["url"])]


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


async def search(plan, hops: Hops, base: str) -> dict:
    provider, limit = plan.provider, plan.limit
    query = " ".join(re.sub(r'["\x00-\x1f\x7f]', " ", plan.query).split())
    if not query:
        raise Failure("evidence_query_invalid")
    usage = {}
    if provider == "europe-pmc":
        data = await hops.json("GET", base + "/search", params={"query": query, "format": "json", "resultType": "core", "pageSize": limit})
        records = europe_records(data, limit)
    elif provider == "pubmed":
        params = {"db": "pubmed", "retmode": "json", "tool": "renulus"}
        found = await hops.json("GET", base + "/esearch.fcgi", params={**params, "term": query, "retmax": limit})
        envelope = found.get("esearchresult")
        if not isinstance(envelope, dict) or found.get("error") or envelope.get("errorlist"):
            raise Failure("retrieval_invalid_response", True)
        ids = envelope.get("idlist")
        if not isinstance(ids, list) or any(not isinstance(item, str) or not re.fullmatch(r"[1-9][0-9]{0,10}", item) for item in ids):
            raise Failure("retrieval_invalid_response", True)
        records = []
        if ids:
            await asyncio.sleep(NCBI_INTERVAL_SECONDS)
            summary = await hops.json("GET", base + "/esummary.fcgi", params={**params, "id": ",".join(ids[:limit])})
            records = pubmed_records(summary, ids[:limit])
    else:
        limit = min(limit, 5)
        if provider == "brave":
            data = await hops.json("GET", base, params={"q": query, "count": limit})
        elif provider == "tavily":
            data = await hops.json("POST", base, body={"query": query, "max_results": limit, "search_depth": "basic",
                "auto_parameters": False, "include_answer": False, "include_raw_content": False,
                "include_images": False, "include_usage": True})
            reported = _number((data.get("usage") or {}).get("credits")) if isinstance(data.get("usage"), dict) else None
            if reported is not None:
                usage["reported_credits"] = reported
        else:
            data = await hops.json("POST", base, body={"query": query, "numResults": limit, "type": "fast"})
            cost = data.get("costDollars")
            reported = _number(cost.get("total") if isinstance(cost, dict) else cost)
            if reported is not None:
                usage["reported_cost_dollars"] = reported
        records = _tool_records(provider, data, limit)
    return {"action": "search", "provider": provider, "query": query, "queried_at": utc_now(), "records": records,
            "verification": "discovery-only", "passage_evidence": False, "latest_final_verified": False,
            "provider_usage": usage, "billing_verified": False}


async def fetch(plan, hops: Hops) -> dict:
    fetched = await RetrievalService.fetch_article(_Gateway(hops), plan.pmcid)
    # Reviewed-source restrictions live in the canonical library, which this worker never opens;
    # the host applies them before any passage becomes evidence.
    unrestricted = lambda passages, **_: {"eligible_ids": [row["id"] for row in passages], "metadata": {}}
    passages = dated_passages(fetched, {"id": "evidence", "label": plan.pmcid}, unrestricted, None)
    article = fetched["article"]
    return {"action": "fetch", "provider": "europe-pmc", "pmcid": plan.pmcid, "fetched_at": utc_now(),
            "title": article["title"], "original_sha256": fetched["sha256"],
            "passages": [{key: row[key] for key in ("id", "title", "text", "canonical_url", "publication_date",
                "retrieved_at", "locators", "source_kind", "metadata", "rights")} | {"licence": row["rights"]["licence"],
                "permission_reference": row["rights"]["permission_reference"], "attribution": row["rights"]["attribution"]}
                for row in passages],
            "verification": "dated-research", "latest_final_verified": False, "source_restrictions_checked": False}


async def run(plan, transport, attempt, profile_root, state_root) -> bytes:
    """One evidence action as canonical JSON bytes. Errors are `Failure`s with closed codes."""
    if plan.action == "status":
        return dump(status(profile_root, state_root))
    provider = "europe-pmc" if plan.action == "fetch" else plan.provider
    if plan.action == "search" and (provider is None or plan.query is None) or plan.action == "fetch" and (
            plan.pmcid is None or plan.provider != "europe-pmc"):
        raise Failure("evidence_request_invalid")
    if (provider in KEYED) != (plan.credential is not None):
        raise Failure("evidence_credential_mismatch")
    base = check_endpoint(provider, plan.endpoint, plan.base_url)
    hops = Hops(transport, plan, attempt, base)
    try:
        return dump(await (search(plan, hops, base) if plan.action == "search" else fetch(plan, hops)))
    except ApiError as error:
        raise Failure(error.code, True) from None
