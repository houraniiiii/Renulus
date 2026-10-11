# SPDX-License-Identifier: MIT
"""Route child learning callbacks before the learning Owner root-only guard.

Children retains all canonical claims, model pins and native/Domain tasks. The
learner-context callback must return already pinned root text without IO or a
transaction; it is called inside a local canonical validation transaction.

The parent composes one helper per actual native generation. Resolve model pins
outside writers, and call require_publication_in in the root publication write.
Seal/settlement follows that publication, or the canonical cancellation seal.
"""
from collections.abc import Callable
import inspect
import json
import re
import sqlite3

from renulus.contracts import ApiError
from .harness_children import ChildStatus, HarnessChildren
from .harness_domain import DomainBinding, DomainGrant, DomainRequest
from .harness_model_registry import ModelRunAuthority


def _context_ids(binding: DomainBinding, messages, *, excluded=()) -> list[str]:
    def invalid():
        raise ApiError("harness_context_conflict", "Use verifiable native context descriptors.", 409)

    if type(messages) is not list:
        invalid()
    origins = {}
    for item in messages:
        if (type(item) is not dict or set(item) != {"id", "role"}
                or type(item["id"]) is not str
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}", item["id"]) is None
                or type(item["role"]) is not str or item["role"] not in {"user", "assistant", "tool"}):
            invalid()
        if item["role"] == "tool":
            if origins.get(item["id"]) != "assistant":
                invalid()
        elif item["id"] in origins:
            invalid()
        else:
            origins[item["id"]] = item["role"]
    positions = [index for index, item in enumerate(messages)
        if item == {"id": binding.input_id, "role": "user"}]
    if len(positions) != 1:
        raise ApiError("harness_input_conflict", "The admitted child USER is absent or changed.", 409)
    boundary = positions[0]
    suffix = messages[boundary:]
    previous = {item["id"] for item in messages[:boundary]}
    if (any(item["role"] == "user" for item in suffix[1:])
            or any(item["id"] in previous or item["id"] in excluded for item in suffix)):
        invalid()
    return list(dict.fromkeys(item["id"] for item in suffix))


class HarnessLearningChildren:
    def __init__(self, children: HarnessChildren, *, learner_context: Callable[[DomainBinding], str]):
        self.children = children
        self.learner_context = learner_context

    def resolve_model_run(self, binding: DomainBinding) -> ModelRunAuthority | None:
        return self.children.resolve_model_run(binding)

    def require_publication_in(self, conn: sqlite3.Connection, *, root_binding: DomainBinding) -> None:
        return self.children.require_publication_in(conn, root_binding=root_binding)

    def seal(self, root_binding: DomainBinding) -> None:
        return self.children.seal(root_binding)

    def status(self, root_binding: DomainBinding | None = None) -> ChildStatus:
        return self.children.status(root_binding)

    async def settlement(self, root_binding: DomainBinding, timeout: float) -> dict:
        return await self.children.settlement(root_binding, timeout)

    def _learner_text(self, root_binding):
        context = self.learner_context(root_binding)
        if inspect.isawaitable(context):
            if inspect.iscoroutine(context):
                context.close()
            raise ApiError("child_local_callback_required", "Use cached local learner context.", 422)
        if type(context) is str:
            try:
                if len(context.encode("utf-16-le")) // 2 <= 3000:
                    return context
            except UnicodeError:
                pass
        raise ApiError("harness_context_conflict", "Use bounded pinned learner text.", 409)

    async def authorize(self, request: DomainRequest) -> DomainGrant | None:
        if request.command in {"child.prepare", "child.admit_input", "child.check",
                "child.observe_job", "child.report", "child.consume_report"}:
            return await self.children.authorize(request)
        if request.command not in {"learning.authority", "learning.check", "learning.context",
                "library.retrieve", "library.citation"}:
            return None
        with self.children.db.transaction() as conn:
            row = self.children.journal.child_in(conn, request.binding.operation_id)
        if row is None:
            return None
        if request.command in {"library.retrieve", "library.citation"}:
            return await self.children.authorize(request)
        model = self.children.resolve_model_run(request.binding)
        if model is None:
            raise ApiError("child_binding_conflict", "Use the admitted child input.", 409)
        expected = {"messages"} if request.command == "learning.context" else set()
        if type(request.payload) is not dict or set(request.payload) != expected:
            raise ApiError("harness_callback_payload", "Use the exact child learning payload.", 422)
        if request.command == "learning.context":
            _context_ids(request.binding, request.payload["messages"],
                excluded=(row.parent_binding.input_id, row.message_id))
            encoded = json.dumps(request.payload, separators=(",", ":")).encode()
            if len(encoded) > self.children.bounds.max_work_bytes:
                raise ApiError("harness_callback_payload", "Use bounded context descriptors.", 422)
        payload = ({"messages": [dict(item) for item in request.payload["messages"]]}
            if request.command == "learning.context" else dict(request.payload))
        captured = DomainRequest(request.callback_id, request.binding, request.command, payload)

        def current(*, conn=None):
            if conn is None:
                with self.children.db.transaction() as transaction:
                    return current(conn=transaction)
            model.current(conn=conn)
            latest = self.children.journal.child_in(conn, model.binding.operation_id)
            if latest.state != "admitted":
                raise ApiError("child_report_closed", "The child learning callbacks are closed.", 409)
            return True

        current()

        async def handle(supplied, cancellation):
            if supplied != captured:
                raise ApiError("child_callback_conflict", "Use the captured child callback.", 409)
            cancellation.check_current()
            with self.children.db.transaction() as conn:
                current(conn=conn)
                if supplied.command == "learning.check":
                    result = {"current": True}
                elif supplied.command == "learning.context":
                    messages = supplied.payload["messages"]
                    result = {"message_ids": _context_ids(supplied.binding, messages,
                        excluded=(row.parent_binding.input_id, row.message_id)),
                        "learner_context": self._learner_text(row.parent_binding)}
                else:
                    parent = self.children.resolve_parent(row.parent_binding)
                    result = {"sessionId": request.binding.session_id,
                        "operationId": request.binding.operation_id,
                        "attemptId": request.binding.attempt_id,
                        "scope": parent.library.scope.model_dump(mode="json"),
                        "revisionIds": parent.library.revision_ids,
                        "policyRevision": parent.library.policy_revision,
                        "contextEpoch": parent.library.context_epoch,
                        "cancellationEpoch": row.family_epoch}
                current(conn=conn)
            cancellation.check_current()
            return result

        return DomainGrant(request.binding, handle, current, model.cancellation)
