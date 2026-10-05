"""Pinned generated keys and independent scores; case derivatives remain volatile."""
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from threading import Event as CancelFlag, RLock
from time import monotonic

from renulus.contracts import ApiError, ContextScope, Scope, durable_id
from renulus.storage.database import utc_now

from .generated_contracts import HandoffGuard
from .repository import encode

MAX_VOLATILE = 64
VOLATILE_SECONDS = 1800


def fingerprint(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


@dataclass
class PracticeRun:
    id: str
    key: str
    request_hash: str
    scope: ContextScope
    session_id: str
    topic_id: str | None
    count: int
    messages: list[dict]
    prompt: str
    handoff_id: str | None = None
    case_cancel: object | None = None
    cancel: CancelFlag = field(default_factory=CancelFlag)
    events: list = field(default_factory=list)
    status: str = "new"
    sequence: int = 0
    expires: float = field(default_factory=lambda: monotonic() + VOLATILE_SECONDS)


class GeneratedPracticeRepository:
    def __init__(self, services):
        self.services, self.db = services, services.db
        self.lock = RLock()
        self.volatile: dict[str, dict] = {}
        self.runs: dict[str, PracticeRun] = {}

    def capabilities(self):
        provider = self.services.registry.get("provider")
        available, verified = False, False
        blocked = False
        if provider is not None:
            status = provider.status()
            selected = status.get("selected_provider")
            connection = next((row for row in status.get("connections", [])
                               if row.get("provider") == selected), {})
            learning_use = connection.get("learning_use") or {}
            blocked = (learning_use.get("generation_allowed") is False or
                       (selected == "opencode-go" and learning_use.get("generation_allowed") is not True))
            if status.get("test_adapter") is True:
                available, blocked = True, False
            else:
                available = (not blocked and connection.get("status") == "connected"
                             and any(model.get("availability") == "available"
                                     for model in connection.get("models", [])))
            verified = status.get("live_provider_verified") is True
        return {"available": available, "reason": None if available else
                "OpenCode Go learning use is not confirmed. Renulus has paused learning requests."
                if blocked else "Connect an approved subscription before generating practice",
                "code": "learning_use_unverified" if blocked else None,
                "retryable": False if blocked else True,
                "live_provider_verified": verified, "maximum_questions": 5}

    def _expire(self):
        now = monotonic()
        for identifier, run in list(self.runs.items()):
            if run.expires <= now:
                run.cancel.set()
                run.messages.clear()
                run.prompt = ""
                del self.runs[identifier]
        for identifier, state in list(self.volatile.items()):
            if state["expires"] <= now:
                self.volatile.pop(identifier)

    def _cases(self):
        cases = self.services.registry.get("cases")
        if cases is None:
            raise ApiError("case_handoff_unavailable", "Return to Cases to start a new practice handoff", 503, True)
        return cases

    def guard_run(self, run):
        if run.cancel.is_set() or (run.case_cancel and run.case_cancel.is_set()):
            raise ApiError("practice_cancelled", "Practice generation was stopped", 409)
        if run.handoff_id:
            # Revalidate revision, deletion, expiry and saved revision before every reveal.
            self._cases().resolve_handoff(run.handoff_id, "generated-practice")

    def _guard(self, state):
        if state.get("guard_ticket"):
            self._cases().resolve_handoff(state["guard_ticket"], "generated-practice")

    @staticmethod
    def _check_command(previous, operation, target, request_hash):
        if previous and (previous["operation"] != operation or previous["target"] != target
                         or previous["request_hash"] != request_hash):
            raise ApiError("idempotency_conflict", "This request key was used for a different practice action", 409)
        return json.loads(previous["result_json"]) if previous else None

    def prepare(self, request):
        digest = fingerprint(request.model_dump(exclude={"idempotency_key"}))
        with self.lock:
            self._expire()
            previous = self.db.fetch_one("SELECT * FROM assessment_generated_commands WHERE idempotency_key=?",
                                         (request.idempotency_key,))
            replay = self._check_command(previous, "generate", "", digest)
            for run in self.runs.values():
                if run.key == request.idempotency_key:
                    if run.request_hash != digest:
                        raise ApiError("idempotency_conflict", "Use a new request key for changed practice input", 409)
                    if run.status == "running":
                        raise ApiError("practice_running", "This practice request is already running", 409, True)
                    if run.status == "completed" and run.scope.kind != Scope.GENERATED_PRACTICE:
                        state = self.volatile.get(run.session_id)
                        if not state:
                            raise ApiError("practice_expired", "Temporary practice has expired; start again", 410)
                        self._guard(state)
                    return run, replay
            if len(self.runs) >= MAX_VOLATILE:
                raise ApiError("practice_capacity", "Finish an existing practice request before starting another", 429, True)
            identifier = durable_id("practice")
            messages = [{"role": "user", "content": request.prompt}]
            scope = ContextScope(kind=Scope.GENERATED_PRACTICE, entity_id=identifier)
            handoff, cancel = None, None
            if request.case_handoff_id:
                handoff = self._cases().resolve_handoff(request.case_handoff_id, "generated-practice")
                scope = handoff["scope"]
                if scope.kind != Scope.TEMPORARY_CASE:
                    raise ApiError("case_scope_mismatch", "Case practice must remain temporary", 409)
                messages = handoff["messages"] + messages
                cancel = handoff["cancel"]
            elif request.context != "study":
                scope = ContextScope(kind=Scope.TEMPORARY_CASE if request.context == "temporary" else Scope.UNCLASSIFIED)
            run = PracticeRun(durable_id("practice_run"), request.idempotency_key, digest,
                              scope, identifier, request.topic_id, request.count, messages, request.prompt,
                              request.case_handoff_id, cancel)
            if replay is not None:
                run.session_id = replay["session"]["id"]
                run.scope = ContextScope.model_validate(replay["session"]["scope"])
            self.runs[run.id] = run
            return run, replay

    @staticmethod
    def public_item(item):
        return {"id": item["id"], "ordinal": item["ordinal"], "kind": "single_best_answer",
                "stem": item["stem"], "options": [{"id": o["id"], "text": o["text"]} for o in item["options"]],
                "assisted": item["assisted"]}

    @staticmethod
    def scores(state):
        result = {name: {"answered": 0, "correct": 0, "accuracy": None} for name in ("unassisted", "assisted")}
        for attempt in state["attempts"].values():
            bucket = result["assisted" if attempt["assisted"] else "unassisted"]
            bucket["answered"] += 1
            bucket["correct"] += int(attempt["correct"])
        for bucket in result.values():
            if bucket["answered"]:
                bucket["accuracy"] = bucket["correct"] / bucket["answered"]
        return result

    def view(self, state, present=False):
        current = next((item for item in state["items"] if item["id"] not in state["attempts"]), None)
        if present and state["status"] == "active" and current:
            current["presented"] = True
        return {"id": state["id"], "mode": "generated", "scope": state["scope"],
                "retention": "persistent" if state["scope"]["kind"] == "generated-practice" else "volatile",
                "status": state["status"], "topic_id": state["topic_id"],
                "created_at": state["created_at"], "updated_at": state["updated_at"],
                "item_count": len(state["items"]), "answered_count": len(state["attempts"]),
                "current_item": self.public_item(current) if present and state["status"] == "active" and current else None,
                "scores": self.scores(state), "source_verification": state["source_verification"]}

    def _load(self, conn, identifier):
        row = conn.execute("SELECT * FROM assessment_generated_sessions WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise ApiError("practice_not_found", "This practice session was not found or has expired", 404)
        state = dict(row)
        state["scope"] = {"kind": "generated-practice", "entity_id": identifier}
        state["items"] = []
        for raw in conn.execute("SELECT * FROM assessment_generated_items WHERE session_id=? ORDER BY ordinal", (identifier,)):
            item = json.loads(raw["snapshot_json"])
            item.update(assisted=bool(raw["assisted"]), presented=bool(raw["presented"]))
            state["items"].append(item)
        state["attempts"] = {}
        for raw in conn.execute("SELECT * FROM assessment_generated_attempts WHERE session_id=?", (identifier,)):
            attempt = dict(raw)
            attempt["selected_option_ids"] = json.loads(attempt.pop("answer_json"))
            attempt.update(correct=bool(attempt["correct"]), assisted=bool(attempt["assisted"]))
            state["attempts"][attempt["item_id"]] = attempt
        return state

    @staticmethod
    def _save(conn, state, new=False):
        if new:
            conn.execute("INSERT INTO assessment_generated_sessions VALUES(?,?,?,?,?,?,?)",
                         (state["id"], "generated-practice", state["status"], state["topic_id"],
                          state["source_verification"], state["created_at"], state["updated_at"]))
            for item in state["items"]:
                conn.execute("INSERT INTO assessment_generated_items VALUES(?,?,?,?,?,?)",
                             (item["id"], state["id"], item["ordinal"], encode(item),
                              int(item["assisted"]), int(item["presented"])))
        else:
            conn.execute("UPDATE assessment_generated_sessions SET status=?,updated_at=? WHERE id=?",
                         (state["status"], state["updated_at"], state["id"]))
            for item in state["items"]:
                conn.execute("UPDATE assessment_generated_items SET assisted=?,presented=? WHERE id=?",
                             (int(item["assisted"]), int(item["presented"]), item["id"]))
        for attempt in state["attempts"].values():
            if not conn.execute("SELECT 1 FROM assessment_generated_attempts WHERE id=?", (attempt["id"],)).fetchone():
                conn.execute("INSERT INTO assessment_generated_attempts VALUES(?,?,?,?,?,?,?)",
                             (attempt["id"], state["id"], attempt["item_id"], encode(attempt["selected_option_ids"]),
                              int(attempt["correct"]), int(attempt["assisted"]), attempt["committed_at"]))

    def publish(self, run, batch, citations):
        with self.lock:
            self.guard_run(run)
            now = utc_now()
            state = {"id": run.session_id, "scope": run.scope.model_dump(mode="json"), "status": "active",
                     "topic_id": run.topic_id, "created_at": now, "updated_at": now, "attempts": {},
                     "source_verification": "retrieved" if citations else "not-verified", "items": [],
                     "commands": {}, "expires": monotonic() + VOLATILE_SECONDS}
            for ordinal, question in enumerate(batch.items, 1):
                item = question.model_dump()
                item.update(id=durable_id("practice_item"), ordinal=ordinal, version="1", assisted=False, presented=False,
                            sources=[citations[index] for index in question.source_indices])
                state["items"].append(item)
            result = {"session": self.view(state, present=True)}
            if run.scope.kind == Scope.GENERATED_PRACTICE:
                with self.db.transaction() as conn:
                    previous = conn.execute("SELECT * FROM assessment_generated_commands WHERE idempotency_key=?", (run.key,)).fetchone()
                    replay = self._check_command(previous, "generate", "", run.request_hash)
                    if replay is not None:
                        return replay
                    self._save(conn, state, new=True)
                    self._record(conn, run.key, "generate", "", run.request_hash, result)
            else:
                self._expire()
                if len(self.volatile) >= MAX_VOLATILE:
                    raise ApiError("practice_capacity", "Finish existing temporary practice before starting another", 429, True)
                if run.handoff_id:
                    # Cases performs the final revision/cancellation check before
                    # appending only a key-free completion marker to volatile context.
                    cases = self._cases()
                    case = cases.commit_handoff(run.handoff_id, "generated-practice",
                        "Generated practice: " + str(len(state["items"])) + " questions ready. Practice results remain separate.",
                        cancel=run.case_cancel, scope=run.scope)
                    ticket = cases.handoff(case["id"], HandoffGuard(revision=case["revision"]))
                    state["guard_ticket"] = ticket["case_handoff_id"]
                self.volatile[state["id"]] = state
            return result

    @staticmethod
    def _record(conn, key, operation, target, digest, result):
        conn.execute("INSERT INTO assessment_generated_commands VALUES(?,?,?,?,?,?)",
                     (key, operation, target, digest, encode(result), utc_now()))

    def mutate(self, identifier, operation, request, work):
        digest = fingerprint(request.model_dump(exclude={"idempotency_key"}) if request else {})
        key = request.idempotency_key if request else None
        with self.lock:
            self._expire()
            if identifier in self.volatile:
                state = deepcopy(self.volatile[identifier])
                if operation != "end":
                    self._guard(state)
                if key:
                    previous = state["commands"].get(key)
                    replay = self._check_command(previous, operation, identifier, digest)
                    if replay is not None:
                        return replay
                state["updated_at"] = utc_now()
                result = work(state)
                if key:
                    state["commands"][key] = {"operation": operation, "target": identifier,
                                              "request_hash": digest, "result_json": encode(result)}
                self.volatile[identifier] = state
                return result
            with self.db.transaction() as conn:
                state = self._load(conn, identifier)
                if key:
                    previous = conn.execute("SELECT * FROM assessment_generated_commands WHERE idempotency_key=?", (key,)).fetchone()
                    replay = self._check_command(previous, operation, identifier, digest)
                    if replay is not None:
                        return replay
                state["updated_at"] = utc_now()
                result = work(state)
                self._save(conn, state)
                if key:
                    self._record(conn, key, operation, identifier, digest, result)
                return result

    def session(self, identifier):
        return self.mutate(identifier, "session", None, lambda state: self.view(state, present=True))

    def sessions(self):
        # Temporary sessions have no discovery/history endpoint.
        with self.lock, self.db.transaction() as conn:
            rows = conn.execute("SELECT id FROM assessment_generated_sessions ORDER BY updated_at DESC LIMIT 100").fetchall()
            return {"sessions": [self.view(self._load(conn, row["id"])) for row in rows]}

    @staticmethod
    def _current(state, item_id):
        if state["status"] != "active":
            raise ApiError("practice_not_active", "Resume this practice session before answering", 409)
        item = next((item for item in state["items"] if item["id"] == item_id), None)
        if item is None:
            raise ApiError("practice_item_not_found", "This question does not belong to the practice session", 404)
        if item_id in state["attempts"]:
            raise ApiError("answer_already_committed", "This practice answer is committed; use its original request key to retry", 409)
        if not item["presented"]:
            raise ApiError("item_not_presented", "Open this practice question before answering", 409)
        return item

    def feedback(self, item, attempt):
        return {"attempt_id": attempt["id"], "item": self.public_item(item),
                "selected_option_ids": attempt["selected_option_ids"],
                "correct_option_ids": [item["correct_option_id"]],
                "correct": attempt["correct"], "assisted": attempt["assisted"],
                "committed_at": attempt["committed_at"], "explanation": item["explanation"],
                "options": item["options"], "sources": item["sources"], "verification": "generated-unreviewed"}

    def answer(self, identifier, request):
        def work(state):
            item = self._current(state, request.item_id)
            if len(request.option_ids) != 1 or request.option_ids[0] not in {option["id"] for option in item["options"]}:
                raise ApiError("invalid_answer", "Choose one of this practice question's options", 422)
            attempt = {"id": durable_id("practice_attempt"), "item_id": item["id"],
                       "selected_option_ids": request.option_ids, "correct": request.option_ids == [item["correct_option_id"]],
                       "assisted": item["assisted"], "committed_at": utc_now()}
            state["attempts"][item["id"]] = attempt
            return {"feedback": self.feedback(item, attempt), "session": self.view(state)}
        return self.mutate(identifier, "answer", request, work)

    def help(self, identifier, request):
        def work(state):
            item = self._current(state, request.item_id)
            if request.kind == "hint" and not item.get("hint"):
                raise ApiError("hint_unavailable", "This practice question has no generated hint", 409)
            item["assisted"] = True
            return {"item_id": item["id"], "assisted": True, "kind": request.kind,
                    "hint": item.get("hint") if request.kind == "hint" else None,
                    "sources": item["sources"] if request.kind == "sources" else []}
        return self.mutate(identifier, "help", request, work)

    def review(self, identifier):
        def work(state):
            return {"session_id": identifier, "scores": self.scores(state),
                    "feedback": [self.feedback(item, state["attempts"][item["id"]])
                                 for item in state["items"] if item["id"] in state["attempts"]]}
        return self.mutate(identifier, "review", None, work)

    def transition(self, identifier, operation, request):
        def work(state):
            if state["status"] == "ended" and operation != "end":
                raise ApiError("practice_ended", "This practice session ended; start a new one", 409)
            state["status"] = {"pause": "paused", "resume": "active", "end": "ended"}[operation]
            return self.view(state, present=operation == "resume")
        return self.mutate(identifier, operation, request, work)

    def cancel(self, run_id):
        with self.lock:
            run = self.runs.get(run_id)
            if run and run.status not in ("completed", "error", "cancelled"):
                run.cancel.set()
            return {"run_id": run_id, "cancelled": True}
