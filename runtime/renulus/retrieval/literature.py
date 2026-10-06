"""Primary metadata schemas and conservative licensed JATS text acquisition."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from defusedxml.ElementTree import fromstring

from renulus.contracts import ApiError

EUROPE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
PUBMED = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PMCID = re.compile(r"PMC[1-9][0-9]{0,10}")


def text(node) -> str:
    return " ".join(" ".join(node.itertext()).split()) if node is not None else ""


def europe_records(data: dict, limit: int) -> list[dict]:
    envelope = data.get("resultList")
    rows = envelope.get("result") if isinstance(envelope, dict) else None
    if not isinstance(rows, list):
        raise ApiError("retrieval_invalid_response", "Europe PMC returned unsupported metadata.", 502)
    records = []
    for row in rows[:limit]:
        if not isinstance(row, dict) or not isinstance(row.get("title"), str) or not row["title"].strip():
            raise ApiError("retrieval_invalid_response", "Europe PMC returned incomplete metadata.", 502)
        source, identifier = row.get("source", ""), row.get("id", "")
        if not isinstance(source, str) or not re.fullmatch(r"[A-Z]{2,8}", source) or not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", identifier):
            raise ApiError("retrieval_invalid_response", "Europe PMC returned unsupported identifiers.", 502)
        pmcid = row.get("pmcid")
        if pmcid is not None and (not isinstance(pmcid, str) or not PMCID.fullmatch(pmcid)):
            raise ApiError("retrieval_invalid_response", "Europe PMC returned unsupported identifiers.", 502)
        if source == "MED" and identifier.isdigit():
            url = "https://pubmed.ncbi.nlm.nih.gov/" + identifier + "/"
        elif pmcid:
            url = "https://europepmc.org/articles/" + pmcid
        else:
            url = "https://europepmc.org/article/" + source + "/" + identifier
        status = europe_status(row)
        records.append({"id": source + ":" + identifier, "title": row["title"],
            "url": url, "authors": row.get("authorString"), "doi": row.get("doi"),
            "pmid": identifier if source == "MED" else None, "pmcid": pmcid,
            "publication_date": row.get("firstPublicationDate") or row.get("pubYear"),
            "open_access": row.get("isOpenAccess") == "Y",
            **status,
            "fulltext_licence": "unverified", "record_type": "discovery",
            "latest_final_verified": False, "passage_evidence": False})
    return records


def europe_status(row: dict) -> dict:
    types = row.get("pubTypeList", {})
    types = types.get("pubType", []) if isinstance(types, dict) else None
    relationships = row.get("commentCorrectionList", {})
    relationships = relationships.get("commentCorrection", []) if isinstance(relationships, dict) else None
    if not isinstance(types, list) or any(not isinstance(value, str) for value in types) or not isinstance(relationships, list) or any(not isinstance(value, dict) for value in relationships):
        raise ApiError("retrieval_invalid_response", "Europe PMC returned unsupported article status.", 502)
    corrections = [{key: item[key] for key in ("source", "id", "type") if isinstance(item.get(key), str)} for item in relationships]
    reported = row.get("isRetracted") == "Y" or any("retract" in value.lower() for value in types) or any("retract" in item.get("type", "").lower() for item in corrections)
    return {"article_types": types, "comment_corrections": corrections,
            "retracted": True if reported else None,
            "retraction_check_status": "reported" if reported else "not_settled"}


def pubmed_records(data: dict, identifiers: list[str]) -> list[dict]:
    result = data.get("result")
    if not isinstance(result, dict):
        raise ApiError("retrieval_invalid_response", "PubMed returned unsupported metadata.", 502)
    rows = []
    for identifier in identifiers:
        record = result.get(identifier)
        if not isinstance(record, dict) or not isinstance(record.get("title"), str) or not record["title"].strip():
            raise ApiError("retrieval_invalid_response", "PubMed returned incomplete metadata.", 502)
        if not isinstance(record.get("articleids", []), list) or not isinstance(record.get("authors", []), list) or not isinstance(record.get("pubtype", []), list):
            raise ApiError("retrieval_invalid_response", "PubMed returned unsupported metadata.", 502)
        ids = {item.get("idtype"): item.get("value") for item in record.get("articleids", []) if isinstance(item, dict)}
        types = record.get("pubtype", [])
        if any(not isinstance(value, str) for value in types):
            raise ApiError("retrieval_invalid_response", "PubMed returned unsupported article status.", 502)
        reported = any("retract" in value.lower() for value in types)
        rows.append({"id": "MED:" + identifier, "title": record.get("title", ""),
            "url": "https://pubmed.ncbi.nlm.nih.gov/" + identifier + "/",
            "authors": ", ".join(item.get("name", "") for item in record.get("authors", []) if isinstance(item, dict)),
            "pmid": identifier, "pmcid": ids.get("pmc"), "doi": ids.get("doi"),
            "publication_date": record.get("pubdate"), "article_types": types,
            "open_access": None, "retracted": True if reported else None,
            "retraction_check_status": "reported" if reported else "not_settled",
            "fulltext_licence": "unverified", "record_type": "discovery",
            "latest_final_verified": False, "passage_evidence": False})
    return rows


def licensed_article(raw: bytes, expected_pmcid: str) -> dict:
    try:
        root = fromstring(raw, forbid_entities=True, forbid_external=True)
    except Exception:
        raise ApiError("article_xml_invalid", "The article XML could not be safely parsed.", 422) from None
    for node in root.iter():
        if "}" in node.tag:
            node.tag = node.tag.split("}", 1)[1]
    front = root.find("front/article-meta")
    if root.tag != "article" or front is None:
        raise ApiError("article_xml_invalid", "A complete JATS article is required.", 422)
    ids = {node.get("pub-id-type"): text(node) for node in front.findall("article-id")}
    pmcid = ids.get("pmcid") or ("PMC" + ids["pmc"] if ids.get("pmc", "").isdigit() else ids.get("pmc"))
    if pmcid != expected_pmcid:
        raise ApiError("article_identity_mismatch", "The full text does not match the selected article.", 409)
    categories = text(front.find("article-categories")).lower()
    if root.get("article-type") in ("retraction", "retracted-article") or "retracted publication" in categories:
        raise ApiError("article_retracted", "Retracted articles are excluded from new evidence imports.", 409)
    licences = front.findall("permissions/license")
    accepted = set()
    for licence in licences:
        statement = text(licence).lower()
        if re.search(r"except|exclud|third.party|unless otherwise|not covered|separate permission", statement):
            raise ApiError("article_permission_required", "This article has exclusions requiring a reviewed manual import.", 403)
        for link in licence.iter():
            href = link.get("{http://www.w3.org/1999/xlink}href") or link.get("href")
            if not href:
                continue
            try:
                parsed = urlsplit(href)
                valid = parsed.scheme in ("https", "http") and parsed.hostname == "creativecommons.org" and not (parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment)
                path = parsed.path.rstrip("/")
            except ValueError:
                valid, path = False, ""
            if not valid or path not in ("/licenses/by/2.0", "/licenses/by/3.0", "/licenses/by/4.0", "/publicdomain/zero/1.0"):
                raise ApiError("article_permission_required", "The article licence is outside the automatic import policy.", 403)
            accepted.add(("CC0-1.0" if "zero" in path else "CC-BY-" + path.rsplit("/", 1)[1], "https://creativecommons.org" + path + "/"))
    if len(licences) != 1 or len(accepted) != 1:
        raise ApiError("article_permission_required", "Automatic import requires an explicit article CC BY or CC0 licence. Use a permitted manual import otherwise.", 403)
    title = text(front.find("title-group/article-title"))
    if not title:
        raise ApiError("article_xml_invalid", "An article title is required for attribution.", 422)
    authors = []
    for author in front.findall("contrib-group/contrib"):
        if author.get("contrib-type", "author") != "author":
            continue
        name = author.find("name")
        value = " ".join(filter(None, (text(name.find("given-names")), text(name.find("surname"))))) if name is not None else text(author.find("string-name")) or text(author.find("collab"))
        if value:
            authors.append(value)
    copyright_statement = text(front.find("permissions/copyright-statement"))
    copyright_holder = text(front.find("permissions/copyright-holder"))
    copyright_year = text(front.find("permissions/copyright-year"))
    if not authors and not copyright_holder and not copyright_statement:
        raise ApiError("article_attribution_required", "Article authors or copyright credit are required for automatic import.", 403)
    blocks = [title]
    skipped = {"fig", "table-wrap", "supplementary-material", "graphic", "media", "permissions", "disp-quote", "boxed-text"}
    def collect(node):
        if node.tag in skipped or "third-party" in node.get("specific-use", "").lower():
            return
        if node.tag in ("p", "title"):
            if not any(item.tag in skipped or "third-party" in item.get("specific-use", "").lower() for item in node.iter()):
                value = text(node)
                if value:
                    blocks.append(value)
            return
        for child in node:
            collect(child)
    for section in (front.find("abstract"), root.find("body")):
        if section is not None:
            collect(section)
    # Preserve body paragraph provenance for automatic evidence. Abstract and
    # heading metadata alone are never promoted to full-text passage evidence.
    passages = []
    def body_passages(node, path, section="Body"):
        if node.tag in skipped or "third-party" in node.get("specific-use", "").lower():
            return
        if node.tag == "sec":
            section = text(node.find("title")) or section
        if node.tag == "p":
            if not any(item.tag in skipped or "third-party" in item.get("specific-use", "").lower() for item in node.iter()):
                value = text(node)
                if value:
                    passages.append({"text": value, "locator": {"kind": "jats", "item_id": path,
                        "section": section, "char_start": 0, "char_end": len(value)}})
            return
        counts = {}
        for child in node:
            counts[child.tag] = counts.get(child.tag, 0) + 1
            body_passages(child, path + "/" + child.tag + "[" + str(counts[child.tag]) + "]", section)
    body = root.find("body")
    if body is not None:
        body_passages(body, "/article/body")
    content = "\n\n".join(blocks)
    if len(content) > 1_000_000 or len(blocks) < 2:
        raise ApiError("article_text_unavailable", "A bounded, eligible article body could not be extracted.", 422)
    publication_date = None
    for date in front.findall("pub-date"):
        year, month, day = (text(date.find(name)) for name in ("year", "month", "day"))
        if year.isdigit() and len(year) == 4:
            publication_date = year + ("-" + month.zfill(2) if month.isdigit() and 1 <= int(month) <= 12 else "")
            if len(publication_date) == 7 and day.isdigit() and 1 <= int(day) <= 31:
                publication_date += "-" + day.zfill(2)
            break
    licence, licence_url = next(iter(accepted))
    return {"title": title or expected_pmcid, "text": content, "passages": passages, "pmcid": pmcid,
            "article_type": root.get("article-type", ""),
            "pmid": ids.get("pmid"), "doi": ids.get("doi"), "licence": licence,
            "licence_url": licence_url, "licence_statement": text(licences[0]),
            "authors": authors, "copyright_statement": copyright_statement,
            "copyright_holder": copyright_holder, "copyright_year": copyright_year,
            "publication_date": publication_date,
            "publisher": text(root.find("front/journal-meta/publisher/publisher-name")) or "Article authors/publisher"}
