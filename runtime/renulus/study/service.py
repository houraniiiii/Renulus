from datetime import date, datetime, timedelta, timezone
import hashlib
import json

from renulus.contracts import ApiError
from renulus.storage import utc_now


class StudyService:
    def __init__(self, services):
        self.services, self.db = services, services.db

    def goals(self):
        row = self.db.fetch_one("SELECT value FROM preferences WHERE key='study.goals'")
        return json.loads(row["value"]) if row else {"hours_per_week": 3, "exam_date": None,
                                                    "topic_ids": [], "track": "general"}

    def save_goals(self, values):
        self.db.execute("INSERT INTO preferences VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                        ("study.goals", json.dumps(values), utc_now()))
        return self.goals()

    def topics(self):
        content = self.services.registry.get("content")
        if not content:
            return []
        result = content.list_topics()
        return result.get("topics", []) if isinstance(result, dict) else result

    def evidence(self):
        rows = self.db.fetch_all("SELECT * FROM learning_evidence ORDER BY created_at DESC LIMIT 2000")
        for row in rows:
            row["payload"] = json.loads(row.pop("payload_json"))
        return rows

    def progress(self):
        groups = {"fresh": {"answered": 0, "correct": 0},
                  "assisted": {"answered": 0, "correct": 0},
                  "repeat": {"answered": 0, "correct": 0}}
        topics = {}
        for row in self.evidence():
            if row["kind"] != "assessment-answer":
                continue
            payload = row["payload"]
            bucket = payload.get("score_bucket")
            if bucket not in groups:
                bucket = "assisted" if payload.get("assisted") else "repeat" if payload.get("repeat") else "fresh"
            groups[bucket]["answered"] += 1
            groups[bucket]["correct"] += int(bool(payload.get("correct")))
            topic = topics.setdefault(row["topic_id"], {"topic_id": row["topic_id"], "answered": 0,
                "correct": 0, "fresh_answered": 0, "fresh_correct": 0})
            topic["answered"] += 1
            topic["correct"] += int(bool(payload.get("correct")))
            if bucket == "fresh":
                topic["fresh_answered"] += 1
                topic["fresh_correct"] += int(bool(payload.get("correct")))
        return {"groups": groups, "topics": list(topics.values()),
                "interpretation": "Observed reviewed-question results. Conversations indicate interest, not mastery."}

    def list_activities(self):
        rows = self.db.fetch_all("SELECT * FROM study_activities ORDER BY due_date,created_at")
        for row in rows:
            row["reason"] = json.loads(row.pop("reason_json"))
            row["manual_override"] = bool(row["manual_override"])
        return rows

    def propose(self, today=None):
        today = today or date.today()
        goals, topics, evidence = self.goals(), self.topics(), self.evidence()
        names = {topic["id"]: topic.get("title", topic.get("name", topic["id"])) for topic in topics}
        selected = goals.get("topic_ids") or list(names)
        if not selected:
            return {"activities": self.list_activities(), "status": "waiting-content",
                    "message": "Install a topic pack to build your study plan."}
        available = max(1, min(14, round(goals["hours_per_week"] * 60 / 20)))
        candidates, seen_questions, seen_topics = [], set(), set()
        for row in evidence:
            if row["kind"] != "assessment-answer" or row["topic_id"] not in selected:
                continue
            payload = row["payload"]
            family = payload.get("family_id", payload.get("question_id", row["id"]))
            if family in seen_questions:
                continue
            seen_questions.add(family)
            # A later correct answer resolves an earlier mistake for scheduling, without rewriting it.
            if payload.get("correct"):
                continue
            candidates.append({"topic_id": row["topic_id"], "objective_id": payload.get("objective_id"),
                "kind": "mistake-review", "title": f"Review {names.get(row['topic_id'], row['topic_id'])}",
                "evidence_id": row["id"], "reason": {"kind": "committed-mistake",
                "evidence_id": row["id"], "question_id": payload.get("question_id"),
                "description": "Your latest recorded answer in this question family was incorrect."}})
            seen_topics.add(row["topic_id"])
        for topic_id in selected:
            if topic_id not in seen_topics:
                candidates.append({"topic_id": topic_id, "objective_id": None, "kind": "topic-study",
                    "title": f"Study {names.get(topic_id, topic_id)}", "evidence_id": None,
                    "reason": {"kind": "coverage", "description": "Explore an objective from your selected topics."}})
        now = utc_now()
        with self.db.transaction() as conn:
            for i, candidate in enumerate(candidates[:available]):
                due = (today + timedelta(days=min(6, i // max(1, available // 7)))).isoformat()
                identity = candidate["evidence_id"] or f"{today.isocalendar().year}-{today.isocalendar().week}:{candidate['topic_id']}"
                identifier = "study_" + hashlib.sha256(identity.encode()).hexdigest()[:24]
                conn.execute("INSERT OR IGNORE INTO study_activities VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (identifier, candidate["topic_id"], candidate["objective_id"], candidate["kind"],
                     candidate["title"], due, 20, json.dumps(candidate["reason"]), candidate["evidence_id"],
                     "planned", 0, now, now))
        return {"activities": self.list_activities(), "status": "ready",
                "explanation": "Committed mistakes are suggested first, followed by selected topic coverage. Manual changes are preserved."}

    def change_activity(self, identifier, values):
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM study_activities WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise ApiError("activity_missing", "This study activity is no longer available", 404)
            due, state = values.get("due_date", row["due_date"]), values.get("state", row["state"])
            conn.execute("UPDATE study_activities SET due_date=?,state=?,manual_override=1,updated_at=? WHERE id=?",
                         (due, state, utc_now(), identifier))
            if state == "completed":
                conn.execute("INSERT OR IGNORE INTO learning_evidence VALUES(?,?,?,?,?,?)",
                    (f"study:{identifier}", "study-completion", row["topic_id"], identifier,
                     json.dumps({"activity_id": identifier, "completion": "learner-confirmed"}), utc_now()))
        return next(activity for activity in self.list_activities() if activity["id"] == identifier)

    def home(self):
        learn = self.services.registry.get("learn")
        updates = self.services.registry.get("updates")
        today = date.today().isoformat()
        activities = [row for row in self.list_activities() if row["state"] == "planned"]
        return {"resume": learn.list_threads()[:3] if learn else [],
                "review": [row for row in activities if row["due_date"] <= today][:3],
                "upcoming": activities[:5], "topics": self.topics(), "goals": self.goals(),
                "progress": self.progress(),
                "updates": updates.list_entries(reviewed_only=True)[:3] if updates else []}
