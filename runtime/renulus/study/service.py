from datetime import date, timedelta
import hashlib
import json

from renulus.contracts import ApiError
from renulus.storage import utc_now

TRACK_IDS = {"general": "general_nephrology", "eseneph": "esen_eph"}


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

    def tracks(self):
        content = self.services.registry.get("content")
        metadata = getattr(content, "track_metadata", None)
        if metadata is not None:
            return metadata()
        # An older/missing producer cannot establish ESENeph alignment. General
        # topic study remains usable without manufacturing a programme mapping.
        return [{"id": "general_nephrology", "title": "General nephrology"},
                {"id": "esen_eph", "title": "ESENeph preparation",
                 "available": False, "status": "not_formally_mapped",
                 "exam_simulation_available": False,
                 "reason": "Programme metadata is not available from the active content pack."}]

    def selection(self, goals=None, topics=None, tracks=None):
        goals = self.goals() if goals is None else goals
        topics = self.topics() if topics is None else topics
        tracks = self.tracks() if tracks is None else tracks
        track_id = TRACK_IDS[goals["track"]]
        metadata = next((row for row in tracks if row["id"] == track_id), {})
        requested = set(goals.get("topic_ids") or (topic["id"] for topic in topics))
        selected = [topic for topic in topics if topic["id"] in requested]
        objectives = {}
        if track_id == "esen_eph":
            # Only active exam-domain links count here. Curriculum-support links
            # remain visible in the producer metadata, separate from this plan.
            aligned = set(metadata.get("aligned_objective_ids", []))
            for topic in selected:
                linked = [o["id"] for o in topic.get("objectives", []) if o["id"] in aligned]
                if linked:
                    objectives[topic["id"]] = linked
            selected = [topic for topic in selected if topic["id"] in objectives]
        status, message = "ready", None
        if track_id == "esen_eph" and not metadata.get("available", False):
            selected, objectives = [], {}
            status = "track-unavailable"
            message = metadata.get("reason", "No active ESENeph mapping is available.")
        elif not topics:
            status, message = "waiting-content", "Install a topic pack to build your study plan."
        elif not selected:
            status, message = "waiting-topics", "No active topics match these preferences. Choose other topics or a different track."
        return {"track": track_id, "title": metadata.get("title", track_id),
                "status": status, "message": message,
                "topic_ids": [topic["id"] for topic in selected],
                "objective_ids": objectives, "mapping_version": metadata.get("version")}

    def evidence(self):
        rows = self.db.fetch_all("SELECT * FROM learning_evidence ORDER BY created_at DESC,rowid DESC LIMIT 2000")
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

    @staticmethod
    def mapped_pins(track):
        return {(pin["id"], str(pin["version"])) for domain in track.get("domains", [])
                for alignment in domain.get("alignments", []) for pin in alignment.get("questions", [])}

    def list_activities(self, selection=None, tracks=None):
        rows = self.db.fetch_all("SELECT * FROM study_activities ORDER BY due_date,created_at")
        for row in rows:
            row["reason"] = json.loads(row.pop("reason_json"))
            row["manual_override"] = bool(row["manual_override"])
        if selection is not None:
            track = next((t for t in (self.tracks() if tracks is None else tracks)
                          if t["id"] == selection["track"]), {})
            pins = self.mapped_pins(track)
            visible = []
            for row in rows:
                matches = (row["topic_id"] in selection["topic_ids"]
                           and row["reason"].get("track", "general_nephrology") == selection["track"])
                if selection["track"] == "esen_eph":
                    matches = (matches and row["reason"].get("mapping_version") == selection["mapping_version"]
                               and row["objective_id"] in selection["objective_ids"].get(row["topic_id"], []))
                    if row["kind"] == "mistake-review":
                        matches = matches and (row["reason"].get("question_id"),
                                               str(row["reason"].get("question_version"))) in pins
                if matches or row["manual_override"] or row["state"] != "planned":
                    row["outside_selection"] = not matches
                    visible.append(row)
            return visible
        return rows

    def plan(self):
        tracks = self.tracks()
        selection = self.selection(tracks=tracks)
        return {"activities": self.list_activities(selection, tracks), "selection": selection, "tracks": tracks}

    def propose(self, today=None):
        today = today or date.today()
        goals, topics, evidence = self.goals(), self.topics(), self.evidence()
        names = {topic["id"]: topic.get("title", topic.get("name", topic["id"])) for topic in topics}
        tracks = self.tracks()
        selection = self.selection(goals, topics, tracks)
        selected = selection["topic_ids"]
        if not selected:
            return {"activities": self.list_activities(selection, tracks), "status": selection["status"],
                    "message": selection["message"], "selection": selection, "tracks": tracks}
        track = next((row for row in tracks if row["id"] == selection["track"]), {})
        pins = self.mapped_pins(track)
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
            objective_id = payload.get("objective_id")
            if selection["track"] == "esen_eph":
                linked = selection["objective_ids"][row["topic_id"]]
                objective_id = next((o for o in payload.get("objective_ids", [objective_id]) if o in linked), None)
                if (payload.get("question_id"), str(payload.get("question_version"))) not in pins or objective_id is None:
                    continue
            candidates.append({"topic_id": row["topic_id"], "objective_id": objective_id,
                "kind": "mistake-review", "title": f"Review {names.get(row['topic_id'], row['topic_id'])}",
                "evidence_id": row["id"], "reason": {"kind": "committed-mistake",
                "evidence_id": row["id"], "question_id": payload.get("question_id"),
                "question_version": payload.get("question_version"),
                "description": "Your latest recorded answer in this question family was incorrect."}})
            seen_topics.add(row["topic_id"])
        for topic_id in selected:
            if topic_id not in seen_topics:
                linked = selection["objective_ids"].get(topic_id, [])
                candidates.append({"topic_id": topic_id, "objective_id": linked[0] if linked else None, "kind": "topic-study",
                    "title": f"Study {names.get(topic_id, topic_id)}", "evidence_id": None,
                    "reason": {"kind": "coverage", "description":
                        "Explore an objective linked to a partially mapped ESENeph exam domain."
                        if selection["track"] == "esen_eph" else "Explore an objective from your selected topics."}})
        now = utc_now()
        with self.db.transaction() as conn:
            for i, candidate in enumerate(candidates[:available]):
                candidate["reason"].update(track=selection["track"])
                if selection["track"] == "esen_eph":
                    candidate["reason"].update(mapping_version=selection["mapping_version"],
                                               mapping_checked_on=track.get("checked_on"))
                due = (today + timedelta(days=min(6, i // max(1, available // 7)))).isoformat()
                identity = candidate["evidence_id"] or f"{today.isocalendar().year}-{today.isocalendar().week}:{candidate['topic_id']}"
                if selection["track"] == "esen_eph":
                    identity = f"esen_eph:{selection['mapping_version']}:{identity}"
                identifier = "study_" + hashlib.sha256(identity.encode()).hexdigest()[:24]
                conn.execute("INSERT OR IGNORE INTO study_activities VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (identifier, candidate["topic_id"], candidate["objective_id"], candidate["kind"],
                     candidate["title"], due, 20, json.dumps(candidate["reason"]), candidate["evidence_id"],
                     "planned", 0, now, now))
        return {"activities": self.list_activities(selection, tracks), "status": "ready",
                "selection": selection, "tracks": tracks,
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
        return next(activity for activity in self.plan()["activities"] if activity["id"] == identifier)

    def home(self):
        learn = self.services.registry.get("learn")
        updates = self.services.registry.get("updates")
        today = date.today().isoformat()
        topics, tracks, goals = self.topics(), self.tracks(), self.goals()
        selection = self.selection(goals, topics, tracks)
        activities = [row for row in self.list_activities(selection, tracks) if row["state"] == "planned"]
        return {"resume": learn.list_threads()[:3] if learn else [],
                "review": [row for row in activities if row["due_date"] <= today][:3],
                "upcoming": activities[:5], "topics": topics, "goals": goals,
                "tracks": tracks, "selection": selection,
                "progress": self.progress(),
                "updates": updates.list_entries(reviewed_only=True)[:3] if updates else []}
