**Review 21 — Strongest Hermes-first harness design**

October 10, 2026. Research/design only; no execution or adoption changes. Reviews 01–20 supplied leads, including review20's OpenCode preference on the client/execution seam. Decisive claims below were checked against primary files. Pins: Renulus `528025ff0b22477c12ee1512e0e7d15297a6e888`; Hermes bundled **B** `af90026aa09949579bd423d24def3d38f743cde0` and inspected **C** `dce1e9b37581dd62e480a9064dc04a709c2940d3`; Pi 1.1.0 `abe508e1b89912adde45528136c3221eb69acdd7`; OpenCode v2 source 2.0.26 `55dde8810d8a859c0a21e42491ae7d5801fb49ef`. Links identify immutable files and raw, one-based ranges.

**Conclusion — judgment:** the strongest Hermes contender is a deep `RenulusHarness` module with one execution owner per learner profile, embedding B's agent loop beside existing Python domain modules. Its advantage is reuse of execution, context and domain code with fewer serialization seams. Choose it only if explicit client/configuration/tool injection can contain its ambient behavior with maintainable patches. Prior selection does not establish that advantage or authorize implementation.

**Five verified facts shape the design.**

1. B's `AIAgent` constructor accepts route, toolsets, callbacks, session storage and budgets; `run_conversation` is synchronous. `interrupt` requests cancellation and `close` releases resources. C adds `prelude` to the turn interface: retain B for the compatibility proof. [H1][H2][H3][H4][HC]
2. `registry.register(name, toolset, schema, handler, …)` and `registry.dispatch` support domain handlers. Dispatch calls handlers without validating their argument schema. Stock child construction inherits toolsets; its narrowing helper can append MCP tools and restore delegation. [HT][HD][HB][HS]
3. Hermes defaults to three main-call attempts and five recovery cycles. Its failing custom-client hook falls through to standard construction at B and C. Provider transports own conversion, excluding credentials/retries. Host injection needs enforcement beyond constructor flags. [HR][HF][HFC][HW]
4. Renulus already rechecks Library rights/revisions against SQLite after index search and commits reviewed answers transactionally. Its present generation adapter strips tools and disables SDK retries; today's integration is not the proposed full harness. [RL][RA][RG]
5. DC16 explicitly preserves validated generated-test work after cancellation/restart without automatically restarting billed/model work. The dated general rejection rule addresses authentication, quota, model and image errors; general transient-network/restart policy remains unresolved. [DC][RP]

**Proposed interface, not implemented:**

	type Start = {
	  requestId: string; conversationId: string; contextRef: string;
	  workflowRef: string; inputRef: string;
	  replyTo?: string; retryOf?: string;
	};
	type Admission = { runId: string; attemptId: string };
	type Event = {
	  seq: number; runId: string; attemptId: string; childId?: string;
	  kind: "snapshot" | "text" | "tool" | "input_needed" | "artifact" | "settled";
	  payload: JsonValue;
	};
	interface RenulusHarness {
	  start(request: Start): Promise<Admission>;
	  events(runId: string, afterSeq?: number): AsyncIterable<Event>;
	  cancel(runId: string): Promise<{ accepted: boolean }>;
	}

Usage:

	const run = await harness.start({ requestId: "synthetic-1",
	  conversationId: chat.id, contextRef: chat.contextRef,
	  workflowRef: "explain", inputRef: dialysisQuestion.id });
	stopSignal.addEventListener("abort", () => void harness.cancel(run.runId));
	for await (const event of harness.events(run.runId)) present(event);

Workflow/context references resolve through authenticated host policy. Matching request ID/digest replays admission; conflicts fail. Reject busy turns explicitly. Clarification replies target a pending input; explicit generation Retry references the interrupted run and creates an attempt. Event attachment never generates; detachment never cancels. Cancellation acknowledgment precedes settled outcome. Include snapshots, cursor-gap resync and artifact manifests; coalesce text deltas. Domain commands retain Archive, deletion and reviewed-Test operations.

**Hidden implementation and adapters — proposals.** Own receipts, ordered events, parent/child ownership, budgets, cancellation fences and cleanup. Run synchronous Hermes turns on owned workers, serialize each conversation, freeze vetted extension definitions and enforce capabilities inside every handler. Construct fresh child `AIAgent`s with narrower grants and shared root budgets; contain stock delegation's ambient defaults. Retain a single profile writer and client-independent bootstrap; desktop/CLI are local clients. Require no hosted inference, doctor-managed GPU/Docker/generative server or mandatory paid generation API.

| Dependency | Seam and adapters |
| --- | --- |
| Pure policies/scoring | In-process code; exercise through the harness/domain interfaces. |
| SQLite/files; managed CPU engines | Local-substitutable adapters: real isolated SQLite/files plus deterministic engine stand-ins. |
| Owned Python IPC | Typed `HarnessPort`; authenticated local production adapter and in-memory test adapter. |
| Selected generation providers | Injected private `GenerationPort`; subscription transport and scripted test adapter. |

Direct imports reuse `AIAgent.run_conversation/interrupt/close`, registry registration/dispatch, `ResponsesApiTransport.build_kwargs`, `ChatCompletionsTransport.build_kwargs` and `ContextCompressor.should_compress/compress` through Renulus's controlled summary adapter. [H1][H2][H3][H4][HT][HD][TX][TC][CC][RC] Inject owned paths/discovery/logging before agent startup; retain licences and patch provenance. A synchronous client adapter must replace today’s async generation path. Make client-construction failure terminal; govern parents, children, summaries and Mem0 extraction through the same broker. Keep selected Codex `gpt-6.1-sol`/`gpt-6-astra`/`gpt-6-luna` or Go `mimo-v2.6-pro`/`deepseek-v4.1-flash` routes, visible rejections, SDK retries disabled and conservative proof recovery gated. [RP][RG][RO]

Library evidence/revisions/rights, learner facts/suppression, Chat/Cases retention, Study/Test, reviewed keys/exposure and generated draft artifacts stay canonical in Renulus SQLite/originals. Reuse Mem0 OSS/local Qdrant, Docling HybridChunker, FastEmbed and LanceDB; indexes/transcripts remain derived or operational. Saved-default/Archive migration is incomplete. Temporary payloads and child derivatives need volatile handling. Revision fences and receipts/outbox reconciliation connect separate stores; do not assume shared atomicity. Preserve DC16 checkpoints; replay safe deterministic work under fresh checks. Workers cannot disclose reviewed keys or publish scores. [RL][RA][RS][DC]

**Borrow patterns, without importing competing runtimes:** Pi separates model `content` from client details; its real, separate experimental durable library supplies admission reconciliation and conservative tool replay, not assumed AgentSession integration. Borrow those contracts. OpenCode supplies write-ahead execution claims, accepted-versus-settled interruption and route checkpoint provenance. Translate these into the Python owner's ledger; neither supplies Renulus purge semantics automatically. [P1][P2][P3][P4][O1][O2][O3]

**Disqualifying evidence:** pervasive patches to catch auxiliary generation, unavoidable ambient profile/tool access, failed approved-model tool continuation or orphaned Windows workers would defeat this contender. A synthetic proof covering duplicate admission, concurrent parents, stop/publication races, deletion/rebuild and DC16 restart—with recorded request counts—would strengthen it. Exact-model live tool support and the full Windows dependency closure remain unproved. Educational quality across nephrology requires separate evidence.

[H1]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/run_agent.py#L263-L312
[H2]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/turn_facade.py#L22-L33
[H3]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/interrupt_control.py#L115-L124
[H4]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/run_agent.py#L969-L988
[HC]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/turn_facade.py#L22-L34
[HT]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/registry.py#L666-L691
[HD]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/registry.py#L875-L921
[HS]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/delegate_tool_toolsets.py#L77-L123
[HR]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/agent_init.py#L1465-L1476
[HF]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/agent_runtime_helpers.py#L1928-L1957
[HFC]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/agent_runtime_helpers.py#L1893-L1922
[HW]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/transports/base.py#L1-L41
[RL]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L509-L592
[RA]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/repository.py#L251-L303
[RG]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L66-L143
[RC]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/context.py#L53-L105
[RO]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/policy.py#L11-L22
[RS]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L23-L54
[RP]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[DC]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678-L695
[P1]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/types.ts#L424-L440
[P2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/submissions.ts#L149-L175
[P3]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L85-L116
[P4]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L1-L7
[O1]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution.ts#L26-L42
[O2]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/provider-context.ts#L18-L54

[HB]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/delegate_tool.py#L417-L427
[TX]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/transports/codex.py#L653-L684
[TC]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/transports/chat_completions.py#L473-L506
[CC]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/context_compressor.py#L5656-L5675
[O3]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution.ts#L76-L85

Handoff: `docs/research/2026-10-10-harness-adoption/review-21-hermes-first-design.md`; conclusion: conditional Hermes kernel inside a Renulus-owned deep module; strongest fact: existing headless agent and registry permit direct Python execution reuse; unresolved risk: containing every generation/delegation path without an extensive fork.

