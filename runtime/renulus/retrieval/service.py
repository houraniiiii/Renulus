"""Topic labels alone cross the network; records are discovery, not evidence."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import time

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.storage.database import utc_now
from .connections import FREE, TOOLS, RetrievalConnections
from .hermes import normalize
from .http import OfficialHTTP
from .literature import EUROPE, PUBMED, PMCID, europe_records, europe_status, pubmed_records, licensed_article


class RetrievalService:
    def __init__(self, services, *, transport=None, protector=None, today=None):
        self.services = services
        self.db = services.db
        self.connections = RetrievalConnections(services.paths, protector=protector)
        self.http = OfficialHTTP(transport=transport)
        self._today = today or (lambda: datetime.now(timezone.utc).date().isoformat())
        self._settings_lock = asyncio.Lock()
        self._ncbi_lock = asyncio.Lock()
        self._import_lock = asyncio.Lock()
        self._last_ncbi = 0.0
        self._connection_versions = {provider: 0 for provider in TOOLS}
        self._selection_version = 0

    @staticmethod
    def _scope(scope, *, importing=False) -> ContextScope:
        try:
            scope = scope if isinstance(scope, ContextScope) else ContextScope.model_validate(scope)
        except Exception:
            raise ApiError("invalid_retrieval_scope", "Choose an explicit study or library scope.") from None
        allowed = (Scope.LIBRARY,) if importing else (Scope.STUDY, Scope.LIBRARY)
        if scope.kind not in allowed:
            raise ApiError("retrieval_scope_blocked", "Discover from a study topic. Case and unclassified contexts cannot use network discovery.", 403)
        # Discovery has no entity context. Import is a deliberate general library
        # action; never carry a submitted case/session identifier into a record.
        return ContextScope(kind=scope.kind)

    def topic(self, topic_id: str) -> dict:
        content = self.services.registry.get("content")
        if content is None:
            raise ApiError("retrieval_topics_unavailable", "Install a content pack to choose a discovery topic.", 503)
        for topic in content.list_topics():
            if topic["id"] == topic_id:
                label = topic.get("label")
                if not isinstance(label, str) or not 1 <= len(label) <= 180 or re.search(r'["\r\n\x00]', label):
                    raise ApiError("retrieval_topic_invalid", "The installed topic label is not suitable for public discovery.", 422)
                return {"id": topic["id"], "label": label}
        raise ApiError("retrieval_topic_unknown", "Choose an installed canonical topic.", 404)

    def status(self) -> dict:
        rows = []
        for provider in (*FREE, *TOOLS):
            record = self.connections.config(provider)
            usage = self.db.fetch_one("SELECT requests,credits FROM retrieval_usage WHERE provider=? AND day=?",
                                      (provider, self._today())) or {"requests": 0, "credits": 0}
            health = self.db.fetch_one("SELECT last_attempt_at,last_success_at,error_code FROM retrieval_health WHERE provider=?", (provider,)) or {}
            rows.append({"provider": provider, "key_required": provider in TOOLS,
                "configured": bool(record.get("api_key")), "enabled": record["enabled"] if provider in TOOLS else True,
                "selected": provider == self.connections.settings["selected_provider"],
                "daily_request_limit": record["daily_request_limit"], "daily_credit_limit": record["daily_credit_limit"],
                "requests_used": usage["requests"], "credits_used": usage["credits"],
                "credit_unit": "basic_search_credit" if provider == "tavily" else ("search_request_budget_unit" if provider in ("brave", "exa") else "not_billed_search"),
                "auth_status": health.get("error_code") or ("request_succeeded" if health.get("last_success_at") else "not_checked"),
                **health})
        return {"default_source": "europe-pmc", "selected_tool": self.connections.settings["selected_provider"],
                "connections": rows, "queries": "installed_topic_label_only", "case_egress": False,
                "vendor_generated_answers": False, "credit_caps_are_monetary_guarantee": False}

    async def configure(self, provider: str, **values) -> dict:
        async with self._settings_lock:
            previous = self.connections.settings["selected_provider"]
            self.connections.configure(provider, **values)
            self._connection_versions[provider] += 1
            if self.connections.settings["selected_provider"] != previous:
                self._selection_version += 1
            if values.get("api_key") is not None:
                self.db.execute("DELETE FROM retrieval_health WHERE provider=?", (provider,))
        return self.status()

    async def select(self, provider: str | None) -> dict:
        async with self._settings_lock:
            previous = self.connections.settings["selected_provider"]
            self.connections.select(provider)
            if provider != previous:
                self._selection_version += 1
        return self.status()

    async def disconnect(self, provider: str) -> dict:
        async with self._settings_lock:
            previous = self.connections.settings["selected_provider"]
            self.connections.disconnect(provider)
            if provider in TOOLS:
                self._connection_versions[provider] += 1
            if self.connections.settings["selected_provider"] != previous:
                self._selection_version += 1
            self.db.execute("DELETE FROM retrieval_health WHERE provider=?", (provider,))
        return self.status()

    def _reserve(self, provider: str, requests: int, credits: int) -> None:
        config = self.connections.config(provider)
        day = self._today()
        with self.db.transaction() as conn:
            usage = conn.execute("SELECT requests,credits FROM retrieval_usage WHERE provider=? AND day=?",
                                 (provider, day)).fetchone()
            used_requests, used_credits = (usage[0], usage[1]) if usage else (0, 0)
            if used_requests + requests > config["daily_request_limit"] or used_credits + credits > config["daily_credit_limit"]:
                raise ApiError("retrieval_daily_limit", "The selected source reached your daily request or credit cap. Change its limits deliberately or wait until tomorrow UTC.", 429)
            conn.execute("INSERT INTO retrieval_usage VALUES(?,?,?,?) ON CONFLICT(provider,day) DO UPDATE SET requests=requests+excluded.requests,credits=credits+excluded.credits",
                         (provider, day, requests, credits))
            conn.execute("INSERT INTO retrieval_health(provider,last_attempt_at) VALUES(?,?) ON CONFLICT(provider) DO UPDATE SET last_attempt_at=excluded.last_attempt_at", (provider, utc_now()))

    def _health(self, provider: str, error: ApiError | None = None) -> None:
        with self.db.transaction() as conn:
            if error:
                conn.execute("INSERT INTO retrieval_health(provider,error_code) VALUES(?,?) ON CONFLICT(provider) DO UPDATE SET error_code=excluded.error_code", (provider, error.code))
            else:
                conn.execute("UPDATE retrieval_health SET last_success_at=?,error_code=NULL WHERE provider=?", (utc_now(), provider))

    def _require_authorization(self, provider: str, authorization) -> None:
        if authorization is not None:
            current = (self._connection_versions[provider], self._selection_version)
            record = self.connections.config(provider)
            if current != authorization or self.connections.settings["selected_provider"] != provider or not record["enabled"] or not record.get("api_key"):
                raise ApiError("retrieval_connection_changed", "Retrieval settings changed during this request. Check your selection and repeat the search deliberately.", 409)

    async def _ncbi(self, provider: str, route: str, params: dict, authorization=None) -> dict:
        async with self._ncbi_lock:
            delay = max(0, 0.35 - (time.monotonic() - self._last_ncbi))
            if delay:
                await asyncio.sleep(delay)
            self._require_authorization(provider, authorization)
            self._last_ncbi = time.monotonic()
            self._reserve(provider, 1, 0)
            return await self.http.json("GET", PUBMED + "/" + route, params=params)

    async def discover(self, topic_id: str, *, scope: ContextScope, provider: str = "europe-pmc", limit: int = 5) -> dict:
        self._scope(scope)
        topic = self.topic(topic_id)
        if not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ApiError("retrieval_result_limit", "Choose between one and twenty discovery results.")
        async with self._settings_lock:
            if provider == "selected-tool":
                provider = self.connections.settings["selected_provider"]
            if provider not in (*FREE, *TOOLS):
                raise ApiError("retrieval_tool_required", "Choose a public source or explicitly select an optional tool.", 409)
            config = self.connections.config(provider)
            if provider in TOOLS and (not config["enabled"] or not config.get("api_key") or self.connections.settings["selected_provider"] != provider):
                raise ApiError("retrieval_tool_disabled", "The optional tool must be configured, enabled and selected before use.", 409)
            key = config.get("api_key") if provider in TOOLS else None
            authorization = (self._connection_versions[provider], self._selection_version) if provider in TOOLS else None
        provider_usage = {}
        try:
            if provider == "europe-pmc":
                self._reserve(provider, 1, 0)
                data = await self.http.json("GET", EUROPE + "/search", params={"query": 'TITLE_ABS:"' + topic["label"] + '"', "format": "json", "resultType": "core", "pageSize": limit})
                records = europe_records(data, limit)
            elif provider in ("pubmed", "ncbi"):
                params = {"db": "pubmed", "retmode": "json", "tool": "renulus", **({"api_key": key} if key else {})}
                found = await self._ncbi(provider, "esearch.fcgi", {**params, "term": '"' + topic["label"] + '"[Title/Abstract]', "retmax": limit}, authorization)
                self._require_authorization(provider, authorization)
                envelope = found.get("esearchresult")
                if not isinstance(envelope, dict) or found.get("error") or envelope.get("errorlist"):
                    raise ApiError("retrieval_invalid_response", "PubMed could not interpret the installed topic search.", 502)
                ids = envelope.get("idlist")
                if not isinstance(ids, list) or any(not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,10}", value) for value in ids):
                    raise ApiError("retrieval_invalid_response", "PubMed returned unsupported identifiers.", 502)
                records = pubmed_records(await self._ncbi(provider, "esummary.fcgi", {**params, "id": ",".join(ids[:limit])}, authorization), ids[:limit]) if ids else []
            else:
                self._reserve(provider, 1, 1)
                tool_limit = min(limit, 5)
                query = topic["label"] + " nephrology research"
                if provider == "brave":
                    data = await self.http.json("GET", "https://api.search.brave.com/res/v1/web/search",
                        params={"q": query, "count": tool_limit}, headers={"X-Subscription-Token": key, "Accept": "application/json"})
                elif provider == "tavily":
                    data = await self.http.json("POST", "https://api.tavily.com/search", headers={"Authorization": "Bearer " + key},
                        body={"query": query, "max_results": tool_limit, "search_depth": "basic", "auto_parameters": False,
                              "include_answer": False, "include_raw_content": False, "include_images": False, "include_usage": True})
                else:
                    data = await self.http.json("POST", "https://api.exa.ai/search", headers={"x-api-key": key},
                        body={"query": query, "numResults": tool_limit, "type": "fast"})
                records = normalize(self.services.paths, provider, data, tool_limit)
                if provider == "tavily":
                    value = data.get("usage", {}).get("credits") if isinstance(data.get("usage"), dict) else None
                    if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                        provider_usage["reported_credits"] = value
                elif provider == "exa":
                    value = data.get("costDollars")
                    if isinstance(value, dict):
                        value = value.get("total")
                    if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                        provider_usage["reported_cost_dollars"] = value
            self._require_authorization(provider, authorization)
            self._health(provider)
            return {"topic_id": topic["id"], "topic_label": topic["label"], "provider": provider,
                    "queried_at": utc_now(), "records": records, "passage_evidence": False,
                    "latest_final_verified": False, "query_basis": "installed_topic_label",
                    "provider_usage": provider_usage, "billing_verified": False}
        except ApiError as error:
            self._require_authorization(provider, authorization)
            self._health(provider, error)
            raise
        except (KeyError, TypeError, ValueError):
            self._require_authorization(provider, authorization)
            error = ApiError("retrieval_invalid_response", "The source returned unsupported discovery metadata.", 502)
            self._health(provider, error)
            raise error from None

    async def import_article(self, topic_id: str, pmcid: str, *, scope: ContextScope, idempotency_key: str) -> dict:
        scope = self._scope(scope, importing=True)
        topic = self.topic(topic_id)
        if not isinstance(pmcid, str) or not PMCID.fullmatch(pmcid):
            raise ApiError("invalid_article_id", "Choose a canonical PMC article identifier.")
        if not isinstance(idempotency_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", idempotency_key):
            raise ApiError("invalid_import_id", "Supply an opaque import identifier.")
        knowledge = self.services.registry.get("knowledge")
        if knowledge is None:
            raise ApiError("knowledge_unavailable", "The personal library is not available.", 503)
        # Single owned server serialises article intents. SQLite keeps bindings
        # across restart; knowledge owns the actual body and ingestion lifecycle.
        async with self._import_lock:
            return await self._import_article(topic, pmcid, scope, idempotency_key, knowledge)

    def _import_response(self, binding: dict, knowledge, *, replayed=False) -> dict:
        document = knowledge.get_document(binding["document_id"])
        job = knowledge.get_job(binding["job_id"])
        revision = next((item for item in document["revisions"] if item["id"] == binding["revision_id"]), None)
        if revision is None or revision["status"] == "deleted":
            raise ApiError("article_import_missing", "The previous library import is no longer available.", 409)
        metadata, rights = revision["metadata"], revision["rights"]
        article = {key: metadata.get(key) for key in ("pmcid", "pmid", "doi", "publication_date", "canonical_url")}
        article.update(title=document["title"], licence=rights["licence"], licence_url=rights["permission_reference"], attribution=rights["attribution"])
        return {"topic_id": binding["topic_id"], "article": article,
                "import": {"document_id": binding["document_id"], "revision_id": binding["revision_id"], "status": job["state"], "job": job},
                "replayed": replayed, "latest_final_verified": False, "content_reviewed": False}

    async def _import_article(self, topic, pmcid, scope, idempotency_key, knowledge):
        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
        with self.db.transaction() as conn:
            old = conn.execute("SELECT * FROM retrieval_imports WHERE key_hash=?", (key_hash,)).fetchone()
            if old is not None and (old["topic_id"] != topic["id"] or old["pmcid"] != pmcid):
                raise ApiError("idempotency_conflict", "That import key belongs to a different article or topic.", 409)
            if old is None:
                conn.execute("INSERT INTO retrieval_imports(key_hash,topic_id,pmcid,retrieved_at) VALUES(?,?,?,?)", (key_hash, topic["id"], pmcid, utc_now()))
        binding = self.db.fetch_one("SELECT * FROM retrieval_imports WHERE key_hash=?", (key_hash,))
        if binding["job_id"]:
            return self._import_response(binding, knowledge, replayed=True)
        try:
            self._reserve("europe-pmc", 1, 0)
            metadata = await self.http.json("GET", EUROPE + "/search", params={"query": "PMCID:" + pmcid,
                "format": "json", "resultType": "core", "pageSize": 5})
            europe_records(metadata, 5)  # Validate the primary envelope and rows.
            rows = metadata["resultList"]["result"]
            matches = [row for row in rows if row.get("pmcid") == pmcid]
            if len(matches) != 1 or len(rows) != 1:
                raise ApiError("article_identity_mismatch", "The selected article could not be uniquely resolved.", 409)
            match = matches[0]
            if match.get("isOpenAccess") != "Y" or not isinstance(match.get("license"), str) or not re.fullmatch(r"cc[ -]?by(?: [234]\.0)?|cc0(?: 1\.0)?", match["license"].strip().lower()):
                raise ApiError("article_permission_required", "This article is not available as eligible open-access full text.", 403)
            article_status = europe_status(match)
            if article_status["retracted"]:
                raise ApiError("article_retracted", "Retracted articles are excluded from new evidence imports.", 409)
            self._reserve("europe-pmc", 1, 0)
            raw = await self.http.request("GET", EUROPE + "/" + pmcid + "/fullTextXML", max_bytes=6 * 1024 * 1024)
            digest = hashlib.sha256(raw).hexdigest()
            if binding["xml_sha256"] and binding["xml_sha256"] != digest:
                raise ApiError("article_revision_changed", "The source article changed during this import. Review it and start a new import.", 409)
            article = licensed_article(raw, pmcid)
            for identifier in ("pmid", "doi"):
                expected, observed = match.get(identifier), article.get(identifier)
                equal = isinstance(expected, str) and isinstance(observed, str) and (expected.casefold() == observed.casefold() if identifier == "doi" else expected == observed)
                if expected and not equal:
                    raise ApiError("article_identity_mismatch", "Full text and metadata have different article identifiers.", 409)
            self.db.execute("UPDATE retrieval_imports SET xml_sha256=? WHERE key_hash=?", (digest, key_hash))
            from renulus.knowledge.models import Rights, SourceMetadata
            corrections = article_status["comment_corrections"]
            source = SourceMetadata(source_id="L03", source_owner=article["publisher"],
                canonical_url="https://europepmc.org/articles/" + pmcid, access_class="open-licensed",
                publication_date=article["publication_date"], retrieved_at=binding["retrieved_at"],
                publication_status="unknown", latest_final_verified=False, content_reviewed=False,
                correction=("Europe PMC relationships: " + json.dumps(corrections, sort_keys=True)) if corrections else None,
                topic_ids=[topic["id"]], doi=article["doi"], pmid=article["pmid"], pmcid=pmcid,
                notes=["Europe PMC fullTextXML SHA256:" + digest,
                       "Licence statement: " + article["licence_statement"],
                       "Article authors: " + "; ".join(article["authors"]),
                       "Europe PMC record identity: " + match["source"] + ":" + match["id"],
                       "Europe PMC publication types: " + json.dumps(article_status["article_types"]),
                       "Europe PMC first publication date: " + str(match.get("firstPublicationDate") or match.get("pubYear") or "unknown"),
                       "Retraction completeness is not settled by discovery metadata.",
                       "Licensed text extraction; figures, tables, media, quoted blocks and supplements omitted; not latest-final verified."])
            credits = [article["title"], "; ".join(article["authors"]), article["copyright_statement"],
                       " ".join(filter(None, (article["copyright_year"], article["copyright_holder"]))),
                       source.canonical_url, article["licence"] + " " + article["licence_url"],
                       "Text extracted and formatting changed; figures, tables, media, quoted blocks and supplements omitted."]
            rights = Rights(display=True, cache=True, index=True, embedding=True, model_input=True,
                derivation=True, evaluation=False, redistribution=False, licence=article["licence"],
                permission_reference=article["licence_url"], attribution=". ".join(value for value in credits if value))
            # Known library API owns originals/queue/chunking. No private payload
            # enters this route; no second parser/index/model engine is introduced.
            result = await asyncio.to_thread(knowledge.import_text, article["text"], title=article["title"],
                metadata=source, rights=rights, scope=scope, idempotency_key="retrieval_" + key_hash, process=False)
            self.db.execute("UPDATE retrieval_imports SET document_id=?,revision_id=?,job_id=? WHERE key_hash=?",
                            (result["document_id"], result["revision_id"], result["job"]["id"], key_hash))
            self._health("europe-pmc")
            return self._import_response(self.db.fetch_one("SELECT * FROM retrieval_imports WHERE key_hash=?", (key_hash,)), knowledge)
        except ApiError as error:
            self._health("europe-pmc", error)
            raise
        except (KeyError, TypeError, ValueError):
            error = ApiError("retrieval_invalid_response", "The source returned unsupported article metadata.", 502)
            self._health("europe-pmc", error)
            raise error from None
        except (OSError, RuntimeError):
            error = ApiError("article_import_failed", "The library could not acknowledge this import. Retry the same import request.", 503, True)
            self._health("europe-pmc", error)
            raise error from None
