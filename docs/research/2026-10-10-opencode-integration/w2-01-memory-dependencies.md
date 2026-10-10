# W2-01 — Memory dependencies and completed-answer receipts

2026-10-10. **Research only; four focused reproductions, no implementation.** Renulus source: `528025ff0b22477c12ee1512e0e7d15297a6e888`; inspected implementation directories match HEAD. OpenCode static evidence: `4b6fea2875e4f2e3e8a8fee181803e54f7056845`. Published [SDK 2.0.26][package] declares Effect rc.112 and is distinct from source and [tag 9b4ec571…][tag]. OpenCode was not executed. Read [W1 memory](w1-02-memory.md), [parent context](parent-context.md), and only the relevant memory/context section of the [parent draft](../../planning/OPENCODE_V2_INTEGRATION_PLAN.md#memory-retrieval-and-128k256k-context).

**Independently reproduced defect.** Actual LearnService, MemoryRepository and SQLite, with deterministic recall, answer and extraction doubles, produced:

| Mutation interval | Edit result | Delete result |
| --- | --- | --- |
| Answer saved; capture queued; original mutated; capture claimed/committed | Old text gets a new ID; two facts | Old text gets a new ID; one fact; original tombstone survives |
| First capture completed; original mutated; same-chat follow-up; second capture | Same resurrection through historical assistant text | Same resurrection despite suppression of the first answer evidence |

All four assert `current(job) == True` before stale commit. They establish policy defects, not model repetition frequency. Completed-answer references omit memory dependencies; revision pins are volatile; suppression follows existing source keys; historical replay checks citations, not learner dependencies. [Producer][learn], [pins][pins], [suppression/commit][repo], [history][history]

**Recommended minimal contract, not implemented.** Keep OpenCode authoritative for transcripts and SQLite authoritative for learner records. Persist this reference-only receipt; field names are proposed:

```text
CompletedAnswerReceipt v1:
  id; profile_id; runtime_store_id; conversation_id; session_id
  input_id; assistant_message_id; terminal_event_id
  text_part_ordinals[]; serialization="text-array-json-utf8-v1"
  content_sha256; character_count; context_manifest_id; policy_revision; capture_epoch
  scope={kind, retention, visibility, project_id?, grant_revision}
  capture_kind="generated-teaching"; publication_id
Dependency:
  subject={type,id,revision}; input={type,id,revision}
  relation=derived_from|supports|owns|member_of; support_group_id?
```

The manifest includes **every consumed input**, including earlier messages, tool results, summary nodes and memory/source revisions. The host binds references to store/profile/scope; no copied answer text or model-selected authority. Hash the ordered JSON array of selected exact text parts, UTF-8, with pinned serialization. Resolve bodies transiently through `sessions.message.get`; require successful final domain publication, settled tools, assistant completion, normalized `stop`, unchanged digest and eligible saved ordinary-learning scope. Preserve the existing 16,000-character ceiling; reject rather than truncate oversized answers. Stream end alone is insufficient: upstream distinguishes `time.streamed` from `time.completed`. Exclude reasoning, arbitrary tools/children and compaction messages. [Public client][client], [assistant schema][message], [existing resolver][resolver]

Admission and commit both validate the complete dependency closure. Idempotency binds receipt identity and fingerprint; conflicting reuse fails. Persist publication intent/manifest before dispatch; reconcile terminal events after crashes. Missing dependencies fail closed. A single profile coordinator serializes revocation with dispatch/publication; cross-database reads do not become an imaginary shared transaction. Canonical receipt/outbox insertion compares the current retention epoch and exact revisions in one SQLite transaction.

**Decisive proposed retention rules.** These refine C's defaults, not newly confirmed user decisions. [C ownership/retention][retention]

| Operation | Required outcome |
| --- | --- |
| Correct a fact | New canonical revision with explicit user support; revoke old revision and dependent receipts/jobs; exclude old descendants before acknowledging correction. |
| Delete a fact | Tombstone its identity, revoke all support and downstream reuse, purge canonical text/history and derived caches. Saved original chat messages remain labelled historical until chat deletion; excluded text cannot feed model context, capture, zoom, search snippets or children. |
| Multi-source fact | Inputs within one support group are AND; independently valid groups are OR. Remove invalid groups; retain a descendant only with independent surviving support or explicit user ownership. An echo through another answer is not independent support. Direct fact deletion overrides every group. |
| Delete chat | Cancel pending capture; remove transcript/owned attachments and derived summaries; keep separately retained facts with unavailable-source provenance by default. “Delete related learning” revokes that chat's support groups, preserving independently supported/edited facts. |
| Scope | Project conversations capture project-local facts; unassigned learning captures profile-global facts. Recall admits global plus matching-project facts only. Include visibility/project in deduplication. Children inherit an intersection; moving chats never relabels old receipts. Temporary sessions neither read nor write learner memory; explicit promotion creates fresh reviewed eligible input. |
| Project/archive | Archive changes visibility only. Project deletion removes project-owned data, not global/shared items through membership links. |
| Restore | Merge current tombstones, corrections and suppression monotonically before activating either store; reject stale revisions/receipts, rebuild indexes/views, then allow recovery. Never infer ownership from arbitrary `*_id` fields. An old backup alone cannot know later deletions: require the current revocation ledger or quarantine it pending reconciliation. |

Unavailable provenance after chat deletion is not a revoked assertion: separately retained facts remain recallable, while their deleted source cannot supply new extraction. Corrections, fact deletion and evidence invalidation revoke support; file absence alone does not.

A revocation first advances a durable epoch and denies dependent reads/commits; purge/rebuild can follow with explicit pending status. All receipts, transcript-derived context, summary ancestors, saved views and provider checkpoints inherit dependencies. Invalidate the entire node when precise safe spans are unavailable; rebuild from eligible originals. Retain reference-only tombstones/suppression across restart and restore. Unknown legacy lineage is ineligible for automatic recapture; never silently invent an empty dependency set. Existing restore traverses generic reference fields, so typed edges require a scoped change. [Restore implementation][restore]

**Material parent-draft corrections.** Its queued-capture description understates the reproduced second path: even completed capture plus source suppression permits transcript replay. Its compaction-hook recommendation also needs a concrete constraint: upstream `fromHook()` persists the supplied summary **plus independently selected recent text**; the result contract cannot override that recent field. Context sanitization must therefore cover recent text and opaque native checkpoints, not only summary text. [Compaction][compaction], [hook result][hook]

**Next-wave public-seam acceptance; proposed, not executed.** Use the pinned embedded SDK with synthetic model/tool boundaries and public `sessions.prompt/message.get/compact/context/remove` plus the Renulus domain interface. Reproduce both intervals above after reopen; pause at resolve, extraction and commit while correcting/deleting. Assert no stale prompt, zoom result, canonical candidate, summary/recent text or resumed child publication. Repeat with independent/echo support groups, project A/B/global/temporary scopes, project moves and an older two-store restore. Force missing manifests and policy-hook failure: zero dispatch/capture is required, not merely an error log. A hook exception alone is not demonstrated enforcement. [Client][client], [hook failures][failures]

Minimal change boundary: durable receipt/dependency tables and resolver adapter; revision/suppression propagation in MemoryRepository; filtered context/history/checkpoint construction; typed restore reconciliation. Keep Mem0/Qdrant and the agent loop. Whether public hooks can sanitize persisted recent text, selectively purge affected transcript artifacts, and enforce the final dispatch boundary remains unproved; if not, specify a small upstream seam patch before adoption. Later waves own specs/tickets. Optional future providers need the same receipt rules; current defaults remain unchanged.

**Executed checks and replay.** The four-case inline probe exited 0 in 1.99 seconds using managed Python 3.14.4; replay extracted from this memo also passed all four assertions. Citation completeness, fences, whitespace and final newline passed. `git diff --exit-code HEAD -- runtime/renulus/memory runtime/renulus/learn runtime/renulus/storage pyproject.toml` passed. No suites rerun. External socket destinations were denied; temporary synthetic profiles only. Source inspection used unauthenticated public raw URLs and exact registry metadata. No auth/provider call, install, service, private profile or OpenCode runtime execution occurred.

Run from repository root; this loads only the research probe preserved here:

```powershell
@'
from pathlib import Path
p = Path("docs/research/2026-10-10-opencode-integration/w2-01-memory-dependencies.md")
code = p.read_text(encoding="utf-8").split("<!-- replay-start -->\n```python\n", 1)[1].split("\n```", 1)[0]
exec(compile(code, str(p) + ":probe", "exec"))
'@ | & 'C:/Renulus/dev/python/Scripts/python.exe' -B -
```

<!-- replay-start -->
```python
import asyncio, json, socket, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
sys.dont_write_bytecode = True
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "runtime"))
from renulus.contracts import ContextScope, Scope
from renulus.learn.service import LearnService
from renulus.memory.models import ManualFact
from renulus.memory.repository import MemoryRepository
from renulus.services import Services
from renulus.storage import AppPaths, Database

# Permit only asyncio's Windows loopback self-pipe; no external transport.
def network_guard(event, args):
    if event in ("socket.connect", "socket.getaddrinfo"):
        address = args[1] if event == "socket.connect" else args
        if address[0] not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError("External network forbidden")
sys.addaudithook(network_guard)
OLD, NEW = "SYNTHETIC_OLD_LEARNER_POINT", "SYNTHETIC_CORRECTED_POINT"
QUESTION, TOPIC = "Explain the synthetic learning point.", "T20"
SCOPE = ContextScope(kind=Scope.STUDY)

async def scenario(action, interval):
    with tempfile.TemporaryDirectory(prefix="renulus-w2-memory-") as temporary:
        paths = AppPaths.create(Path(temporary) / "profile", ROOT)
        services = Services(paths, Database(paths.database))
        for module in ("learn", "memory"):
            services.db.apply_migration(module + "-w2",
                (ROOT / "runtime/renulus" / module / "schema.sql").read_text())
        repo = MemoryRepository(services)
        original = repo.add(ManualFact(text=OLD, topic_id=TOPIC, scope=SCOPE,
                                      idempotency_key="seed"))["id"]
        class SyntheticProvider:
            calls = []
            async def stream(self, messages, **kwargs):
                self.calls.append(messages)
                assert OLD in kwargs["system"] or any(
                    OLD in m["content"] for m in messages)
                yield OLD
        provider = SyntheticProvider()
        services.registry.update(provider=provider, memory=SimpleNamespace(
            retrieve=lambda *a, **k: {"records": repo.list()},
            notify=lambda: None))
        learn = LearnService(services)

        async def answer(thread_id, key):
            _, run = learn.prepare(QUESTION, SCOPE, thread_id, TOPIC, "direct", key)
            events = [e async for e in learn.answer(
                run, QUESTION, "direct", TOPIC, freshness=False)]
            assert events[-1].type == "completed", events[-1]
            scope = ContextScope(kind=Scope.STUDY, entity_id=run.thread_id)
            evidence = "learn-answer:" + run.id
            payload = json.loads(services.db.fetch_one(
                "SELECT payload_json FROM learning_evidence WHERE id=?",
                (evidence,))["payload_json"])
            assert set(payload) == {"scope", "answer_reference"}
            job = repo.enqueue(evidence, scope)
            return run, scope, evidence, job

        run, scope, evidence, job = await answer(None, "first")
        if interval == "captured":
            claimed = repo.claim(job["id"])
            assert repo.commit_capture(claimed, repo.material(evidence, scope),
                                       [OLD]) == [original]
            assert repo.job(job["id"])["state"] == "completed"
        if action == "edit":
            repo.edit(original, NEW, 1)
        else:
            repo.delete(original, 1)
            assert services.db.is_deleted("memory_fact", original)
        assert not any(r["text"] == OLD for r in repo.list())
        assert services.db.fetch_one(
            "SELECT 1 FROM memory_suppression WHERE source_key='manual:seed'")
        if interval == "captured":
            assert services.db.fetch_one(
                "SELECT 1 FROM memory_suppression WHERE source_key=?",
                ("evidence:" + evidence,))
            run, scope, evidence, job = await answer(run.thread_id, "followup")
            assert any(m["role"] == "assistant" and m["content"] == OLD
                       for m in provider.calls[-1])
        claimed = repo.claim(job["id"])
        assert claimed and repo.current(claimed)
        # Explicit extraction double: tests commit policy, not model probability.
        identifiers = repo.commit_capture(claimed, repo.material(evidence, scope),
                                          [OLD])
        assert len(identifiers) == 1 and identifiers[0] != original
        assert repo.get(identifiers[0])["text"] == OLD
        assert len(repo.list()) == (2 if action == "edit" else 1)
        print(json.dumps(dict(interval=interval, action=action, current=True,
            new_id=True, stale_reentered=True, facts=len(repo.list()),
            original_tombstone=services.db.is_deleted("memory_fact", original))))

async def main():
    for interval in ("queued", "captured"):
        for action in ("edit", "delete"):
            await scenario(action, interval)
asyncio.run(main())
```
<!-- replay-end -->

[learn]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/learn/service.py#L345-L375
[pins]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/learn/memory_context.py
[repo]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/repository.py
[resolver]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/study_answers.py
[history]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/learn/evidence.py#L52-L67
[restore]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/storage/backup.py#L243-L315
[retention]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L110-L143
[package]: https://registry.npmjs.org/@opencode%2Fsdk/2.0.26
[tag]: https://github.com/anomalyco/opencode/tree/9b4ec5714d481559990db0a816d5dec19541a814/packages/sdk
[client]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/client/src/promise/generated/client.ts#L537-L1013
[message]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/schema/src/session-message.ts#L212-L237
[compaction]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/compaction.ts#L594-L656
[hook]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin/src/promise/session.ts#L25-L48
[failures]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin/hooks.ts#L21-L29
