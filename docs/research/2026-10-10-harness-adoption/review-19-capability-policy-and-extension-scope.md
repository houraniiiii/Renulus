# Review 19 — capability policy and extension scope

October 10, 2026. Source inspection only; no runtime tests or adoption changes. Raw line ranges below were checked against Renulus `528025ff0b22477c12ee1512e0e7d15297a6e888`, bundled Hermes `af90026aa09949579bd423d24def3d38f743cde0`, upstream Hermes `dce1e9b37581dd62e480a9064dc04a709c2940d3`, Pi 1.1.0 `abe508e1b89912adde45528136c3221eb69acdd7` and OpenCode v2 `55dde8810d8a859c0a21e42491ae7d5801fb49ef`. OpenCode findings concern this source snapshot, not default v1 CLI behavior or equivalence to the published v2 SDK artifact.

**Conclusion — judgment.** OpenCode v2 offers the strongest reusable permission broker for this question. Borrow its action/resource requests, explicit rejection and approval transport; Pi offers useful host-controlled tools and interception, while Hermes offers command guards and child-tool filtering. This does not select a complete foundation. Renulus must own an independent authority check at each domain service: permission to read a path or invoke a tool cannot establish permission to embed its contents, disclose them to a model, retain them or mutate canonical records.

**Four verified facts.**

1. **Renulus already has narrower domain controls.** Rights default to false per operation; import requires display/cache and, ordinarily, index/embedding rights. Retrieval checks model-input rights, source status and scope. Case scopes are excluded from learner-memory processing. The generation adapter supplies no tools, validates exact model identity and sets SDK retries to zero. These are reusable assets, rather than permissions furnished by Hermes's general agent loop. [R1] [R2] [R3] [R4] [R8]

2. **OpenCode has enforcement and broad defaults together.** Its broker uses the last matching action/resource rule, defaults to ask, checks configured denial before saved grants, and persists “always” approvals by project. Shell execution explicitly asserts parsed command permissions. However, Explore's prompt forbids writes while its rules allow every shell resource and external directory. Tool metadata filters declaration visibility; the execution adapter calls the registered implementation. A custom adapter must actually enforce authorization. This broker is an application gate, not evidence of an operating-system sandbox. [O1] [O2] [O3] [O4] [O5] [O6] [O7]

3. **Pi's modern hooks are useful, but extensions remain trusted code.** AgentSession installs tool hooks; agent-core can block before execution, including nested calls through its tool pipeline. Built-in MCP calls, including codemode calls, traverse that pipeline. Server annotations such as `readOnlyHint` are declared hints used by permission extensions. SDK hosts can explicitly choose tools/resources; they must add CLI MCP factories themselves. Pi documents that extensions execute in-process with the user's permissions and project trust does not constrain tool access. Thus hooks can govern cooperating adapters, not contain arbitrary extensions. [P1] [P2] [P3] [P4] [P6] [P7] [P8]

4. **Hermes guards are not universal source policy.** At the bundled pin, command approval applies hard floors before bypasses, but unattended execution otherwise permits calls unless an applicable configured deny mode intervenes. Registry dispatch invokes the handler. Child toolsets intersect requested tools with the parent's, with important exceptions: optional MCP inheritance appends parent MCP toolsets to a narrowed child, and the orchestrator role re-adds delegation. The inspected upstream retains these exceptions. Reuse the filters and approval transport, but do not mistake toolset membership for source/retention authorization. [H1] [H2] [H3] [H4]

**Practical narrow defaults — proposals.**

- **Retrieval:** expose document/revision/passage identifiers through Renulus services, with rights, currentness, excluded-page and deletion checks before results enter model context. Keep display, cache, embedding, model input, derivation, evaluation and redistribution independent. Approved literature connections get explicit endpoints, operation and usage bounds; a user-supplied retrieval key never authorizes another generation route. Filesystem read, generic web fetch and MCP resource access are too broad substitutes for this contract. [R1] [R2] [R5]
- **Execution/extensions:** ship reviewed extensions and named, bounded CPU helper operations. Omit generic shell, arbitrary code execution, skill installation and unrestricted MCP by default. Skills supply instructions; capability names, schemas and read-only/idempotent hints are metadata. Enforce policy in the service implementation even after a wrapper approves. Untrusted executable plugins require a separately proved Windows process/files/network boundary; do not introduce doctor-managed Docker or local generative servers as an assumed solution.
- **Scope/delegation:** the host derives scope from canonical input and grants children a subset of operations, source IDs, provider route and retention permissions. Model arguments cannot self-declare source rights or promote temporary input. Temporary conversations exclude durable transcripts, helper caches, learner-memory capture and background jobs containing their payload. Saved-by-default conversations remain the confirmed target, with migration incomplete; saving does not erase separate Library/memory eligibility checks. [R2] [R3] [R6]
- **Canonical changes/routes:** expose typed draft, validate, publish, edit and delete commands with expected revisions and idempotency receipts. Keep SQLite/originals authoritative; retain Mem0 OSS, Docling/HybridChunker, FastEmbed and LanceDB as bounded processing/index assets. Give neither plugins nor subagents raw database/original-file write access. Check every generative request, including helper/compaction/subagent work, against the selected subscription and exact approved five-model list; preserve visible authentication/quota/model/image rejection without automatic retry or fallback. [R4] [R6] [R9]

**Recovery is scope-specific.** DC16 requires temporary inputs to stay out of durable generated-test jobs except its validated fictional transition or explicitly saved context. It also preserves validated work after cancellation/restart without automatically restarting billed/model work. Propose replay only for safe deterministic validation/publication with fresh rights/deletion checks and receipts. General transient-network/restart policy remains unresolved. Pi's separate durable library is a real adoption candidate; its internal atomic commits do not establish atomicity with Renulus's separate stores. Require outbox/receipt reconciliation and a verified purge contract. [R7] [P5]

**Uncertainty and changing evidence.** No Windows containment, malicious-extension, scope-revocation or restart behavior was tested. A synthetic proof that every direct, nested MCP and child call rechecks rights/routes, revoked sources remain inaccessible, temporary payloads leave no durable copies, and DC16 never automatically replays generation would strengthen adoption. Demonstrated bypasses or unavailable Windows containment would favor a narrower embedded tool surface regardless of foundation.

**Handoff:** `docs/research/2026-10-10-harness-adoption/review-19-capability-policy-and-extension-scope.md`. Conclusion: reuse OpenCode's broker; retain host-owned domain authority. Strongest fact: Explore permits all shell resources despite its no-write prompt. Unresolved risk: executable extensions can bypass cooperating tool wrappers.

Primary sources (immutable GitHub files; anchors are raw, one-based line ranges):

[R1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/models.py#L6-L21
[R2]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L202-L210
[R3]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/models.py#L10-L18
[R4]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L65-L113
[R5]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/SOURCES.md#L181-L200
[R6]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L23-L54
[R7]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678-L695
[R8]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L509-L550
[R9]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[O1]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/permission.ts#L87-L188
[O2]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/permission.ts#L231-L320
[O3]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin/agent.ts#L98-L117
[O4]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool/plugin/shell.ts#L117-L145
[O5]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool.ts#L225-L238
[O7]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin/agent.ts#L7-L17
[O6]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool/runtime.ts#L29-L45
[P1]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/security.md#L3-L33
[P2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sdk.md#L98-L116
[P3]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/mcp.md#L250-L272
[P4]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent-loop.ts#L725-L755
[P5]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L78-L113
[P6]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L652-L674
[P7]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent-loop.ts#L802-L818
[P8]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/security.md#L88-L99
[H1]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/approval.py#L1168-L1233
[H2]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/registry.py#L893-L910
[H3]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/delegate_tool_toolsets.py#L80-L123
[H4]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/tools/delegate_tool_toolsets.py#L85-L124
