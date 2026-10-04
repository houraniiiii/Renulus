# SPDX-License-Identifier: MIT
"""Read-only currency annotation for an original teaching case's pinned version."""

MAX_CURRENCY_ANNOTATIONS = 12


def pinned_currency(services, identifier, version) -> dict:
    result = {"kind": "case", "id": identifier, "version": version,
              "status": "unavailable", "needs_re_review": None,
              "annotations": [], "annotation_count": 0, "truncated": False}
    if not isinstance(identifier, str) or not identifier or type(version) is not int or version < 1:
        return result
    try:
        updates = services.registry.get("updates")
        reader = getattr(getattr(updates, "affected", None), "needs_re_review", None)
        if not callable(reader):
            return result
        # No live session ID, case text, prompts, history or source extraction
        # crosses this seam. The producer performs a local read by content ID.
        impact = reader("case", identifier, version)
        if (not isinstance(impact, dict) or impact.get("kind") != "case" or
                impact.get("id") != identifier or type(impact.get("version")) is not int or
                impact["version"] != version or type(impact.get("needs_re_review")) is not bool or
                not isinstance(impact.get("annotations"), list)):
            return result
        annotations = impact["annotations"]
        if any(not isinstance(row, dict) or row.get("kind") != "case" or
               row.get("entity_id") != identifier or type(row.get("version")) is not int or
               row["version"] != version or row.get("state") not in ("needs-re-review", "dismissed") or
               row.get("review_state") not in ("pending", "reviewed", "dismissed") for row in annotations):
            return result
        needs_review = impact["needs_re_review"]
        if needs_review != any(row["state"] == "needs-re-review" for row in annotations):
            return result
        # Display active warnings first. Keep the response bounded and exclude
        # source locators from hidden stages and any future producer payloads.
        active = (row for row in annotations if row["state"] == "needs-re-review")
        dismissed = (row for row in annotations if row["state"] == "dismissed")
        visible = []
        for group in (active, dismissed):
            for row in group:
                if len(visible) >= MAX_CURRENCY_ANNOTATIONS:
                    break
                visible.append({
                    "entry_id": row.get("entry_id", "")[:128] if isinstance(row.get("entry_id"), str) else "",
                    "title": row.get("title", "")[:500] if isinstance(row.get("title"), str) else "",
                    "detected_at": row.get("detected_at", "")[:64] if isinstance(row.get("detected_at"), str) else None,
                    "state": row["state"], "review_state": row["review_state"],
                })
        return {**result, "status": "needs-re-review" if needs_review else "no-known-impact",
                "needs_re_review": needs_review, "annotations": visible,
                "annotation_count": len(annotations), "truncated": len(annotations) > len(visible)}
    except Exception:
        # Missing migration/read failures remain unknown. Engine exceptions may
        # include private paths or input; neither log nor stringify them here.
        return result
