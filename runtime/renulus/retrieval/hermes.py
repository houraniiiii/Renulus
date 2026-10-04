"""Pure result shaping from pinned Hermes; no native dispatcher/env/key lookup."""
from renulus.runtime.hermes import HermesSubscriptionTransport
from renulus.contracts import ApiError
from .http import public_link


def normalize(paths, provider: str, data: dict, limit: int) -> list[dict]:
    envelope = data.get("web") if provider == "brave" else data
    original = envelope.get("results") if isinstance(envelope, dict) else None
    if not isinstance(original, list) or any(not isinstance(row, dict) or not isinstance(row.get("title"), str) or not isinstance(row.get("url"), str) for row in original):
        raise ApiError("retrieval_invalid_response", "The selected tool returned unsupported discovery results.", 502)
    if provider in ("brave", "tavily") and any(not isinstance(row.get("description" if provider == "brave" else "content", ""), str) for row in original):
        raise ApiError("retrieval_invalid_response", "The selected tool returned unsupported discovery snippets.", 502)
    with HermesSubscriptionTransport(paths.source_root, paths.root).controlled():
        from plugins.web._common import titled_rows, web_hit
        if provider == "brave":
            rows = titled_rows((data.get("web") or {}).get("results", [])[:limit], "description")
        elif provider == "tavily":
            from plugins.web.tavily.provider import _normalize_tavily_search_results
            rows = _normalize_tavily_search_results(data)["data"]["web"][:limit]
        else:
            rows = [web_hit(row.get("url", ""), row.get("title", ""), "", index + 1)
                    for index, row in enumerate(data.get("results", [])[:limit])]
    return [{"id": provider + ":" + str(row["position"]), "title": row["title"][:1000],
             "url": row["url"], "snippet": row.get("description", "")[:1500],
             "publication_date": original[row["position"] - 1].get("publishedDate") or original[row["position"] - 1].get("published_date"),
             "snippet_source": "vendor_search_result",
             "record_type": "discovery", "passage_evidence": False,
             "latest_final_verified": False, "fulltext_licence": "unverified"}
            for row in rows if len(row.get("url", "")) <= 4096 and public_link(row.get("url", ""))]
