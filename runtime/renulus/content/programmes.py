# SPDX-License-Identifier: MIT
"""Dated curriculum alignment; active bank coverage is derived from exact pins.

No learner records or model output enter this module. A mapping is an authored
interpretation, not an official endorsement, assessment blueprint or mastery.
"""

from collections import Counter


def _unique(rows, kind):
    result = {row["id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate {kind} identity")
    return result


def validate_programme_mappings(bundle, known_register_ids=None):
    manifest = bundle["manifest"]
    programmes = _unique(manifest.get("programme_mappings", []), "programme")
    objectives = {o["id"] for t in bundle["topics"] for o in t["objectives"]}
    items = {kind: {i["id"]: i for i in bundle[kind]} for kind in ("questions", "cases")}
    aligned = set()
    for programme in programmes.values():
        if programme["checked_on"] > manifest["published_on"]:
            raise ValueError("Mapping check is after publication")
        evidence = _unique(programme["evidence"], "programme evidence")
        if {s["kind"] for s in evidence.values()} != {"exam_format", "blueprint", "curriculum"}:
            raise ValueError("Exam format, blueprint and curriculum evidence are required")
        for source in evidence.values():
            if known_register_ids is not None and source["register_id"] not in known_register_ids:
                raise ValueError("Unknown SOURCES register ID for programme evidence")
            if source["checked_on"] != programme["checked_on"]:
                raise ValueError("Mapping evidence check dates must agree")
            if source["kind"] != "exam_format" and not (source.get("sha256") and source.get("page_count")):
                raise ValueError("PDF mapping evidence must pin hash and page count")
        exam = programme["exam"]
        if evidence.get(exam["source_id"], {}).get("kind") != "exam_format":
            raise ValueError("Exam format must refer to its evidence")
        if exam["papers"] * exam["questions_per_paper"] != exam["total_questions"]:
            raise ValueError("Exam paper totals disagree")
        domains = _unique(programme["domains"], "blueprint domain")
        if sum(d["indicative_questions"] for d in domains.values()) != exam["total_questions"]:
            raise ValueError("Indicative blueprint counts do not total the exam")
        for domain in domains.values():
            source = evidence.get(domain["source_id"], {})
            if source.get("kind") != "blueprint" or domain["source_page"] > source.get("page_count", 0):
                raise ValueError("Domain must cite a blueprint page")
        rows = _unique(programme["alignments"], "alignment")
        represented_domains = set()
        question_domains = {}
        for row in rows.values():
            domain = row["domain_id"]
            if row["relation"] == "exam_domain":
                if domain not in domains or row["status"] == "supporting":
                    raise ValueError("Exam alignment must name a known domain")
                represented_domains.add(domain)
            elif domain is not None or row["status"] != "supporting":
                raise ValueError("Curriculum support cannot count as exam-domain coverage")
            reference = row["curriculum_reference"]
            source = evidence.get(reference["source_id"], {})
            if source.get("kind") != "curriculum" or any(p > source.get("page_count", 0) for p in reference["pages"]):
                raise ValueError("Alignment must cite a curriculum page")
            if not set(row["objective_ids"]).issubset(objectives):
                raise ValueError("Unknown aligned objective")
            supported = set()
            for kind in ("questions", "cases"):
                _unique(row[kind], f"{kind} pin")
                for pin in row[kind]:
                    item = items[kind].get(pin["id"])
                    if item is None or item["version"] != pin["version"]:
                        raise ValueError(f"Unknown selected {kind} version: {pin['id']}")
                    if not set(item["objective_ids"]).intersection(row["objective_ids"]):
                        raise ValueError(f"Mapping pin lacks a related objective: {pin['id']}")
                    supported.update(item["objective_ids"])
                    if kind == "questions":
                        if item["usage"] != "assessment_reserved":
                            raise ValueError("Only the reviewed bank may support mapped assessment")
                        if domain is not None:
                            if question_domains.get(pin["id"], domain) != domain:
                                raise ValueError("A question cannot inflate two blueprint domains")
                            question_domains[pin["id"]] = domain
            if row["status"] == "gap":
                if row["objective_ids"] or row["questions"] or row["cases"]:
                    raise ValueError("A gap cannot claim content coverage")
            elif not row["objective_ids"] or not set(row["objective_ids"]).issubset(supported):
                raise ValueError("Alignment is not supported by explicit item/objective pins")
            aligned.update(row["objective_ids"])
        if represented_domains != set(domains):
            raise ValueError("Every blueprint domain must expose coverage or a gap")
        for pin in _unique(programme.get("excluded_questions", []), "excluded question").values():
            question = items["questions"].get(pin["id"], {})
            if question.get("version") != pin["version"] or pin["id"] in question_domains:
                raise ValueError("Excluded question must be an unselected exact bank version")
    for topic in bundle["topics"]:
        mapping = topic["mapping"]
        linked = any(o["id"] in aligned for o in topic["objectives"])
        if mapping["esen_eph"] == "partially_mapped":
            programme = programmes.get("esen_eph", {})
            if not linked or mapping.get("mapping_version") != programme.get("version"):
                raise ValueError("Partial topic mapping needs dated programme evidence and item pins")
        elif linked or "mapping_version" in mapping:
            raise ValueError("Unmapped topic contradicts programme alignment")


def mapped_question_pins(manifest, track):
    programme = next((p for p in (manifest or {}).get("programme_mappings", []) if p["id"] == track), None)
    return {(q["id"], q["version"]) for row in programme["alignments"]
            if row["relation"] == "exam_domain" for q in row["questions"]} if programme else set()


def _active_alignment(row, selected, cases):
    active_q = [p for p in row["questions"] if (p["id"], p["version"]) in selected]
    active_c = [p for p in row["cases"] if (p["id"], p["version"]) in cases]
    supported = {o for p in active_q for o in selected[(p["id"], p["version"])]["objective_ids"]}
    supported.update(o for p in active_c for o in cases[(p["id"], p["version"])]["objective_ids"])
    status = ("supporting" if row["relation"] == "curriculum_support" else "partial") if active_q or active_c else "gap"
    return {**row, "questions": active_q, "cases": active_c,
            "objective_ids": sorted(set(row["objective_ids"]) & supported), "status": status}


def programme_metadata(manifest, topics, cases, questions):
    general = {"id": "general_nephrology", "title": "General nephrology",
               "available": bool(questions), "available_families": len({q["family_id"] for q in questions})}
    if not manifest:
        return [general, {"id": "esen_eph", "title": "ESENeph preparation", "available": False,
                          "status": "not_formally_mapped", "reason": "No active content pack",
                          "exam_simulation_available": False}]
    programme = next((p for p in manifest.get("programme_mappings", []) if p["id"] == "esen_eph"), None)
    if not programme:
        return [general, {"id": "esen_eph", "title": "ESENeph preparation", "available": False,
                          "status": "not_formally_mapped", "reason": "The active pack has no formal mapping",
                          "exam_simulation_available": False}]
    selected = {(q["id"], q["version"]): q for q in questions}
    case_pins = {(c["id"], c["version"]): c for c in cases}
    mapped = mapped_question_pins(manifest, "esen_eph") & selected.keys()
    all_objectives = {o["id"] for t in topics for o in t["objectives"]}
    exam_objectives, support_objectives, mapped_cases = set(), set(), set()
    domains = []
    for domain in programme["domains"]:
        rows = [r for r in programme["alignments"] if r["domain_id"] == domain["id"]]
        pins = {(p["id"], p["version"]) for r in rows for p in r["questions"]} & selected.keys()
        families = {selected[p]["family_id"] for p in pins}
        active_rows = []
        for row in rows:
            active = _active_alignment(row, selected, case_pins)
            exam_objectives.update(active["objective_ids"])
            mapped_cases.update((p["id"], p["version"]) for p in active["cases"])
            active_rows.append(active)
        domains.append({**domain, "available_questions": len(pins), "available_families": len(families),
                        "family_shortfall": max(0, domain["indicative_questions"] - len(families)),
                        "status": "partial" if any(r["status"] == "partial" for r in active_rows) else "gap",
                        "alignments": active_rows})
    supporting_rows = [_active_alignment(row, selected, case_pins) for row in programme["alignments"]
                       if row["relation"] == "curriculum_support"]
    support_objectives.update(o for row in supporting_rows for o in row["objective_ids"])
    review_counts = Counter(selected[p]["review"]["status"] for p in mapped)
    metadata = {k: programme[k] for k in ("id", "version", "title", "checked_on", "status", "method",
                "reviewer_kind", "independent_human_review", "official_endorsement", "exam_simulation_available",
                "evidence", "exam")}
    metadata.update(
        available=bool(mapped), pack={"id": manifest["id"], "version": manifest["version"]},
        available_questions=len(mapped), available_families=len({selected[p]["family_id"] for p in mapped}),
        unmapped_questions=len(selected.keys() - mapped), available_cases=len(mapped_cases),
        aligned_objective_ids=sorted(exam_objectives), supporting_objective_ids=sorted(support_objectives),
        unaligned_objective_ids=sorted(all_objectives - exam_objectives - support_objectives),
        supporting_alignments=supporting_rows,
        excluded_questions=[pin for pin in programme.get("excluded_questions", [])
                            if (pin["id"], pin["version"]) in selected],
        option_count_distribution={str(n): count for n, count in sorted(Counter(len(selected[p]["options"]) for p in mapped).items())},
        format_compatible_questions=sum(len(selected[p]["options"]) == programme["exam"]["options_per_question"] for p in mapped),
        review_counts={s: review_counts[s] for s in ("assistant_reviewed", "human_reviewed")},
        domains=domains,
        coverage_note="Partial assistant mapping of original learning content. Domain weights are indicative; item counts and objective links do not establish full depth, clinician review, mastery or an exam simulation. Generated practice is excluded.",
    )
    if not mapped:
        metadata["reason"] = "No eligible active reviewed questions remain in the mapped track"
    return [general, metadata]
