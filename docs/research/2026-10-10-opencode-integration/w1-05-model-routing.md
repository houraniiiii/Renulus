**Wave 1–05 — model routing for the selected embedded OpenCode harness**

2026-10-10. Research/testing only; no product changes. Renulus source baseline: `528025ff0b22477c12ee1512e0e7d15297a6e888` (detached HEAD). OpenCode source: `4b6fea2875e4f2e3e8a8fee181803e54f7056845`. The published `@opencode/sdk@2.0.26` declares matching OpenCode packages and Effect `4.0.0-rc.112`; its tag is `9b4ec5714d481559990db0a816d5dec19541a814`, a distinct artifact. Registry metadata and pinned source were inspected; the package was not installed or executed. [SDK metadata][sdk-package], [source package][sdk-source]

**Recommendation:** reuse OpenCode’s model registry, resolver and request preparation, adding one mandatory Renulus dispatch policy shared by interactive and background work. Configuring the primary agent alone is insufficient. Preserve current subscription defaults; treat future optional providers as separately enabled connections. The findings below distinguish **observed source**, **executed isolated checks**, and **proposals**.

**Current Renulus policy, observed.** The exact routes are:

| Connection | Allowed wire model IDs | Current transport/auth |
| --- | --- | --- |
| Codex | `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6-luna` | Responses at `https://api.openai.com/v1`; Renulus-owned plan OAuth. |
| OpenCode Go | `mimo-v2.6-pro`, `deepseek-v4.1-flash` | Chat Completions at `https://opencode.ai/zen/go/v1`; explicitly supplied subscription key. |

The auth source requires `resource.invoke` and `chatgpt.tokens.use.direct`; inspecting it did not authenticate an account. The Go documentation confirms both selected IDs’ Chat Completions endpoint and requires a client identity and stable conversation header. These are protocol facts, not account-entitlement evidence. [Allowlist/endpoints][r-policy], [auth][r-auth], [transport][r-transport], [Go documentation][go]

`_route()` preserves explicit/saved choices even when absent from the catalogue. Automatic chooses the first allowlisted catalogue match, otherwise the first allowlisted ID. A known rejected choice fails without trying another. This is ordered selection, not capability-aware role routing. `purpose` is a free string; it labels events and distinguishes compaction recursion, but does not select the model. The UI supplies one default model per subscription. [Manager][r-manager], [request schema][r-api], [Connections][r-ui]

Current capabilities are incomplete: connected accounts are labelled available unless rejected; Codex text/image defaults come from a source constant, while Go starts unknown. Only known image rejection blocks submission. Tools, JSON-schema behavior and verified model windows are not represented. The 32,768-token context budget is explicitly an application limit, not a verified model capacity. This audit makes no new capacity or vision claims. [Capability status][r-capability], [image admission][r-image], [context budget][r-context]

**Confirmed acceptance gap from the parent’s runtime report:** after an inference 401, `test_inference_auth_failure_invalidates_catalogue_without_image_claim` expects both availability and image input to become unknown. Source clears the catalogue/observations but retains the connection, allowing status to return available and documented capability defaults. Preserve this failing expectation in migration acceptance; do not equate stored credentials with usable access. [401 handling][r-401], [capability status][r-capability]

**Call-surface audit, observed source.**

| Surface | Actual path and routing consequence |
| --- | --- |
| Primary learning/case turn | OpenCode runner prepares `primary`, then calls `LLMClient.stream`. Explicit session model resolution checks catalogue availability. Renulus’s existing transport strips tools and rejects automation, so it cannot become the full harness transport unchanged. [Runner][o-runner], [step][o-step], [resolution][o-resolution], [Renulus transport][r-transport] |
| Child | Subagent creation selects explicit tool-input model, then agent model, then parent model. Continuing a child can switch its model. Every child needs route admission; parent configuration does not prohibit overrides. [Subagent][o-child] |
| Title | Uses title-agent model or `Model.small(primary.providerID)`, then primary. On an unsuccessful first attempt, it can try the primary again. Small-model selection uses family preferences, not Renulus role evidence. [Title selection][o-context], [title attempts][o-title], [small selector][o-model] |
| Compaction | Can select a compaction-agent model; supports summary streaming and native `LLMClient.compact`. Summary-template repair sends another request; overflow shrinking has its own loop. Neither is fully controlled by disabling ordinary runner retries. [Compaction][o-compact] |
| General session generation | `SessionGenerate.generate` resolves the session model and calls `LLMClient.generate` after the `generate` hook. Any future domain summary using this API is another policy entry. [Generate][o-generate] |
| Memory extraction | Renulus’s Mem0 `ApprovedLLM` calls the shared provider with `memory-extraction`, refuses tools and validates returned JSON. Preserve this seam; do not introduce a separate Mem0 provider key or silent repair model. [Memory adapter][r-memory] |
| Test summaries | Reviewed scores/progress are deterministic repository operations. Generated practice separately calls the provider with `generated-practice`. There is no demonstrated existing LLM test-summary route. [Assessment][r-assessment], [practice][r-practice] |
| Updates | Source checks hash publication links, literature refresh imports metadata, and review accepts supplied summaries. An LLM digest is a future route, not an existing necessary model call. [Checks][r-updates], [literature][r-literature] |

Additional routing hazards matter more than another model-selection abstraction:

- Request hooks can change base URL/headers; catalogue ID can differ from wire `modelID`. Check the final deployment and serialized identity, not only the menu selection. Unsupported media can become explanatory text during preparation; reject incompatible required input before that substitution. [Request preparation][o-request], [resolver][o-resolver]
- The ChatGPT plugin uses a broader fallback catalogue than Renulus and forces summary compaction. Integration discovery includes environment credentials. Isolate app connections and explicitly map Renulus `codex` to the intended OpenCode provider/auth method. Do not inherit ambient OpenCode/Console credentials or mistake another OpenAI route for the selected subscription. [ChatGPT plugin][o-chatgpt], [integration discovery][o-integration]
- Runner retry permits up to ten retries; WebSocket paths can fall back to HTTP; restart recovery resumes suspended work. Preserve the existing visible-rejection policy. At the newer source, host plugins register before recovery; the 2.0.26 tagged Promise entry registers them after host creation. This is an inspected ordering difference, not an executed escape. [Retry][o-retry], [transport][o-transport], [restart][o-restart], [new host][o-host], [tag host][tag-host], [tag Promise][tag-promise]

**Proposed minimum role policy.** Resolve a trusted purpose to a route once per operation; record connection identity/revision, exact model ID, protocol, endpoint, capability evidence, attempt allowance and parent/run identity. Revalidate before dispatch and after reconnect/recovery. Purpose must come from the owning domain operation, not arbitrary renderer text. Initially, roles inherit the selected model; do not invent “cheap title” or “strong clinical” rankings from model names.

| Purpose | Required capability and constrained behavior |
| --- | --- |
| Explain/case, child | Text/streaming; tool round-trip support when tools are exposed; image support only when actual image content is required. Children inherit the connection and permitted model set. |
| Title, compaction | Text with explicit output budgets and no tools. Prefer deterministic title when unavailable. Compaction failure preserves input and pauses; it does not change provider. |
| Memory extraction, generated practice | Validated structured output and bounded response size. Schema-constrained generation requires separate evidence from ordinary text/JSON parsing. |
| Test summary, Updates digest, daily suggestions | Only newly requested/generated explanations need a model. Keep authoritative scores, source-change detection and review decisions deterministic. Daily suggestions are already a Design C planned model consumer. [Design C][r-design] |

Capabilities should distinguish unknown, documented, observed working and observed rejected, scoped to connection/model/deployment/version. Include modality/MIME, tool calls/results, structured output, streaming/cancellation, input/output budget and protocol statefulness. Catalogue presence alone proves none of these. Automatic selection should exclude unmet requirements; manual use of an unknown capability needs explicit verification, not silent input removal.

**Fallback classes, proposal:** (1) initial Automatic selection within the selected connection; (2) deterministic degradation such as retaining a title or numerical score; (3) same-route retry/continuation after transport failure; (4) model, endpoint or connection substitution. Only the first two are initial defaults. Keep authentication, quota, model and input rejection terminal; offer explicit retry/reconnection. Additional generation attempts, summary repair, transport replay and restart resend require a separately adopted policy and an attempt record. Cross-subscription or optional-provider substitution is never an implicit recovery ladder. [Existing rejection decision][r-decision]

**Future opt-in extensibility.** The user’s newer direction permits optional vLLM, Ollama and other providers without changing current defaults or requiring doctors to install inference software. Add connection descriptors behind the same policy rather than replacing the two-provider list with unrestricted URLs. A descriptor needs explicit consent, exact endpoint/model aliases, credential reference, protocol adapter and deployment-specific capability evidence.

Public protocols are not interchangeable capability promises. vLLM documents Chat Completions and Responses, with chat-template requirements and model-dependent tool behavior. Ollama documents an OpenAI-compatible subset, non-stateful Responses, and deployment-configured context size. Do not forward OpenAI continuation IDs, assume native compaction, or infer image/tools/context support merely from compatibility. No local server, model download or hosted-provider call was attempted. [vLLM][vllm], [Ollama][ollama]

**Next-wave gaps and minimal proposed changes:**

1. **Mandatory dispatch gate:** wrap all three `LLMClient` methods through the embedded host’s replacement seam; check final HTTP dispatch after hooks. Verify both native and AI-SDK adapters: the latter uses its own `language.doStream`/fetch path, so a `RequestExecutor` replacement alone is insufficient. Arbitrary plugins/tools making independent calls remain unproved coverage. Keep this a narrow integration change. [Host override][o-host], [LLM service][o-client], [AI-SDK adapter][o-aisdk]
2. **Auxiliary attempt control:** explicitly configure title/compaction models and output limits; disable unauthorized title fallback, repair, overflow retry and recovery resend. Hooks are customization points; their failure contract is not evidence of an installed mandatory guard. Test missing/reloaded policy and tagged versus selected-build startup. [Hook contract][o-hooks], [request kinds/budgets][o-request]
3. **Capability and route fixtures:** exercise every table row with synthetic credentials/catalogues, alias changes, account changes, forbidden child override and rejected required media. Assert zero dispatch on denial and no second attempt after terminal rejection. Actual account availability, Windows packaging, tool protocol compatibility and model suitability remain unproved here.

**Exact checks performed.** Executed `python -B -` with AST-extracted, unchanged `_route`/`_selected_model` and allowlist helpers, synthetic in-memory settings and a stub error class: **9/9 passed** (no selection, forbidden provider, disconnected connection, cross-subscription ID, unlisted explicit choice, unlisted saved choice, Automatic catalogue selection, empty catalogue default, rejected choice without fallback). This is isolated function execution, not a full manager/provider test.

Ran **12 static source assertions**: four request kinds, title second attempt, child precedence, compaction nudge/native path/overflow loop, ten-retry allowance, both startup orderings, wire alias selection, AI-SDK dispatch and published Effect pin. Compared **12 cited local implementation files** with the Renulus baseline after newline normalization: all matched. Read pinned public files, registry metadata and official protocol documentation. No OpenCode runtime, live auth/provider, installation or service was executed. Parent-reported `tests/runtime/test_images_context.py`, using existing `C:/Renulus/dev/python/Scripts/python.exe`: **19 passed, 1 failed in 9.06s**, with the 401 discrepancy above. The earlier 13-failure run used global Python missing `ruamel.yaml`; it is superseded. Neither run was repeated in this lane.

[sdk-package]: https://registry.npmjs.org/@opencode%2Fsdk/2.0.26
[sdk-source]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/package.json
[r-policy]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/policy.py#L10-L24
[r-auth]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/auth.py#L19-L50
[r-transport]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L66-L151
[r-manager]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/manager.py#L309-L327
[r-api]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/api.py#L25-L45
[r-ui]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/apps/desktop/src/platform/ConnectionsPage.tsx#L301-L305
[r-capability]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/manager.py#L90-L119
[r-image]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/manager.py#L429-L439
[r-401]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/manager.py#L544-L559
[r-context]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/context.py#L13-L57
[r-memory]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/providers.py#L63-L104
[r-assessment]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/repository.py#L331-L380
[r-practice]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/generated_streaming.py#L201-L203
[r-updates]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/updates/service.py#L97-L156
[r-literature]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/updates/literature.py#L67-L93
[r-design]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md
[r-decision]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L143-L153
[o-runner]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/runner/llm.ts#L209-L285
[o-step]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/runner/step.ts#L73-L111
[o-resolution]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/runner/model.ts#L75-L90
[o-child]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/tool/plugin/subagent.ts#L168-L193
[o-context]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/context.ts#L95-L118
[o-title]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/title.ts#L127-L133
[o-model]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/model.ts#L260-L278
[o-compact]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/compaction.ts#L205-L455
[o-generate]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/generate.ts#L25-L73
[o-request]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/model-request.ts#L240-L428
[o-resolver]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/model-resolver.ts#L196-L238
[o-chatgpt]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin/provider/chatgpt.ts
[o-integration]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/integration.ts#L396-L409
[o-retry]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/runner/retry.ts#L42-L90
[o-transport]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/model-transport.ts
[o-restart]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution/restart.ts
[o-host]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/host.ts#L25-L56
[tag-host]: https://github.com/anomalyco/opencode/blob/9b4ec5714d481559990db0a816d5dec19541a814/packages/sdk/src/internal/host.ts#L28-L52
[tag-promise]: https://github.com/anomalyco/opencode/blob/9b4ec5714d481559990db0a816d5dec19541a814/packages/sdk/src/promise.ts#L33-L59
[o-client]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/ai/src/route/client.ts#L657-L683
[o-aisdk]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/aisdk.ts#L722-L731
[o-hooks]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin/hooks.ts#L21-L29
[go]: https://opencode.ai/docs/go/#endpoints
[vllm]: https://docs.vllm.ai/en/latest/serving/online_serving/
[ollama]: https://docs.ollama.com/api/openai-compatibility
