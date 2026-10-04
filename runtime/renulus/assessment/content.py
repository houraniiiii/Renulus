"""Narrow consumer of M8's ContentRepository; no independent pack reader."""
from copy import deepcopy

from renulus.contracts import ApiError


class ContentGateway:
    def __init__(self, services):
        self.services = services

    @property
    def repository(self):
        return self.services.get("content")

    def summaries(self, selector):
        questions = self.repository.list_question_summaries(track=selector.track)
        selected = []
        for question in questions:
            topic = question["topic_id"]
            if selector.topic_ids and topic not in selector.topic_ids:
                continue
            if selector.domain_ids and topic not in selector.domain_ids:
                continue
            review = question.get("review", {})
            if (question.get("usage") == "assessment_reserved"
                    and review.get("status") in ("assistant_reviewed", "human_reviewed")
                    and review.get("source_key_checked") is True):
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
