# Review 01 — Hermes embedding and execution

2026-10-10. Renulus `528025ff0b22477c12ee1512e0e7d15297a6e888`; bundled Hermes **B** = `af90026aa09949579bd423d24def3d38f743cde0`; inspected upstream **C** = `dce1e9b37581dd62e480a9064dc04a709c2940d3`. Links below identify immutable files and their raw line ranges. This is source inspection, without runtime execution, installation, inference or private-state reads.

**Conclusion, engineering judgment:** Hermes is a usable headless general-agent foundation with substantial application coupling. If adopted, Renulus should embed the full `AIAgent` execution lifecycle behind a Renulus-owned harness interface, with explicit isolation patches. Its existing converter integration does not provide that harness. This finding does not establish Hermes as the overall winner against Pi or OpenCode, or authorise implementation.

Four verified facts govern that conclusion:

1. **The headless entry point exists at both pins.** `run_agent.AIAgent.__init__` forwards to `agent.agent_init.init_agent`. It accepts explicit `provider`, `api_mode`, `base_url`, `api_key`, `model`, toolsets, session identity/store, callbacks and iteration/time budgets. `max_iterations` defaults to `sys.maxsize`. `run_conversation(user_message, system_message, conversation_history, task_id, stream_callback, …)` is synchronous; its loop issues model calls, runs tools, and continues until a final response or termination. Results include messages, response, API-call count and completion/interruption state. These are built-in interfaces, independent of Electron. C adds a `prelude` parameter to the turn facade, so the pins are not API-identical. Sources: [B constructor][b-ctor], [C constructor][c-ctor], [B turn][b-turn], [C turn][c-turn], [C execution][c-loop], [C result][c-result].

2. **Tools have real registration and execution seams.** `tools.registry.registry.register(name, toolset, schema, handler, …)` supports synchronous and asynchronous handlers; `dispatch` filters injected context arguments and normalises results. The toolset selector treats `None` as all toolsets. The loop's `_execute_tool_calls` selects sequential/concurrent executors and appends results. `model_tools.handle_function_call` supplies task/session/turn/request identities and reaches `registry.dispatch` through middleware. This supports domain tools around Renulus services rather than requiring coding-only actions. Sources: [B registration][b-register], [C dispatch][c-dispatch], [B selection][b-selection], [B execution][b-execution], [C call interface][c-call], [C tool routing][c-routing].

3. **Provider conversion and provider execution are separate.** `ProviderTransport` handles message/tool conversion, request construction and response normalisation; its contract excludes client creation, streaming, credentials and retries. `register_transport` extends wire dialects. `ProviderProfile.create_client(**kwargs)` supplies an actual client through `create_openai_client`. However, a failing custom-client hook is caught and falls through to standard client construction at both pins. Renulus currently constructs `AsyncOpenAI` itself, passes `tools=None` and strips tool definitions; its facade cannot simply become the synchronous agent's client. Sources: [C transport contract][c-format], [B transport registry][b-transports], [C client hook][c-client], [B hook failure][b-client-failure], [C hook failure][c-client-failure], [Renulus integration][r-transport].

4. **Quiet embedding still has application side effects.** B and C import-time code loads Hermes/project dotenv. Constructor setup discovers plugins, creates a sessions directory and installs file logging. `session_db` is optional, but B's session-recall helper can lazily acquire the default Hermes store; the supplied handle follows Hermes methods such as `create_session`, not an arbitrary SQLite connection. Both pins configure three main-call attempts and five post-exhaustion recovery cycles by default. Request clients disable SDK retries, which does not disable the outer loop. Sources: [B dotenv][b-env], [C dotenv][c-env], [B startup][b-startup], [C plugins][c-plugins], [C session setup][c-session], [B logging][b-logging], [B persistence][b-persistence], [B recovery][b-recovery], [C recovery][c-recovery], [B SDK client][b-sdk].

   The dependency boundary also matters: both manifests describe Python 3.14 as supported despite broader compatibility metadata; C declares Windows PTY/Win32 dependencies and moves native `nemo-relay` from B's 0.9 to 0.10. Sources: [B runtime manifest][b-python], [C runtime manifest][c-python], [C Windows dependencies][c-windows], [B Relay][b-relay], [C Relay][c-relay].

**Proposed adoption unit:** retain the pinned agent, turn loop, tool dispatcher, context machinery and lifecycle under Renulus's managed local Python backend. Expose start/stream/interrupt/close through one client-independent harness interface; serialize synchronous turns per session on owned workers and bridge callbacks to backend events. `interrupt` and `close` already supply lifecycle entry points ([B interrupt][b-interrupt], [C cleanup][c-cleanup]). Supply exact approved subscription/model identities, finite budgets and explicitly selected domain toolsets. Reuse the existing authentication ownership, with a synchronous compatible client adapter whose construction errors terminate the request.

The necessary fork boundary should inject owned configuration/tool discovery/logging, avoid inherited dotenv and automatic component acquisition, and enforce one attempt per planned model request across recovery paths. `api_max_retries=1`, `auto_recovery_cycles=0`, empty fallback/pool configuration and disabled background review are starting controls, not proof that every generative retry path is closed. Detailed policy and delegation review belong to other assignments.

Retain Mem0 OSS, Docling/HybridChunker, FastEmbed and LanceDB as reusable domain services exposed through tools. Keep canonical source, learner and assessment authority in Renulus SQLite; keep operational transcripts and derived indexes distinct. Any Hermes session-store adapter must preserve saved-by-default/temporary/Archive semantics. B is a concrete compatibility baseline for an isolation proof: [Renulus imports its private Mem0 adapter][r-memory], while [C's catalogue targets an external integration][c-mem0]. These interface changes do not justify adopting C wholesale. The benefit is reuse alongside Python domain services; the tradeoff is ownership of an embedding fork and its larger dependency set.

**Uncertainty and reversal evidence:** source contracts do not prove exact-model tool calling, Windows cancellation, concurrent session isolation, clean shutdown or educational quality. Later authorised synthetic embedding checks should verify lifecycle/isolation and record attempted model calls; exact subscription tool calling needs separate authorised live evidence. Evidence that isolation requires pervasive patches, that the approved routes cannot carry tools, or that Windows packaging cannot support the full dependency set would weaken this recommendation. A maintained upstream embedding interface with injected clients/configuration/tool catalogues and terminal failure semantics would strengthen it.

[b-ctor]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/run_agent.py#L263-L312
[c-ctor]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/run_agent.py#L236-L286
[b-turn]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/turn_facade.py#L22-L33
[c-turn]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/turn_facade.py#L22-L34
[c-loop]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/conversation_loop.py#L1650-L1706
[c-result]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/turn_finalizer.py#L684-L710
[b-register]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/registry.py#L666-L691
[c-dispatch]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/tools/registry.py#L893-L921
[b-selection]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/model_tools.py#L315-L341
[b-execution]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/run_agent.py#L1330-L1353
[c-call]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/model_tools.py#L872-L885
[c-routing]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/model_tools.py#L822-L845
[c-format]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/transports/base.py#L1-L41
[b-transports]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/transports/__init__.py#L21-L56
[c-client]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/providers/base.py#L326-L349
[b-client-failure]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/agent_runtime_helpers.py#L1928-L1957
[c-client-failure]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/agent_runtime_helpers.py#L1893-L1922
[r-transport]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L80-L153
[b-env]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/run_agent.py#L118-L127
[c-env]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/run_agent.py#L91-L100
[b-startup]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/agent_init.py#L2490-L2516
[c-plugins]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/agent_init.py#L1093-L1124
[c-session]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/agent_init.py#L1182-L1207
[b-logging]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/agent_init.py#L711-L725
[b-persistence]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/run_agent.py#L314-L378
[b-recovery]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/agent_init.py#L1465-L1476
[c-recovery]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/agent_init.py#L1434-L1445
[b-sdk]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/client_lifecycle.py#L442-L464
[b-python]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/pyproject.toml#L5-L58
[c-python]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/pyproject.toml#L5-L58
[c-windows]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/pyproject.toml#L150-L201
[b-relay]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/pyproject.toml#L202-L216
[c-relay]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/pyproject.toml#L202-L216
[c-mem0]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/plugin-catalog/mem0.yaml#L1-L11
[r-memory]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/engine.py#L67-L82
[b-interrupt]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/interrupt_control.py#L115-L124
[c-cleanup]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/run_agent.py#L920-L953

Handoff: `docs/research/2026-10-10-harness-adoption/review-01-hermes-runtime.md`. Conclusion: conditionally adopt the full headless runtime behind a controlled boundary. Strongest fact: both pins expose the actual model→tool→result loop, but the current Renulus facade disables tools. Unresolved risk: containing implicit discovery, provider-client fallthrough and recovery while retaining exact subscription routing.
