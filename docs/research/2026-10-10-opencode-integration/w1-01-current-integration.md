# W1-01 — Current Renulus ownership and OpenCode integration

2026-10-10. Research/testing only; no product implementation. Renulus inspected at detached HEAD `528025ff0b22477c12ee1512e0e7d15297a6e888`. All Renulus source links below pin that commit; paths identify the current local files. Concurrent planning edits were left untouched. The assignment's OpenCode selection and future opt-in vLLM/Ollama/additional-provider scope supersede older foundation exclusions; current subscription defaults and absence of required doctor setup remain.

**Finding:** preserve the Python domain services and Electron client, replacing execution ownership in a coordinated F0/M1/M3 migration. Design C is a backlog, not an already running integration: its execution record explicitly says DC01–DC21 are not started. Its Hermes-preservation wording now needs a scoped planning amendment, while its data, assessment and delivery contracts remain relevant. [Current execution record][execution], [C instructions][c-start]

OpenCode's source baseline is `4b6fea2875e4f2e3e8a8fee181803e54f7056845`; published `@opencode/sdk@2.0.26` has separate tag baseline `9b4ec5714d481559990db0a816d5dec19541a814`. Registry inspection confirmed matching 2.0.26 dependencies and Effect `4.0.0-rc.112`, with no `gitHead` returned. Do not substitute this package for the source candidate without reconciliation. The pinned SDK documentation describes in-process routing, explicit persistent database configuration and host disposal; none was executed here. [Registry metadata][sdk-package], [pinned SDK README][sdk]

**Ownership inventory — observed code, with proposed integration responsibilities.** Backend paths below are under `runtime/renulus/`; corresponding feature views are under `apps/desktop/src/modules/`. The architecture assigns module ownership, not named active workers. [Ownership ledger][ownership]

| Owner | Existing records/interfaces to retain | OpenCode/Design C boundary |
| --- | --- | --- |
| F0 runtime/platform | `runtime/manager.py`: route selection, cancellation, connection/capability status; `runtime/protected.py`: profile-bound DPAPI; desktop `platform/` and `electron/`. | Own the embedded host and model-policy adapter. Preserve connection migration and CPU helper provisioning; coordinate DC03 controller, DC08 isolation and DC10 settings. [Manager][manager], [protected storage][protected] |
| M1 Learn + M3 Cases | Learn thread/message/run records; Cases snapshots, revisions, attachments, teaching reveals and guarded handoffs. | One coordinated DC04 owner maps conversation identities and retention; DC05 adds projects. Move operational transcript/run ownership deliberately. [Learn][learn], [Cases][cases] |
| M2 Knowledge | `KnowledgeRepository.retrieve/check_evidence`, originals, revisions, locators, permissions and ingestion worker. | Expose eligible retrieval/read tools; retain deterministic import/access APIs. DC08 readers/extraction and DC05 shared documents consume the same references. [Retrieval checks][knowledge], [worker][worker] |
| M4 Assessment | Reviewed scoring/exposure, command idempotency and transactional learning evidence; generated-batch validation and publication. | Keep scores and saved tests domain-owned. Runtime executes generation; DC12–DC19 define artifacts, attempts and scheduling. [Reviewed commitment][assessment], [generation publication][publication] |
| M5 Memory | Canonical facts/revisions, suppression, capture jobs, Mem0/Qdrant derivatives and revision-filtered recall. | Retain eligibility; adapt completed-answer provenance and the bounded generation caller. DC06/DC19 consume eligible learning, never raw saved-case payloads. [Recall][memory], [answer resolver][answers], [Mem0 caller][memory-provider] |
| M6 Study | Global goals/preferences, deterministic plans and `study_activities`. | Retain progress logic. Project goals/notes and daily suggestions are DC09/DC06 additions; no runtime claim may award progress. [Study][study] |
| M7 Updates; M8 Content | Source-review/currentness operations and bounded scheduling; immutable installed content versions and pinned content lookups. | Keep review/edition authority and deterministic workers. Reuse scheduling patterns for DC19; do not turn every check into an agent turn. [Updates][updates], [content][content] |
| Integration owner | SQLite migrations, deletion/evidence ledgers, export/restore, shared shell/UI, contracts and dependency pins. | Reserve DC02, shared event/reference changes, host packaging and DC20/DC21. Actual contracts are `contracts.py` and `platform/contracts.ts`; the architecture's `packages/contracts/` is a planned path. [Database][database], [contracts][contracts], [renderer contracts][ts-contracts] |

One ownership gap merits explicit reservation: `retrieval/` is installed as a separate service but has no separate row in the older F0/M1–M8 ledger. Proposal: M2 coordinates discovery/evidence/import semantics, F0 connection policy, and M7 freshness consumers; one writer owns each concrete patch. Headless composition is another shared change: `Services` is reusable, but `server.create_app()` currently constructs services and applies migrations while assembling HTTP routers. Extract only that bootstrap seam if required. [Retrieval registration][retrieval], [server composition][server], [service container][services]

**Stable seams and their limits.** The existing `Provider` contract is `status()`, text-only `stream(messages, scope, run_id, model, system, purpose)`, and `cancel(run_id)`. Hermes transport removes tool declarations and rejects returned tool calls. A text-iterator replacement cannot expose child sessions, permissions or tool progress. Preserve a compatibility caller for bounded Mem0/generation requests while adding one small harness interface for conversation execution; do not recreate OpenCode's loop inside it. [Provider][provider], [transport][transport]

API v1 and `Event(id, run_id, sequence, type, payload)` are reusable transport conventions, not a unified semantic event protocol. `platform/runs.ts` filters duplicates/wrong-run events and recognises `completed/cancelled/error`; Cases emits `answer.delta` and `failed`. Specify one adapter mapping and cancellation result before migrating clients. Preserve ordinary domain HTTP calls. `ModuleOutlet` remounts on route/revision, so DC03/DC07 must separate pane navigation from response ownership. [Event contract][contracts], [run consumer][runs], [case events][case-events], [module mounting][outlet]

**Current lifecycle/transcript ownership — static observation.** Electron starts an owned Python child with an explicit profile, authenticates readiness, and waits for backend termination during quit. Python owns service startup/shutdown; Knowledge additionally uses router lifespan for its worker. There is no OpenCode host in the inspected application manifests. Adding a host requires explicit lifetime ownership, readiness and shutdown acknowledgement; a renderer component is unsuitable. The exact Windows process arrangement remains unproved. [Desktop lifecycle][backend], [quit][quit], [server][server], [Knowledge lifespan][knowledge-api], [desktop manifest][desktop-package]

Learn commits the user message before generation, persists the completed assistant answer/citations and learning evidence together, and marks surviving `running` rows `interrupted` on construction. Case runs/context are volatile; Save writes a snapshot, subsequent changes make it dirty/temporary, and even saved-case handoffs use temporary scope. Generated practice keeps run state in memory and publishes an active session only after validation; it does not yet checkpoint a 20-question saved-test job. [Learn lifecycle][learn], [case scope/save/handoffs][cases], [generated repository][generated], [batch limits][batch]

Consequently, **retire only overlapping execution machinery after parity**: migrated conversations' Hermes compression path, provider read/cancel loops, module-local generation run maps and ad hoc stream settlement. Retain domain commit guards, source/memory revision checks, assessment idempotency, ingestion, memory indexing and Updates scheduling. These enforce different invariants. Current package pins include Docling 2.133.0, Docling-core 2.99.0, FastEmbed 0.8.1, LanceDB 0.39.0, Mem0 2.2.1 and Qdrant-client 1.19.1; execution migration is not a reason to replace them. [Context path][context], [domain publication][publication], [pins][pins]

**Minimal migration proposal, not implementation.** Let OpenCode own new operational transcripts/executions/compaction, while Renulus owns conversation metadata, projects, originals, learning records and test versions. Add durable mappings between legacy conversation/run/message IDs and engine IDs. Preserve old history and citations through an explicit read/import adapter; never leave two writable transcript authorities. Migration must be repeatable and must not initiate generation or promote temporary input.

The critical hidden coupling is `memory/study_answers.py`: capture joins `learn_messages`, `learn_runs` and `learn_threads`, verifies completion/deletion and checks an answer hash. A versioned completed-answer resolver or clearly derived compatibility projection is necessary before moving new writes. Preserve provenance and suppression semantics across retries. Backup similarly allowlists table prefixes/preferences and validates exact columns; existing exports cannot automatically carry a separate runtime database. Reserve consistent snapshot/import, tombstones and rollback conversion with DC02. [Capture resolver][answers], [backup validation][backup], [restore relationships][restore], [DC02][dc02]

**Next-wave gaps and dependencies.** Keep the C delivery sequence and add narrow harness prerequisites:

1. **Wave A / DC02, F0 + integration:** freeze identity, retention, completed-answer and event contracts; classify observation disconnect versus Stop versus host exit. Prove populated synthetic conversion and temporary exclusion. `ContextScope` currently conflates kind/retention; separate saved/temporary from learning/case and archive/deletion before runtime persistence. [Scope][contracts], [C identity rules][identity]
2. **Wave B / DC03–DC05/DC07/DC12:** connect host-backed chat/resume with one M1/M3 owner; preserve deterministic teaching reveals and independent shared originals. Projects, Archive and durable drafts are missing C work, not SDK features. DC05/DC07 completion still depends on conversation identity. [C tickets][dc04]
3. **Wave C / DC06/DC08–DC14:** preserve memory invalidation and source locators, complete readers and backend assessment restrictions. `OriginalViewer` currently shows text literally, saves Office originals externally and lacks TIFF preview. A harness does not complete DC08. DC13 help needs chat/readers/notes; DC14 must block assistance through new tools as well as existing endpoints. [Reader][viewer], [reader ticket][dc08], [assessment tickets][dc13]
4. **Wave D / DC15–DC19:** M4 owns validated saved-test publication and recovery, not a second generic execution scheduler. DC06 Quick practice awaits DC12/DC13/DC16; DC18 additionally awaits timing/setup. DC19 can develop scheduling independently of home UI. Prove no duplicate publication, no automatic restart of billed generation, and fictionalisation before temporary input reaches durable work. [Generation through nightly][dc16], [wave gates][waves]
5. **Wave E / DC20/DC21:** verify restored runtime/domain consistency, deletion during execution, policy installed before recovery, and Windows host shutdown/packaging. Keep hidden app checks separate from native installation/authentication. No such integration proof exists in this memo. [Delivery gates][dc20], [app-control boundary][control]

**Checks actually run.** Source/schema inspection used `Get-Content` and bounded `rg` searches; `git rev-parse HEAD`, branch/status and diff inspection established the baseline. Public retrieval read only the pinned SDK README and exact registry metadata. Runtime command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:/Renulus/dev/python/Scripts/python.exe' -B -m pytest -p no:cacheprovider -q tests/learn/test_subscription_cancel.py
```

Result: **14 passed in 62.39 seconds**. Existing tests use synthetic HTTP streams, isolated SQLite and external-socket guards; they exercise explicit Stop, consumer cancellation, response closure and late failure without partial answer/evidence capture. This proves that bounded legacy seam, not OpenCode integration. Other useful, inspected test entry points are cross-module route/handoff tests, generated response-close tests and backup round trips; they were not rerun. No UI, live provider, auth, installation or service test ran; `test_images_context.py` was left to the parent. [Executed tests][tests], [route seams][route-tests], [generated cleanup][generated-tests], [backup seams][backup-tests]

**Parent-reported unresolved acceptance gap, not rerun here:** managed Python produced 19 passes and one failure in `tests/runtime/test_images_context.py` (9.06 seconds). `test_inference_auth_failure_invalidates_catalogue_without_image_claim` expects both `image_input` and `availability` to become `unknown` after HTTP 401; the implementation returns otherwise. Preserve this discrepancy in route/capability acceptance for wave 2. Earlier global-Python failures were masked by missing `ruamel.yaml`; they are not additional established product failures. No live provider was called. [Existing regression][image-test]

[execution]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/implementation/EXECUTION.md#L3
[c-start]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L11
[sdk-package]: https://registry.npmjs.org/@opencode%2Fsdk/2.0.26
[sdk]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/README.md
[ownership]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/ARCHITECTURE.md#L96
[manager]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/manager.py#L299
[protected]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/protected.py#L61
[learn]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/learn/service.py
[cases]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/cases/repository.py
[knowledge]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L531
[worker]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/worker.py
[assessment]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/repository.py#L251
[publication]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/generated_repository.py#L228
[memory]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/service.py#L278
[answers]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/study_answers.py#L12
[memory-provider]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/providers.py#L63
[study]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/study/service.py
[updates]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/updates/service.py#L38
[content]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/content/repository.py
[database]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/storage/database.py
[contracts]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/contracts.py
[ts-contracts]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/apps/desktop/src/platform/contracts.ts
[retrieval]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/retrieval/api.py#L40
[server]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/server.py
[services]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/services.py
[provider]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/generation.py#L8
[transport]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L66
[runs]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/apps/desktop/src/platform/runs.ts#L5
[case-events]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/cases/repository.py#L604
[outlet]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/apps/desktop/src/shell/ModuleOutlet.tsx
[backend]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/apps/desktop/electron/backend.ts
[quit]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/apps/desktop/electron/main.ts#L154
[knowledge-api]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/api.py#L57
[desktop-package]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/apps/desktop/package.json
[generated]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/generated_repository.py
[batch]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/generated_contracts.py#L9
[context]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/manager.py#L338
[pins]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/pyproject.toml
[backup]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/storage/backup.py
[restore]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/storage/recovery_records.py
[dc02]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L401
[identity]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L111
[dc04]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L448
[viewer]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/apps/desktop/src/modules/library/OriginalViewer.tsx#L39
[dc08]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L522
[dc13]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L619
[dc16]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678
[waves]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L786
[dc20]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L754
[control]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/implementation/APP_CONTROL.md
[tests]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/tests/learn/test_subscription_cancel.py
[route-tests]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/tests/runtime/test_cross_module_generation.py
[generated-tests]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/tests/assessment/test_response_close.py
[backup-tests]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/tests/backup/test_round_trip.py
[image-test]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/tests/runtime/test_images_context.py
