"""Narrow consumer of M8's ContentRepository; no independent pack reader."""
from copy import deepcopy

from renulus.contracts import ApiError


class ContentGateway:
    def __init__(self, services):
        self.services = services

    @property
    def repository(self):
        return self.services.get("content")

    @staticmethod
    def _reviewed(question):
        review = question.get("review", {})
        return (question.get("usage") == "assessment_reserved"
                and review.get("status") in ("assistant_reviewed", "human_reviewed")
                and review.get("source_key_checked") is True)

    def tracks(self):
        metadata = getattr(self.repository, "track_metadata", None)
        if callable(metadata):
            # Keep this consumer key-free even if the producer adds richer
            # content fields. Programme mapping remains entirely M8-owned.
            fields = ("id", "title", "version", "available", "available_families",
                      "available_questions", "status", "reason", "coverage_note",
                      "checked_on", "format_compatible_questions")
            domain_fields = ("id", "label", "status", "indicative_questions",
                             "available_questions", "available_families", "family_shortfall")
            return [{**{field: deepcopy(track[field]) for field in fields if field in track},
                     "exam_simulation_available": False,
                     "domains": [{field: deepcopy(domain[field]) for field in domain_fields
                                  if field in domain} for domain in track.get("domains", [])]}
                    for track in metadata()]
        # Legacy packs/test adapters have no programme contract. Their general
        # pool remains usable; no topic label or ID implies an ESENeph mapping.
        questions = [q for q in self.repository.list_question_summaries(track="general_nephrology")
                     if self._reviewed(q)]
        return [{"id": "general_nephrology", "title": "General nephrology",
                 "available": bool(questions), "available_questions": len(questions),
                 "available_families": len({q["family_id"] for q in questions}),
                 "exam_simulation_available": False, "domains": []},
                {"id": "esen_eph", "title": "ESENeph preparation", "available": False,
                 "available_questions": 0, "available_families": 0,
                 "status": "not_formally_mapped",
                 "reason": "The installed content does not provide formal ESENeph track metadata",
                 "exam_simulation_available": False, "domains": []}]

    def summaries(self, selector, tracks=None):
        tracks = self.tracks() if tracks is None else tracks
        track_id = selector.track or "general_nephrology"
        if not any(track["id"] == track_id and track["available"] for track in tracks):
            return []
        questions = self.repository.list_question_summaries(track=selector.track)
        selected = []
        for question in questions:
            topic = question["topic_id"]
            if selector.topic_ids and topic not in selector.topic_ids:
                continue
            if selector.domain_ids and topic not in selector.domain_ids:
                continue
            if self._reviewed(question):
                selected.append(question)
        return selected

    def topics(self):
        return self.repository.list_topics()

    def pin(self, summary):
        try:
            question = deepcopy(self.repository.get_question_version(
                summary["id"], summary["version"]))
        except LookupError as error:
            raise ApiError("content_unavailable", "The selected question is unavailable",
                           409, True) from error
        for field in ("id", "version", "key_version", "family_id", "family_version",
                      "topic_id"):
            if question.get(field) != summary.get(field):
                raise ApiError("content_version_conflict",
                               "The question changed during selection; choose again", 409, True)
        if question.get("withdrawn"):
            raise ApiError("content_withdrawn", "The selected question was withdrawn", 409, True)
        options = question.get("options", [])
        option_ids = [option.get("id") for option in options]
        correct = question.get("correct_option_ids", [])
        if (question.get("kind") != "single_best_answer" or len(correct) != 1
                or len(option_ids) < 2 or len(set(option_ids)) != len(option_ids)
                or not set(correct).issubset(option_ids) or not question.get("explanation")
                or not question.get("sources")):
            raise ApiError("unsupported_question",
                           "This item does not have a compatible reviewed key", 409)
        # Domain selection uses M8's current stable topic IDs. It does not claim
        # these are an accredited ESENeph blueprint.
        question["domain_id"] = question["topic_id"]
        records = {source["id"]: source for source in question.get("source_records", [])}
        question["sources"] = [{**citation,
            **{field: records[citation["source_id"]][field]
               for field in ("title", "url", "edition", "checked_on", "check_status", "currency")
               if field in records.get(citation["source_id"], {})}}
            for citation in question["sources"]]
        return question

    def annotation(self, item):
        try:
            current = self.repository.get_question_version(
                item["question_id"], int(item["question_version"]))
        except (LookupError, ApiError):
            return {"status": "unavailable", "withdrawn": None,
                    "current_version": None, "withdrawal": None,
                    "message": "Current content status could not be checked; retained score is unchanged"}
        withdrawn = bool(current.get("withdrawn"))
        version = current.get("current_version")
        if withdrawn:
            status = "withdrawn"
        elif version is None:
            status = "inactive"
        elif str(version) != item["question_version"]:
            status = "corrected"
        else:
            status = "current"
        return {"status": status, "withdrawn": withdrawn, "current_version": version,
                "withdrawal": current.get("withdrawal"),
                "message": ("Scored with the pinned historical key; retained score is unchanged"
                            if status != "current" else None)}
