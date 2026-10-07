"""Live, key-free source annotations; never part of committed assessment facts."""


def without_currency(value):
    """Keep command acknowledgments immutable while annotations remain live."""
    if isinstance(value, dict):
        return {key: without_currency(item) for key, item in value.items() if key != "source_currency"}
    if isinstance(value, list):
        return [without_currency(item) for item in value]
    return value


class SourceCurrency:
    def __init__(self, services):
        self.services = services

    def for_item(self, item):
        unavailable = {"state": "unavailable", "needs_re_review": None, "annotations": []}
        updates = self.services.registry.get("updates")
        lookup = getattr(getattr(updates, "affected", None), "needs_re_review", None)
        if not callable(lookup):
            return unavailable
        try:
            identifier, version = item["question_id"], int(item["question_version"])
            result = lookup("question", identifier, version)
            if (not isinstance(result, dict) or not isinstance(result.get("needs_re_review"), bool)
                    or (result.get("kind"), result.get("id"), result.get("version")) != ("question", identifier, version)
                    or not isinstance(result.get("annotations"), list)):
                return unavailable
            annotations = []
            for row in result["annotations"]:
                if row["state"] not in ("needs-re-review", "dismissed") or row["review_state"] not in ("pending", "reviewed", "dismissed"):
                    return unavailable
                if (not isinstance(row["locators"], list) or not all(isinstance(value, str) for value in row["locators"])
                        or not all(isinstance(row[key], str) and row[key] for key in
                                   ("entry_id", "pinned_source_id", "register_id", "detected_at"))):
                    return unavailable
                # Source review findings, bank stems and keys cannot cross this
                # display projection before a committed answer.
                annotations.append({key: row[key] for key in ("entry_id", "pinned_source_id", "register_id",
                    "locators", "detected_at", "state", "review_state")})
            if result["needs_re_review"] != any(row["state"] == "needs-re-review" for row in annotations):
                return unavailable
            return {"state": "available", "needs_re_review": result["needs_re_review"], "annotations": annotations}
        except Exception:
            # Availability is independent of the question's published key and
            # deterministic scoring. A failed lookup cannot claim no notices.
            return unavailable

    def session(self, conn, session, cache=None):
        rows = conn.execute("SELECT i.question_id,i.question_version,a.id AS attempt_id FROM assessment_items i LEFT JOIN assessment_attempts a ON a.item_id=i.id WHERE i.session_id=?", (session["id"],)).fetchall()
        cache = {} if cache is None else cache
        affected, pending, dismissed, unavailable, notices = 0, 0, 0, 0, set()
        for row in rows:
            key = (row["question_id"], row["question_version"])
            if key not in cache:
                cache[key] = self.for_item(row)
            currency = cache[key]
            unavailable += currency["state"] == "unavailable"
            if currency["needs_re_review"]:
                affected += 1
                pending += row["attempt_id"] is None
            elif any(annotation["state"] == "dismissed" for annotation in currency["annotations"]):
                dismissed += 1
            notices.update(annotation["entry_id"] for annotation in currency["annotations"])
        session["source_currency"] = {
            "state": "unavailable" if unavailable and unavailable == len(rows) else "partial" if unavailable else "available",
            "needs_re_review": True if affected else None if unavailable else False,
            "affected_count": affected, "pending_affected_count": pending, "dismissed_count": dismissed,
            "question_count": len(rows), "notice_count": len(notices),
        }
        if session.get("current_item"):
            item = session["current_item"]
            key = (item["question_id"], item["question_version"])
            item["source_currency"] = cache[key] if key in cache else self.for_item(item)
        return session

    def replay(self, conn, result):
        # Refresh only source annotations on a saved acknowledgment. Replayed
        # session, answer, key, assistance, score and dates remain exactly pinned.
        if "current_item" in result:
            self.session(conn, result)
        if isinstance(result.get("session"), dict):
            self.session(conn, result["session"])
        if isinstance(result.get("feedback"), dict):
            feedback = result["feedback"]
            feedback["source_currency"] = self.for_item(feedback["item"])
        return result
