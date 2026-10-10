# Review 24 — Challenge the preference for Hermes

2026-10-10. Research only, without execution or inference. Reviewed memos 01–20, including completed [review20](review-20-clients-workspaces-and-harness-interface.md); preferences were not counted as evidence. Primary files were reread at Renulus `528025ff`, bundled Hermes **B** `af90026a`, inspected Hermes **C** `dce1e9b3`, Pi **1.1.0** `abe508e1`, and OpenCode **v2/2.0.26** `55dde881`. References below contain full immutable revisions and raw-file line ranges.

**Conclusion — judgment:** Hermes remains a conditional candidate, but existing adoption, Python proximity and feature breadth do not establish the best execution owner. **Pi agent-core behind a Renulus-owned host is the strongest control-focused alternative.** OpenCode v2 is stronger when an integrated client/execution boundary is decisive and its recovery policy can be contained. A Hermes recommendation would be wrong if its full loop fails the acceptance conditions below while either alternative passes. This research selects no replacement and authorises no implementation.

Five load-bearing verified facts:

1. **Existing integration does not prove full-loop route control.** Renulus passes no tools, strips their declarations and sets SDK retries to zero [R1]. Hermes C catches a custom-client construction exception and falls through to standard client construction [H1]. Its compressor can immediately fall back from a distinct summary model to the main model **after access/quota failure** [H2]. A policy client or parent model selection alone therefore cannot enforce the retained rejection rule.

2. **Embedding imports ambient application behavior.** Hermes C loads dotenv at import, discovers plugins during tool setup and creates its sessions directory unconditionally [H3][H4][H4s]. Initialization defaults to three outer attempts and five transient recovery cycles [H4d]. Its registry combines process-global registrations with profile overlays [H5]; overlays deserve credit but are not run capabilities. B/C turn signatures differ: C adds optional `prelude` [H6][H7]. Stock terminal execution requires Bash, with staged Git-for-Windows support [H8][H9]. This establishes adaptation and dependency-closure obligations, not Windows impossibility or a demonstrated breaking SDK change.

3. **Tool and cancellation policy need domain enforcement.** A pre-tool-hook exception is logged without blocking [H10]. Narrowed children can inherit additional parent MCP toolsets; orchestrators regain delegation [H11]. Accepted async children detach from parent cancellation, while a separate session-scoped interrupt exists [H12][H13]. Advertised tools, a read-only prompt and parent Stop are insufficient substitutes for explicit execution authority and child ownership.

4. **Pi supplies a real injected seam and a separate durability candidate.** Agent options accept `streamFn`, initial state and tool hooks [P1]. Separately, pi-durable commits tool intent and permits interrupted-tool replay only when recorded/current policies both say safe [P2]. Its experimental API and checkpointed generation resend require explicit integration/recovery policy [P3][P4]. This is more than transcript persistence, but not assumed wiring into stock AgentSession. Its write union lacks conversation/entry deletion; rewindable retirement retains content, leaving purge/migration unverified [P5][P6].

5. **OpenCode v2 is a substantive alternative, not merely a CLI.** The embedded host exposes owned in-process fetch, sessions and close, but starts suspended-session recovery; recovery explicitly permits repeated effects [O1][O2]. Published `@opencode/sdk@2.0.26` uses Effect rc.112 without gitHead, whereas the inspected source uses rc.118; default CLI 1.18.35 is a separate artifact [D1][D2][D3]. Publication cannot establish source/package equivalence.

**Proposed adoption boundary:** retain Library evidence/revisions/rights, learner facts/suppression, Chat/Cases retention, Study/Test, reviewed keys/exposure and generated drafts in Renulus domain modules. Pure policy/scoring stays in process with its owner; SQLite/files and managed CPU engines are local-substitutable dependencies. Preserve Mem0 OSS, Docling/HybridChunker, FastEmbed and LanceDB. The existing attributed Mem0 backend is a direct reusable source unit, not a reason to select its agent loop [R2]. Owned Python IPC needs a typed port with production/test adapters; selected generation providers are true external dependencies behind injected transport.

For Pi, directly import agent-core and supply controlled children through one execution owner. Consider pi-durable **instead of** that coordinator, subject to its gates; initially borrowing replay/ownership patterns does not mean importing a second loop. Pi adds bridge/coordinator work. Hermes preserves direct Python calls but owns more isolation patches. Borrow OpenCode's shared-router pattern and Hermes's session/child lifecycle without adopting their defaults wholesale.

**Falsifiable acceptance conditions — proposed future proofs:**

- **Routes:** scripted parent, child, summary, memory and repair calls retain the selected subscription and exact allowlist (Codex: `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6-luna`; Go: `mimo-v2.6-pro`, `deepseek-v4.1-flash`) [R0]. Authentication/quota/model/image rejection produces one attempted request and visible failure; broker/client construction failure produces zero outbound requests. No automatic fallback, warming, retries or generation replay in the conservative proof.
- **Isolation/authority:** interleave two synthetic profiles and tool-catalogue refresh. No ambient discovery or writes outside owned paths; rejected direct, child and MCP calls execute nothing, including when approval hooks throw. Final child grants remain subsets. Renulus adapter contracts must pass at every pinned upstream update.
- **Ownership/recovery:** one owner serves clients; detaching only unsubscribes. Barrier-controlled cancellation stops admission and all owned work; settled means cleanup finished. DC16 preserves validated batches after cancellation/restart with zero automatically restarted billed/model work and reports the actual publication/cancellation winner [R3]. Replay of safe deterministic work remains separately classified.
- **Records/Windows:** demonstrate canonical receipts/outbox reconciliation across stores, stale-worker fences, temporary/saved/Archive semantics, purge and restore. Transcripts/documents remain operational; SQLite/originals remain canonical. Headless Windows startup/reopen must work with developer tools absent, managed dependencies and no doctor-installed runtime, GPU, Docker or generative server.

The October 6 rule specifically covers authentication/quota/model/image rejection [R4]; general transient-network/restart policy remains unresolved. The broader retry-disabled proof baseline is conservative, while DC16 is an explicit job-specific contract. Saved-by-default migration remains incomplete [R5]. No source inspection proves approved-model tool calling, Windows settlement or educational quality across nephrology. Passing controlled full-loop proofs with a bounded, maintainable Hermes adapter would reverse this challenge; ungateable Pi recovery or purge would weaken the counterproposal.

**Handoff:** memo `docs/research/2026-10-10-harness-adoption/review-24-challenge-hermes-preference.md`; conclusion: conditional Hermes, Pi is the strongest control counterproposal; strongest fact: Hermes summary fallback includes access/quota failures; unresolved risk: enforcing one generation/ownership policy across auxiliary calls and detached children.

[R0]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/policy.py#L10-L13
[R1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L65-L113
[R2]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/engine.py#L67-L82
[R3]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678-L695
[R4]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[R5]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L23
[H1]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/agent_runtime_helpers.py#L1893-L1922
[H2]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/context_compressor.py#L4301-L4325
[H3]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/run_agent.py#L91-L100
[H4]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/agent_init.py#L1093-L1124
[H4s]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/agent_init.py#L1182-L1207
[H4d]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/agent_init.py#L1434-L1445
[H5]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/tools/registry.py#L427-L465
[H6]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/turn_facade.py#L22-L32
[H7]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/turn_facade.py#L22-L33
[H8]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/tools/environments/local.py#L514-L527
[H9]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/pm/shell.py#L1-L21
[H10]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/model_tools.py#L778-L800
[H11]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/tools/delegate_tool_toolsets.py#L78-L124
[H12]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/tools/delegate_tool_dispatch.py#L439-L453
[H13]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/tools/async_delegation.py#L1184-L1191
[P1]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent.ts#L113-L139
[P2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L85-L110
[P3]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L1-L7
[P4]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/generation.ts#L184-L209
[P5]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts#L708-L724
[P6]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/storage/sqlite/storage.ts#L914-L928
[O1]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/internal/host.ts#L30-L68
[O2]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution/restart.ts#L46-L61
[D1]: https://registry.npmjs.org/@opencode%2Fsdk/2.0.26
[D2]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/package.json#L81-L85
[D3]: https://registry.npmjs.org/opencode-ai/latest

