# Renulus backend finalisation specification

2026-10-26 instruction/audit · 2026-10-27 reviewed specification ·
**Approved as an implementation specification baseline; zero material findings remain.**

This is the single finalisation target. It consolidates existing H/DC contracts;
it neither declares implementation complete nor authorises source, runtime,
account, acquisition, installation or deployment changes. Section 13 records
the sequential independent reviews and every accepted finding/repair.

## 1. Authority, scope and starting evidence

### Confirmed direction

The [October 26 instruction](2026-10-04-user-answers.md#october-26-full-backend-finalisation-specification)
confirms TypeScript/Effect plus Python, full OpenCode v2 integration, connected
tools and reliable addition/removal/editing of harness capabilities. Preserve
Design C, SQLite, Mem0 OSS/local Qdrant, Docling/HybridChunker, FastEmbed and
LanceDB OSS. Preserve existing Python implementations until connected
replacements pass. The [decisions](../DECISIONS.md),
[C shared rules](DESIGN_C_IMPLEMENTATION_SPEC.md#4-shared-interaction-and-data-rules),
[module ownership](ARCHITECTURE.md), [worktree rules](PARALLEL_WORK.md),
[H tickets](opencode-v2/README.md) and [source register](../SOURCES.md) govern.
Later confirmed instructions supersede historical temporary/default-cutover text.

Selected generative routes remain exactly Codex `gpt-6.1-sol`, `gpt-6-astra`,
`gpt-6-luna`; OpenCode Go `mimo-v2.6-pro`, `deepseek-v4.1-flash`. No hosted
Renulus service, model training, mandatory paid API, user-managed inference,
new orchestration/storage/search framework or engine replacement is included.
H11 history trees and H19 additional/local providers remain optional future
work. Full Office editing, cloud synchronisation, closed-app scheduling and
the proposed new teaching-card/corpus campaign are outside backend completion.

### Engineering defaults selected here

Restart-based plugin changes, a single profile-wide canonical-writer handoff,
bounded queues, storage allocations and default-off developer tools below are
concrete engineering defaults, **not newly confirmed owner permissions**.
Changing a default requires a recorded rationale and affected acceptance.
Required doctor journeys are part of completion, including disabled/unavailable
states when an account or source does not support an operation.

### Verified baseline and limits

The audited source is `1a40d9fc0813eac1672e21427a5a0430933d3aa4`, branch
`codex/design-c-integration`, canonical checkout `C:/Renulus/dev/repo`.
Uncommitted parent documentation is not accepted product implementation.

| Area | Starting fact and retained limit |
| --- | --- |
| Desktop | Source MVP selected by this PC's ordinary shortcut; previous packaged `f1c49444` retained. Self-contained H20 packaging is open. |
| Native default | `runtime/renulus/runtime/desktop_harness.py` enables Explain only and exactly `renulus_library_retrieve` / `renulus_library_citation`; capture/standalone/title and children budgets are zero. Recall remains wired; desktop images are refused. |
| Local foundation | H00 consumed; H01/H24 locally accepted. Latest H02–H08 checkpoint accepts H02–H05 locally, including selected local engines and synthetic counting transport. It does not qualify accounts or packages. |
| Later integration | H06 has migration/history/delete proofs, with immediate-Archive hidden closure open. H07's isolated child/Library/M5, Stop and closed-death proofs await coordinated integration; preserve its WIP. H08 remains gated. |
| Account | October 20 proves one real Sol text answer, saved and deleted through production backend. No live Go/tool/image/full-renderer/package inference is established. Earlier Go `invalid_host` was a local Host guard failure. |
| Existing product | DC01–DC20 have bounded design/source/connected evidence. They are regression contracts, not missing screens. DC21 final installed acceptance remains H20. Finder still searches legacy message storage; native-only message coverage is an unproven parity gap. |

Evidence: [MVP record](../implementation/MVP_20261019.md),
[foundations](../implementation/OPENCODE_FOUNDATIONS_HANDOFF.md),
[H02–H08 checkpoint](../implementation/OPENCODE_H02_H08_HANDOFF.md),
[H06 criteria](../implementation/OPENCODE_H06_CRITERIA.md), and the C spec's
ticket-status table. Historical failures remain evidence, not simulated passes.

## 2. One authority and the final process layout

### Final responsibilities

The stable public Interface remains authenticated `/api/v1` for desktop and
headless clients, with existing JSON/ZIP compatibility, ordered stream events,
drafts, reader references and recoverable errors. The renderer holds no secrets,
database handles, filesystem authority or provider transport.

| Process/module | Final responsibility | Excluded authority |
| --- | --- | --- |
| Electron main, existing `apps/desktop/electron/backend.ts` | Own app/profile lifecycle, launch hidden backend children, native chooser/external-open mediation and authenticated renderer transport. | Canonical transactions, model dispatch and scoring. |
| Node 26.4.0, proposed `packages/backend/src/main.ts` | One Effect application scope: public facade, configuration/grants, dispatch admission, canonical SQLite, domain modules, receipts/outbox, storage accounting and native OpenCode embedding. | A second agent loop, child scheduler or transcript database. |
| Embedded OpenCode, existing `packages/harness/src/host.ts` / `learning-host.ts` | Native execution, inbox/jobs/claims, messages, tool lifecycle, children, context, MCP and native event observation. Saved graph owns `state/harness/opencode.sqlite`. | Canonical learner facts, reviewed keys, scores or independent provider selection. |
| Python, proposed `runtime/renulus/workers/main.py` | Controlled workers for Docling/HybridChunker, FastEmbed, LanceDB, Mem0/local Qdrant, safe decoding/OCR, existing Windows filesystem primitives and DPAPI/auth/credential-bound transport. | Final canonical-domain writes, configuration choice, scheduling or autonomous network retries. |

Process graph: Electron → one Node facade/OpenCode process → owned Python
engine/broker process; Python inference callbacks return to Node dispatch.
There is one canonical writer, one native transcript owner and explicit engine
leases. Python may run bounded threads; one Mem0 worker retains ownership
through real settlement. No generic worker service/system daemon is added.
A separate fully volatile graph serves temporary work.

Effect Layers provide real varying Adapters at the domain-owner, engine and
protected-transport Seams. Proposed modules are `host/`, `domain/`, `storage/`,
`dispatch/`, `workers/`, `plugins/`, `http/` and `contracts/` beneath
`packages/backend/src/`; domain names remain learn, cases, knowledge, assessment,
memory, study, updates and content. Native embedding stays in
`packages/harness/src/`, shared schemas in `packages/contracts/`. These are
proposed paths, not SDK exports. Keep current Python paths under
`runtime/renulus/{runtime,storage,learn,cases,knowledge,assessment,memory,study,updates,content}/`
until handoff. Workers reuse their engine implementations, not forks with
different assets. Existing entrypoints `python -m renulus.server` and
`packages/harness/src/main.mjs` remain compatible during migration.
The final distributed entrypoint is compiled `packages/backend/dist/main.mjs`,
launched with bundled Node and explicit profile/port/owner identity; it starts
bundled Python with `-m renulus.workers.main`. Headless clients use the same
facade and profile-owner handshake. No separate headless domain implementation.

### Canonical transaction strategy and transition

**Python remains the sole canonical writer and dispatch authority until one
atomic profile-wide handoff.** Per-plugin/per-table writer transfer is rejected:
attempt+evidence+outbox and deletion+lineage cross module ownership. TS plugins
initially call the Python domain facade; Python transactions remain local.
Each slice also exercises its final TS implementation end to end against an
isolated synthetic target profile, where TS is the sole writer. No production
shadow writes or merging two databases is permitted. This verifies the target
incrementally while retaining a production-compatible route.

Final TS domain modules contribute synchronous local transaction functions to
one integration-owned SQLite transaction module. It atomically checks revisions,
assessment policy, cancellation/deletion/grant epochs and records the mutation,
learning evidence, receipt and effect intents. Plugins never open independent
canonical writers. Resolve native transcript content, remote work and engine
outputs **before** transactions; commit only immutable digest-bound inputs and
local predicates. No IPC/model/native-engine wait inside a canonical transaction
or physical conversation/source/recovery lock.

Handoff closes admission with a logical maintenance lease, settles hosts and
workers, snapshots the complete compatible generation, and performs a read-only
migration preview. Validate schema inventory, typed relations, IDs, exports and
old/new command results before applying migration to a prepared generation.
An atomic profile selector publishes that generation with `writer=ts`, authority
epoch and compatible binaries; only then may Node open canonical writes. Python
opens worker/derived stores only. Crash before selection retains Python; crash
after selects TS recovery with admission closed. Neither process guesses ownership
from PID age. Refuse an incompatible/ambiguous selector. Rollback selects a
complete compatible generation after settlement and current deletion/grant
reconciliation; it never enables both writers or silently drops newer records.

Use Node 26.4.0's built-in `node:sqlite` `DatabaseSync` in one owned canonical
writer thread, avoiding another database framework. Its synchronous prepared
statements/transactions run entirely in that thread; Node's control/event pump
continues independently. Submit one typed local command, never arbitrary SQL.
Mirror foreign-key, secure-delete, WAL and migration-inventory rules from
`runtime/renulus/storage/database.py`; use bounded busy handling and paginated
reads. `BEGIN IMMEDIATE`/commit/rollback compositions preserve cross-domain
atomicity. Migrations run while admission is closed. The
[versioned Node 26.4.0 SQLite reference](https://nodejs.org/download/release/v26.4.0/docs/api/sqlite.html)
documents these synchronous primitives; it marks this module release-candidate,
so BF00 must prove exact schema/query/backup compatibility before adoption.
The driver choice is fixed here; failure keeps Python authority and requires
an explicit spec amendment, not an implicit alternate storage stack.

TS also writes the existing machine-local work/intent tables in the canonical
database, including ingestion, dirty-sequence and original-publication debt;
Python workers receive immutable plans and report outcomes without opening that
database. Preserve intent-before-I/O by committing the host intent, executing
native work outside the transaction, then committing acknowledgement/publication.
Worker guard files and derived engine histories do not become alternative
canonical journals. Final worker extraction must remove accidental repository
construction/database writes inherited from current Python service assembly.

Preserve product IDs, typed namespaces, question versions, timestamps, old
column meanings and schema-1 conversion. Additive sidecars and registered
migrations extend schema 2; a needed later schema is explicitly versioned.
`harness/1` and `renulus-harness/1` retain exact existing shapes; new contracts
negotiate versions rather than adding forbidden fields to them.

## 3. Native composition and reliable plugin lifecycle

### Verified native Seams

Use `@opencode/sdk/effect` **`OpenCode.create(options, embed)`** in Scope;
`embed.overrides` supplies LayerNode replacements [U1], [U2]. The Promise wrapper
cannot supply those overrides. Native `Plugin` is `{id, effect(context)}`;
`context.tool.transform` exposes list/get/add/update/remove/namespace, scoped
registrations, hooks, reload and final tool list [U3], [U14]. Session hooks provide
prompt/context/generate/summary/request interception [U5]. Reuse native
skill/provider/MCP transforms. Version deterministic dependencies.

The minimal trusted host retains profile ownership, protected path/config
overrides, closed package acquisition/discovery, final dispatch/context checks,
native recovery holds, worker settlement and observation. Current
`packages/harness/src/host.ts` overrides more than a public plugin: retain these
protections until a connected proof replaces each. Capability plugins compose
Library, memory/context, learning, assessment, study, updates, evidence, skills,
children and MCP through native registration. The manifest is an application
configuration record, **not another plugin bus**. Effect Scope owns resources/
finalizers; interruption alone does not release Python threads, native SDK
handles or remote effects.

### Manifest and activation

Proposed `renulus-plugin/1` contains stable `plugin_id`, semantic version,
immutable artifact SHA-256, native ID, host/cohort compatibility, dependency
IDs/version ranges, contract/schema/migration IDs+checksums, tool names and
input/output schema hashes, prompt/skill IDs+versions+hashes, declared
capabilities/endpoints/retention/resource bounds, licence notices and owned
derived namespaces. Store only credential references. Cycles, missing
dependencies, duplicate tool IDs, unknown migrations and incompatible cohort/
schema fail staging. The integrator owns migrations; removing code does not
remove canonical data or migrations.

1. **Stage/install/edit:** user/admin selects reviewed immutable local artifacts.
   Editing creates new bytes/version/hash. Verify licence, integrity and closed
   dependencies; no runtime npm/pip resolution, global skills/config, ambient
   account import, external MCP startup or network inference.
2. **Inspect candidate:** boot an isolated disposable profile/graph with recovery
   and effects denied. Observe loaded plugin identities and final schemas/names
   after every transform; hash registry/prompts/dependencies. Bind the receipt
   to exact loaded artifact hashes, not just requested IDs.
3. **Quiesce:** close live admission; cancel/drain affected operations, children,
   pending permissions, MCP and engine leases. Timeout leaves `held`, never
   successful removal. Record uncertain admitted external effects.
4. **Select:** persist requested/ready revision, then atomically select effective
   manifest with authority/configuration epoch. Restart with immutable artifacts
   and existing store, recovery held. Re-observe registry/loaded identities;
   reopen only on an exact match.
5. **Reconcile:** crash before select keeps old effective revision; after select
   starts closed and validates selected bytes/registry. Failed startup stays
   failed/held or explicitly rolls back to the previous complete healthy revision.
   Requested, effective, failed and held states remain separately visible.

The SDK has register-by-ID and reload, **no unregister** [U13]. Reload can restore
old healthy bytes after new setup fails [U4]; that is a failed candidate, never
activation of the requested hash. Disable/removal therefore immediately narrows
grants, settles effects, and restarts a host omitting the plugin. Dependants
disable first or removal refuses. Derived cleanup is journalled separately;
saved data needs explicit deletion. Disconnect, credential removal, disable,
uninstall and data deletion differ. Rollback never restores revoked permissions.

Trusted in-process plugins are not a sandbox. Grants constrain approved Adapters
and mediated native tools, not malicious plugin JavaScript or arbitrary programs
admitted through shell/local MCP. Installation requires reviewed artifacts.
The developer execution trust exception in section 4 is explicit; root checks
are not OS confinement. No unconditional OpenCode patch is selected. BF01 proves registry
identity/removal; BF03 proves current child/permission authority; BF04 proves
volatile graph/context hooks. Each spike is bounded to one connected synthetic
scenario and exits with a passing supported-Seam implementation or reproducible
failure. Keep the capability unavailable on failure; F0 may propose a narrow
source patch with test, licence/provenance and removal condition. The target
architecture and one-owner invariants do not change with spike results.

## 4. Exhaustive capabilities, tools and command authority

### Common execution contract

**E** means existing model tool; **P** proposed model tool ID; **N** native tool
requiring a Renulus Adapter; **C** direct user/admin command only. Service
methods are not model tools. All rows are required doctor capabilities unless
explicitly developer/future. Schemas are frozen in manifests.

Every model call receives a host-minted envelope binding profile, native
session/call/parent, scope, retention, operation/attempt, configuration/grant,
assessment/context/deletion/cancel epochs and allowed references. Arguments
cannot set these. **R** reads check rights/revisions before read and return,
recording exact dependencies. **M** local mutation/proposal uses expected
revision plus `(operation, action, payload digest)` idempotency and local commit
checks. **X** external effect reserves usage and records admission, uncertainty
and settlement. C mutations use the same rules. Stop suppresses late publication;
committed results return their reference; timeouts never authorise blind resend.
Active Test denies assistance across every row; neutral Settings/recovery and
attempt-owned commands remain available.

Keep existing native permission `renulus.library`. Proposed grant identities
are `renulus.source.read`, `renulus.evidence.search/fetch`,
`renulus.memory.recall`, `renulus.context.read`, `renulus.history.read`,
`renulus.project.read`, `renulus.note.read/propose`, `renulus.find`,
`renulus.study.help`, `renulus.practice.propose`, `renulus.plan.propose` and
`renulus.updates.read`; slash groups expand to separate dotted names. Bind each
to the row's host-resolved global/project/conversation/attempt scope and exact
allowed references. Native question/skill/child grants bind curated IDs; MCP
grants bind server+endpoint revision+tool schema. Direct commands derive user
authority from authenticated client intent, never a model-supplied user flag.

### Domain catalogue

Unprefixed Python paths in this table are relative to `runtime/renulus/`.

| Plugin / current owner paths | Callable surface and status | Rights, effects, revisions and connected journey |
| --- | --- | --- |
| Library, M2 `knowledge/api.py`, `worker.py` | E `renulus_library_retrieve`, `renulus_library_citation`; P `renulus_source_read` | R: preserve existing schemas/names; active revision and display/index/model-use rights, page/item pins. Retrieve → citation → reader/original; revised/deleted source refuses late return. |
| Acquisition/readers, M2 `reader.py`, `reader_api.py`, `attachment_api.py` | C catalogue, select/import, queue/status, cancel/retry, replace/remove, original Open/Save, preview/position, passage-to-draft | M selected files, rights review, original hash, expected revision and capacity reservation. No sibling crawl/indexing from viewing. Failed/cancelled extraction retains original and truthful state; retry reconciles partial rows. |
| Evidence, M2/F0 `retrieval/api.py`, `learn/service.py` | P `renulus_evidence_search`, `renulus_evidence_fetch`; N adapted `websearch`, `webfetch`; C configure/select provider, deliberate article import | R/X generic topics, permitted endpoints, redirect/private-network guard, dated discovery vs passages. Key-free PubMed/Europe PMC/public evidence and explicitly selected Brave/Tavily/Exa lanes; no generative vendor products. Quota/fetch failure has no fallback debit. |
| Memory, M5 `memory/{engine,providers}.py` | P `renulus_memory_recall`; C inspect/edit/delete/export, explicit Capture, retry/rebuild | R current fact/source revision/scope. Correction/delete M invalidates lineage, jobs, engine history and personalisation. Automatic extraction is separately admitted from committed eligible receipts, not general model-write authority. |
| Context/history, M1/M5 `runtime/harness_learning.py`, Learn history | P `renulus_context_refs`, `renulus_history_range`; C pin/unpin sources/facts, inspect context | R exact eligible refs/ranges, hashes, rights/relevance; no paths. Pin M changes future context only. Compacted history → older exchange → eligible reinjection; unavailable source explicit. |
| Chat/cases, M1/M3 `learn/conversation_stream.py`, `cases/streaming.py` | C teaching-case catalogue/start/reveal, send/direct/guided/follow-up, attach/image, Stop/retry/resume, drafts, Archive/unarchive/delete, temporary/Save | M/X one native message owner, latest draft/revision/policy; case/image rights/retention. Saved disconnect detaches observation; abnormal temporary-owner disconnect cancels/settles/discards the family under section 7. Lost ACK reconciles native inbox/canonical receipt before retry. |
| Projects/Notes, M6/M2 `study/`, `knowledge/note_service.py` | P `renulus_project_read`, `renulus_note_read`, `renulus_note_propose`; C project CRUD/membership/goals, note save/revise/delete | R/M proposals never save autonomously. Expected membership/note revision; shared files linked once. Note → Ask → explicit Save → retrieval/reopen. Unlink/project deletion preserves independent originals. |
| Finder, integration `storage/search.py` | P `renulus_find`; C global literal search/navigation, archive/project filters | R canonical scope/rights, epoch-bound cursor; native-message lookup in BF02. No temporary/reserved/Test snippets. Result opens exact source/chat without losing drafts/response. |
| Reviewed content/assessment, M4/M8 `assessment/api.py`, `content/` | C pack validate/install/activate/withdraw; attempt setup/draft/commit/submit/report/retake/progress; P `renulus_study_help` | Scoring/keys/source review never autonomous tools. Help exposure before assistance. Local atomic attempt+evidence+outbox survives provider failure. Result narrative sees approved committed result only. |
| Generated practice, M4 `generated_streaming.py`, `generation_service.py` | P `renulus_practice_propose`; C request/save 5/10/20, checkpoint, explicit Retry/shorter acceptance | M/X validated batches, no self-awarded review or arbitrary publication. Revisions/validator receipts/requested vs accepted count pinned; lost ACK resolves one saved version → whole Study/Test. |
| Personal import, M4/M2 `import_service.py` | C selected text/file extraction, candidate edit/key resolution, explicit normalization/refinement, Ready publication | M/X `test-import`, existing three-call normalization bound. Original/hash/rights, candidate revisions and ambiguity survive cancel/reopen. No autonomous import approval or bank promotion. |
| Fictional tests, M4/M1/M3 `fictionalisation.py`, `learn/chat_test_service.py` | C Create test, privacy review/publish; transformation/review under `fictional-test` | M/X volatile raw input, independent review, process-minted receipt. Only fictional artifact crosses retention; no durable original hash/job/ref. Chat card and Tests open same immutable version. |
| Home/plans, M6 `study/home_service.py` | P `renulus_plan_propose`; C preferences/goals/plan edit, suggestions/read/resume | R/M/X dated three-category bundle, five each; eligible inputs, no case dumps/keys. Selection prefills, Send separate. Manual overrides win; correction/restore invalidates cache. |
| Nightly, M6/M4 `study/nightly_service.py` | C opt-in/time/count/off/Stop/retry/status; native generation executes occurrence | M/X local-date claim, one bounded catch-up while app runs; default Off, 22:00/five planning defaults. Shutdown interrupts; checkpoints recover without automatic inference. No model schedule editing. |
| Updates, M7 `updates/service.py` | P `renulus_updates_read`; C source check/review/save/correction disposition; `updates-digest` role | R/M/X dated review/outbox, affected-item links; digest cannot mark current/reviewed. Failed checks retain success+failure; corrections flag content, never rewrite attempts. |
| Skills/question, F0/M1 native Context | N `skill`, `question`; C permission answer, versioned skill/prompt selection | R/M curated skills/app question UI, explicit cancel/reject. Skills grant no tools; no workspace AGENTS/global discovery. Answers bind pending call/current grant epoch. |
| Children, F0 H07 | N `subagent`; C observe/cancel family | X native Session/Job, parent-intersected current grants, depth/concurrency/dispatch budget. Evidence-review child → citation → parent. Cancel/revoke/crash retains claims until family settlement. |
| MCP, F0 H09 | Native discovered server/tool names [U15]; N `opencode.list_mcp_resources`, `opencode.read_mcp_resource`; C connect/approve/revoke | R/M/X classified by exact schema/effect; endpoint/schema/credential/grant revisions bound. Unknown effects require approval. Reconnect/retry cannot regain grants; pending “always”/child/late returns fenced. |
| Platform, F0/integration `runtime/api.py`, `storage/` | C login/cancel/refresh/disconnect, settings/capabilities, plugin lifecycle, export/backup/restore/relocate/cleanup/shutdown | No model credentials/backup/restore/deletion-policy/scoring authority. Expected config/profile generation, protected handles and complete manifests. Account-free Settings/readers/reviewed work usable. |

### Complete upstream inventory and disposition

These are **actual pinned native names/families**, not current Renulus exposure
[U10], [U11], [U12], [U13], [U14], [U15], [U16]. Adapters cannot bypass the preceding contract.

| Names | Final disposition and authority |
| --- | --- |
| `question`, `skill`, `subagent` | Doctor Adapters above; no ambient upstream grants. |
| `webfetch`, `websearch` | Selected evidence providers/rights/budgets; upstream ambient/paid defaults disabled. |
| `opencode.models`, `opencode.session_rename` | Allowlisted capability read/title proposal; accepted rename canonical M with expected revision. Listing does not probe providers. |
| `opencode.list_mcp_resources`, `opencode.read_mcp_resource`, discovered MCP tools | Explicit connection/scope/grants; schema hashes/resource provenance pinned. |
| `read`, `glob`, `grep`, `edit`, `write`, `patch`, `shell` | Optional developer plugin, default Off; filesystem roots and read/write/execute grants separate. Doctor tools use readers. Writes need revision/hash/receipts; shell effects may be uncertain, not reversible. |
| `opencode.session_move`, `opencode.worktree_create`, `opencode.worktree_list`, `opencode.worktree_remove` | Developer plugin; workspace/root/branch grants, no doctor-session relocation/inheritance. Destructive removal requires exact owned identity/direct approval. |
| Code Mode `execute`, catalog search/fetch; global HTTP `fetch` | Developer plugin, Off; scoped catalog and separately admitted HTTP X capability. Stock global fetch is replaced by the broker-backed extension below. No indirect access to disabled tools or unmediated HTTP. |
| `browser.tabs.list/open/focus/close`; `browser.preview`; `browser.navigate/back/forward/reload/stop` | Required browser part of developer plugin, enablement Off; owned attachment/profile/network-endpoint lease plus action grants required. Navigation URL checks are distinct from the network boundary below. Registration does not prove attachment. |
| `browser.frames/snapshot/find/evaluate`; `browser.click/hover/drag/fill/fill_form/select/check/press/scroll/wait/screenshot/dialog` | Explicit developer grant; evaluate/input can mutate/leak data. No default doctor browser automation. |
| `browser.files.upload/drop/list/get`; `browser.console`; `browser.network.list/get` | Separate transfer/sensitive-output scope; declared handles only, no credential/native-profile reads. |
| `browser.trace.start/stop/analyze`; `browser.cpu.start/stop/analyze`; `browser.heap.snapshot/summary/query/object/compare`; `browser.lighthouse` | Bounded diagnostic artifacts/retention/cancel, no automatic profile inspection. |

Browser grouping enumerates dotted operations, e.g. `browser.tabs.list`,
`browser.files.upload`, `browser.trace.analyze`. Developer enablement needs a
separate reviewed install/configuration; this spec grants no activation. If
installed, the same dispatch/grants/retention/budget/Test fence applies.
The developer plugin is a required implementation deliverable, shipped disabled
and separately selectable; “optional” describes user enablement, not permission
to omit integration. BF03 implements and tests every listed native family with
owned synthetic files/browser state and a capability receipt. A missing browser
attachment or external prerequisite is reported explicitly. No test needs the
owner's native browser profile or desktop input. Runtime acceptance includes the
disabled default and a deliberately enabled synthetic developer configuration.

**Code Mode HTTP:** the pinned tool constructs `CodeModeWeb.extension`, whose
global `fetch` calls `globalThis.fetch` directly [U17]. Tool-catalog permissions
and the generative RequestExecutor do not intercept it. The stock extension
must not be exposed. A proposed host-bound replacement sends each fetch through
the same external-effect admission and Python transport broker: bind current
operation/config/grant/cancel identity, method/URL/body digest, permitted headers,
endpoint and redirect hops; reserve request/response bytes and usage, stream
bounded results, retain admitted-effect ownership until settlement. Each request
and redirect is re-authorised; a subsequent fetch after revocation is rejected.
No model-supplied authorization header/credential reference or private-network
target is accepted. BF03 proves interception, redirect/oversize failure and a
fetch started after an awaited call is revoked. Investigate the existing
composition seam first; if it cannot substitute this extension, use the narrow
injection-patch process in section 3. Catalog-only interception is insufficient.

**Browser connection and continuing traffic:** native browser registration also
creates attachment RPC and raw TCP tunnels outside tool execution [U20], [U21].
Stock session/connection-ID checks and automatic session-wide `browser/*` allow
are insufficient. Select an app-owned browser attachment adapter and a
broker-backed tunnel factory; keep native tools/RPC/browser engine. The stock
Node `net.createConnection` tunnel path is not exposed. Python owns bounded
socket bytes; Node owns current authority/admission, and the existing owned
desktop browser client owns the isolated developer browser context. No owner
browser profile or learner credentials are attached. This is required BF03
integration, not a new browser automation framework.

An explicit attachment permit binds profile/session/root operation, connection
and client generation, developer context identity, config/grant/cancel epochs,
exact allowed network targets, bytes/socket limits and expiry. Attach and every
reattach require a fresh current permit; a native saved browser allow grants
nothing independently and is removed on detach/revoke. Proposed initial lease:
five minutes, eight sockets, 100 MiB combined traffic, renewable only by an
explicit direct command. These are calibratable defaults, not a background grant.
The lease admits ongoing **page execution/network lifetime**, including scripts,
redirects, subresources and streams after a tool returns; it does not pretend
that each page effect is another model call. The root Stop, developer disable,
attachment disconnect, expiry or grant revocation closes this lifetime.

Enforce the network boundary at broker tunnel open **and every read/write
credit**: current epochs/lease, exact destination host and port, DNS-resolved
address pinned for that connection, private-network policy, maximum bytes and
retained socket identity. Do not pass browser-supplied arbitrary IPs or allow a
reconnect to reuse old authority. Cap/destroy inbound buffers at revoke; bytes
already admitted/on the wire cannot be undone. The app-owned client uses only
its owned authenticated proxy, with no direct-connect fallback; disable other
egress paths such as QUIC/WebRTC for this configuration. If the selected client
cannot establish that traffic boundary, attachment remains unavailable until
the bounded client seam is adapted/proved. Do not attach an arbitrary browser
whose direct network lifetime the app does not own.

**Granularity/trust:** encrypted CONNECT is opaque. The enforceable tunnel policy
is approved network **host/port plus resolved address**, not HTTP path, website
origin identity or content rights inside TLS. Navigation tool arguments receive
separate URL checks, but these do not claim to restrict later page requests.
Within an admitted endpoint, pages are trusted developer execution: same-endpoint
redirect paths, scripts, HTTP/2 origin coalescing and WebSocket messages are
permitted under the explicit continuing lease, not per-request URL consent.
Distinct ungranted network targets fail; a same-address/coalesced application
origin cannot be promised blocked by a TCP wrapper. No full-URL/source-rights
confinement is claimed, no patient/learner context is supplied, and this exception
never applies to doctor evidence retrieval. A future stricter URL mode would
need a proved owned-client request hook; TLS interception is not assumed here.

Revoke first commits the closed epoch, rejects new attachment/tunnel/control
work, cancels pending browser actions, removes its native allow, closes all
owned proxy/tunnel sockets and destroys the owned developer browser context.
Retain attachment leases until socket/client closure acknowledges actual
settlement; otherwise report uncertain effects/cleanup debt. Discard late
state/result/tunnel callbacks. No automatic reattachment, page reload or native
allow restoration may recreate authority; renewal after closure creates a new
generation and an inert context. Tool interruption alone is not this teardown.
Existing streams lose future read/write credits and are closed, even if their
opening tool completed. Previously admitted network effects remain accounted.

BF03/P02 tests A→ungranted distinct endpoint B via navigation, subresource,
redirect and delayed script; revocation with a live WebSocket/pending read/write;
lease expiry/bytes; stale attach/native-allow restoration and proxy/client death.
Assert no new B connection, no newly admitted bytes after revoke, no stale
publication and actual owned closure before lease release. Also verify the
declared same-endpoint trusted behavior so tests do not claim URL confinement.
Inspect connection/tunnel factory composition first; if the pin hardwires it,
use section 3's narrow injection patch with provenance and removal condition.

**Developer execution trust:** choose trusted OS-level execution for arbitrary
shell programs and local MCP executables, with no sandbox claim. Working-root
checks and command approval govern admission only; programs can access files
and networks with the Windows user's rights. Direct shell networking is outside
the mediated transport policy. Enabled arbitrary execution is therefore a
separate developer configuration/profile with explicit direct opt-in, reviewed
executables and no supplied learner-profile handles or broker credentials.
It is never inherited by doctor sessions, children or temporary patient work.
This separation reduces accidental access; it does not confine code running as
the same Windows user. Single-writer, rights, quota, no-spill and revocation
guarantees apply to mediated app operations, not deliberate bypass by trusted
OS code. No stronger shared-profile protection is claimed.

Launch owned programs with a minimal explicit environment, retained process
identity and Windows Job Object descendant ownership; interrupt/terminate the
owned family and verify actual death before releasing leases. Programs that
escape ownership or external effects remain uncertain; revocation cannot undo
their earlier OS effects. BF03 verifies an out-of-root write/network attempt and
a surviving descendant using synthetic paths/local endpoints, recording these
trusted-execution effects accurately. It must refuse doctor-mode exposure and
unproven descendant settlement. A future confined execution mode would require
its own named OS boundary and acceptance; it is not assumed here.

## 5. Typed worker and facade contracts

Add negotiated `renulus-worker/1` JSON Schemas to `packages/contracts/`, generated
as strict TS/Python models: finite numbers, unknown fields rejected, bounded
strings/arrays, tagged results/errors. No new RPC framework. Existing harness
IPC retains `renulus-harness/1` and five outcomes: `rejected_before_admission`,
`accepted_pending`, `committed_reference`, `cancelled_settled`,
`uncertain_after_disconnect`.

Example **proposed worker protocol**, not an SDK API:

```json
{
  "protocol":"renulus-worker/1","kind":"command",
  "profile_id":"profile_synthetic","domain_store_id":"domain_a",
  "runtime_store_id":"runtime_a","authority_epoch":4,"process_generation":"pg_b",
  "operation_id":"op_7","attempt_id":"attempt_2","request_id":"req_9",
  "payload_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "configuration_revision":8,"grant_revision":12,"context_epoch":31,
  "deletion_epoch":6,"cancellation_epoch":0,"retention":"saved",
  "command":"document.extract","expected_revision":"rev_7",
  "input":{"artifact_handle":"artifact_8","offset":0,"length":67108864},
  "limits":{"result_page_bytes":262144,"cpu_seconds":120}
}
```

```json
{
  "protocol":"renulus-worker/1","kind":"reply",
  "identity":{"profile_id":"profile_synthetic","domain_store_id":"domain_a",
    "runtime_store_id":"runtime_a","authority_epoch":4,"process_generation":"pg_b",
    "operation_id":"op_7","attempt_id":"attempt_2","request_id":"req_9"},
  "request_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "revisions":{"configuration":8,"grant":12,"context":31,"deletion":6,"cancellation":0},
  "outcome":"committed_reference",
  "result":{"artifact_handle":"artifact_result_3","artifact_revision":1,
    "artifact_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "bytes":8192,"engine":"docling:2.133.0","pages":12,"next_cursor":null},
  "settlement":{"worker_lease":"lease_4","state":"settled"}
}
```

Here committed-reference means **worker output staging**, not canonical
publication. The host verifies artifact digest/length/provenance and epochs,
then commits a canonical receipt. Replies/events bind every identity and request
digest; stale process/store/epoch/call results cannot settle newer work.
Configuration/grant/cancel/deletion revisions are checked at return/publication,
not trusted because Python echoed them. Worker inputs contain no secret values.

Use authenticated inherited pipes/owned loopback channels with per-launch
nonlogged tokens, exact process handshake and explicit owned roots. Proposed
bounds: 1 MiB frame, 16 data requests in flight, 64 queued, eight reserved control
slots; two document tasks, one memory task and one maintenance task initially.
These are provisional engineering defaults to calibrate, negotiated downward,
never permission
to drop replies. Separate control/reply capacity keeps cancel/revoke/lease/query
and Mem0 reverse-dispatch callbacks alive when data work blocks. Reject overload
before effects. Progress can coalesce; terminal replies cannot.

Preserve the existing **64 MiB** input limit. Do not base64 a 64 MiB file into
IPC. A host-issued artifact handle binds profile, store/process, retention,
rights, immutable hash/size, revision, owned native file identity or RAM segment,
expiry and permitted ranges. No caller path traversal/arbitrary URL handle.
Stream transfers in at most 256 KiB chunks with offsets, total/hash and bounded
credits; staged output is paginated similarly. Temporary artifacts never spill.
Saved outputs require reservations before allocation and publication intent
before original body I/O. Cancel leaves staging owned until settled cleanup;
process death retains uncertain intent, never a ready revision.

Preserve `/api/v1` status/error shapes and `started/progress/sources/delta/completed`
stream semantics, ordering/run identity and terminal failure/cancel events.
Reconnection reads state/receipt; it does not restart generation. Observer
timeout, disconnect, Stop acceptance and actual settlement differ. Partial
worker failure preserves the previous index, original and usable generation
checkpoint. Rebind Study/Test guard on every commit; Python ContextVars cannot
cross the process Seam.
Saved observer disconnect does not cancel execution. Temporary owning-client
disconnect follows section 7's cancellation/discard and Save ordering; neither
action means that workers/remote effects have already settled.

The worker command union is closed/versioned: `document.extract/chunk`,
`embedding.embed`, `library.query/stage/remove/maintain`,
`memory.extract/recall/reconcile/purge`, `artifact.read`,
`native.inspect/publish/dispose`, `credential.connect/refresh/forget`,
`transport.send/cancel` and `worker.settle`. Each expands to explicit dotted
names with command-specific schema/result tags; no arbitrary Python method,
shell command or SQL. Broker connection operations are direct-command-only;
model tools cannot mint worker authority. Engine mutations affect only staged/
derived state; final canonical publication belongs to the one writer.

The public deep Module Interface is `admit(command, expected, key)`,
`observe(operation, afterEvent)`, `decide(pendingPermission, decision)` and
`cancel(operation, expectedEpoch)`, plus deterministic domain reads/commands
already exposed by `/api/v1`. Admission returns identities, never credentials;
observation cannot authorise execution. Preserve typed chat/project/test/content
references, exact event ordering and old error codes through compatibility
Adapters. Schema negotiation rejects unsupported versions before effects.

## 6. Dispatch, accounts, secrets and revocation

One authority admits **all** model purposes. During migration it is Python;
at handoff TS `dispatch/`. Cover `explain`, `case-discuss`, `case-image-discuss`,
`evidence-review`, `generated-practice`, `fictional-test`, `test-import`,
`memory-extraction`, `compaction`, `summary`, `test-result-narrative`,
`daily_suggestions`, `updates-digest`, `title`; include root, continuation, child,
repair, recovery and scheduled request kinds. Nightly reuses generated-practice,
not a second role/scheduler.

Final configuration **positively enables memory extraction** from eligible
committed learning, educational summaries/compaction, generation/import/
fictionalisation, result narrative, Home and Updates roles with nonzero bounded
budgets. This is implementation scope, not current wiring. Title is optional
cosmetic work with zero budget until enabled; summary-repair shares compaction
budget. Initial provisional default: two remote attempts profile-wide, one child
per parent, depth one, eight dispatches per interactive parent including
continuations/children/summary. Generation retains explicit batch budgets;
10/20 budgets must cover validated five-item batches and review calls rather
than inherit an insufficient interactive cap. Exceeding a bound returns a
recoverable checkpoint, never an unbounded continuation.

Before each network admission resolve chosen subscription/account, allowlisted
model, endpoint/protocol, actual tool/vision entitlement, final serialized
request counter, output/reserve/window limits, role/parent permit and current
grants/assessment/deletion/cancel epochs. Catalogue display does not prove account
access. Route records bind protocol, counter implementation/version, endpoint
and qualification evidence. Current desktop 49,152/4,096/57,344 units are
conservative policy, not verified capacities. Unknown tool/vision/context
capability refuses that operation truthfully. No silent subscription/model
change, hidden paid generative fallback, ambient auth or runtime acquisition.
Automatic selection stays within configured allowed/available models in the
chosen subscription; a pinned run cannot silently switch after failure.
Native automatic retry, WebSocket fallback, opaque continuation and unqualified
compaction stay closed.

TS owns route metadata/grants; Python's protected broker retains DPAPI material
and existing login/refresh/native Windows routines. Connect/cancel/refresh/
disconnect use credential handles. Python transports exact admitted requests
with an opaque one-use permit and no independent route selection; it cannot
mint permits or infer from a helper callback. Credentials stay out of renderer,
manifests, prompts, transcripts, logs and learning exports; private broker memory/
DPAPI only. Auth handoffs are explicit commands, not startup probes. Transfer
preserves credential namespace/references without exporting secrets.

Dispatch reservation and final admission are distinct local transactions.
The **final admission commit** records attempt/debit and current grant epoch:
the linearization point against revocation. Revocation commits a newer epoch,
closes new admissions, narrows queued/running children/MCP/permissions and fences
publication. Previously admitted remote effects cannot be unsent. Retain
uncertain debits/effects until reconciled; no refund of unknown charges or
resend after timeout. Transport executes outside transactions; signals are
best effort after admission.

Optional retrieval profiles require saved+enabled+selected state, exact
endpoint/credential revisions, per-attempt request/credit and daily/operation
ceilings. Durable reservations count uncertain calls against ceilings;
settlement records known usage. No implicit rotation. Native MCP reconnect/
expiry [U6], permission “always” [U7] and inherited child permissions [U8] require
app checks before invocation/return. Native saved permission cannot override
current application revocation.

### Native MCP transport and authentication bridge

Native OpenCode retains MCP protocol messages, client/tool/resource discovery,
sessions, pending approvals and execution lifecycle. The proposed
`BrokerMcpTransport` is a credential-free native transport adapter backed by the
owned Python broker, not another MCP client/engine. The broker performs bounded
HTTP/SSE or owned stdio byte transport; native code still handles MCP semantics.
Native configuration contains endpoint and credential **references**, never
bearer headers/tokens. Disable native credential persistence and the stock OAuth
provider for Renulus connections; OAuth discovery, explicit login/refresh and
DPAPI persistence live in Python. Responses strip auth headers/tokens before
returning protocol data to Node. Do not start another login from model execution.

The pin constructs StreamableHTTP transport and captures native fetch internally
[U18], [U19]; replacing generative `RequestExecutor` or wrapping `callTool` is
insufficient. BF03 first proves whether the pinned MCP configuration/embedding
seams can supply the broker transport and auth callbacks without source changes.
If not, add only a narrow injectable transport/auth factory at native client
construction, under section 3's provenance/test/removal process. There is no
assumption that this factory already exists. Stock direct-fetch/native-token
paths stay closed for Renulus MCP until the bridge passes.

Connection-scoped authority admits initialize, catalog/resource listing,
event-listen renewal, explicit OAuth discovery/refresh, reconnect and termination;
it binds selected server/endpoint/schema/credential/config/grant revisions and
bounded lifetime/bytes/retries. Tool/resource work additionally needs the
operation/parent/retention/assessment permit. Each outgoing attempt, retry,
redirect or expiry refresh passes current admission; the native retry loop cannot
reuse an old permit. Streaming inbound results are fenced at publication.
Revocation denies new work/reconnect/refresh, cancels owned streams and records
uncertain effects. A separate one-use cleanup-only permit may send termination
to the already-admitted session endpoint; it cannot list/call/reconnect or restore
grants. Unknown termination remains cleanup debt, never restored authority.

Local stdio servers are launched by the Python broker with bounded frames,
minimal explicit environment and owned descendant settlement; no generative
subscription secrets are forwarded. Arbitrary local executables belong to the
trusted developer execution exception in section 4, not the doctor default.
Any separately authorised server secret stays broker/owned-server private and
does not enter native OpenCode credentials, learning storage or transcripts.
BF03's synthetic authenticated server exercises initialize, list, call, streamed
reply, token expiry/refresh, schema change, pending “always”, revocation during
reconnect and finalizer termination. Inspect native stores/logs for token
sentinels and prove no direct native fetch path or stale permit survives.

## 7. Transcript, memory, retention and long context

OpenCode is the only migrated message writer. SQLite keeps typed conversation
metadata and native session/message references, not writable message copies.
Legacy messages remain immutable compatibility input; migration imports/maps
once with digest receipt/tombstone refusal. Events/Finder projections are
rebuildable, erasure-aware observations.

BF02 fixes Finder through bounded literal native-message search/resolution by
the owning host, combining canonical metadata with native message IDs and
epoch-bound cursors. Find native-only text after restart; omit deleted/temporary/
ineligible text; respect project moves/Archive/Test. No second authoritative
transcript. Any accelerated search projection needs complete invalidation;
initial bounded host query suffices.

Saved chats/cases are default; Archive changes lifecycle, not retention or memory
eligibility. Saved case payloads do not become facts merely by being saved.
Required-file/memory pins hold canonical IDs, versions/hashes, rights/relevance,
not duplicated documents. Resolve them against current source/fact/support
revisions immediately before dispatch.

Mem0/local Qdrant remains the learner-memory engine through the attributed
Hermes OSSBackend; FastEmbed and canonical facts retain their roles. Do not
replace extraction/recall with custom SQL memory. Capture starts from eligible
committed answer/evidence receipts, resolved outside transactions. Publication
checks ancestry/suppression locally. Record passage→tool result→assistant
segment→summary/child→fact support edges. Correction/delete invalidates transitive
inference support, context, personalisation, pending extraction and engine
history; edited/independently supported facts survive under ownership rules.
Preserve explicit delete-related-learning and unavailable-source markers.
Historical messages can remain visible while ineligible for inference. Echoed
assistant/summary/child text cannot recapture suppressed facts. Reindex/Mem0
history purge consumes tombstones before readiness.
Mem0 may stage derived vectors/history before host acceptance; their existence
never makes a fact eligible. Recall filters against accepted canonical ID/revision
and support state; rejected/stale extraction stages are purged or kept fenced
with cleanup debt. The host cannot accept a raw engine ID as canonical authority.

Temporary execution uses an isolated **volatile runtime graph**: database,
inbox/jobs, descendants, attachments/decoders, summaries, tool spills, events,
prompts, logs and worker artifacts. A different Location/name is not a separate
database [U1], [U9]. No durable IDs, payload hashes, crash dumps or export references
may reconstruct temporary content. Parser paths writing scratch images remain
unavailable in temporary mode until adapted/proved safe. OCR and model image
interpretation remain separate capabilities.

**Temporary disconnect:** preserve H21 cancellation/discard. An abnormal loss
of the owning client during unsaved execution closes family admission and
publication, advances its cancellation epoch, signals all native children,
workers and transports, retains ownership through actual settlement or explicit
uncertainty, then discards volatile execution artifacts. It cannot keep issuing
continuations merely because its stores are in RAM. Normal successful terminal
stream closure is not an abnormal disconnect; the still-open temporary view can
continue. Closing/discarding that view ends its volatile family. Saved execution
continues after observer detachment and is reconciled on reconnect.

Explicit Save freezes the whole temporary family, settles work, stages a durable
graph with fresh IDs/mappings/originals, validates rights/epochs, then commits
canonical promotion intent. Native copy/canonical selection use idempotent outbox/
reconciliation, not cross-database atomicity. Until final activation, staging is
hidden from reads/Finder/inference/capture/exports. Activate the complete mapping
once, then retire RAM. Failure retains RAM while alive and never reports saved;
restart removes/reconciles orphan staging without reconstructing temporary input.
Fictionalisation instead promotes only the validated fictional artifact under
DC18, never source hashes/raw-case job IDs.

Save versus disconnect uses one serialized family-control boundary. If saved
activation has committed first, disconnect only detaches from that saved result;
return its committed reference on reconnect. If cancellation wins first, no
later promotion may activate; hidden durable staging is retired after settlement.
Before any Save request this control state is volatile. Once explicit Save has
admitted a promotion intent, cancellation and activation use the same local
authority/epoch compare-and-set receipt, with native copy outside the transaction.
An in-flight Save is not implicit permission to continue after cancellation.
No durable temporary raw payload/hash is added just to record a disconnect.

H10 uses native hooks with versioned educational prompts/skills, preserving
fuller legacy teaching. Prompts express pedagogy; code enforces evidence/rights/
retention/assessment. Reinject current system/skill/pin manifests, exact recent
exchanges, complete tool pairs and media markers; preserve unresolved calls.
Older exact ranges stay available after compaction. Summaries carry covered
message IDs, source/fact revisions and validation receipt; never independent
truth. Empty/failed/stale summary blocks compaction; stock coding summaries and
opaque provider checkpoints stay disabled.

Requested decimal profiles are **128,000 and 256,000 tokens**; existing
131,072/262,144 policy fields need explicit compatibility mapping, not silent
equivalence. Effective capacity is minimum requested/verified route-account
limit. Count final instructions, schemas, history, passages, memory, media,
output and reserve after transforms. Scientific evidence and learner memory
have separate allocations. Saturation, route changes, older-history expansion
and instruction reacquisition recheck the same final counter. Unsupported 256K
stays unavailable; qualification proves supported capacity, not an invented limit.
The proposed next configuration schema stores `requested_decimal_tokens`.
Its read-only conversion preview maps legacy 131,072→128,000 and
262,144→256,000, preserves smaller custom ceilings, and leaves existing input/
output caps unchanged. Unknown/custom larger values require explicit validation,
never automatic expansion. Old schema readers retain their original semantics.

## 8. Documents, originals, rights and currentness

Keep [helper requirements](../../packaging/runtime/requirements-helpers.txt):
Docling 2.133.0, docling-core 2.99.0, FastEmbed 0.8.1, LanceDB 0.39.0,
mem0ai 2.2.1, qdrant-client 1.19.1 and existing transitive/helper artifacts.
BGE-small-en-v1.5 remains 384 dimensions, 512-token model limit/480-token chunks;
preserve hashes/tokenizer/OCR assets. No EmbeddingGemma migration. Docling/
HybridChunker retains page/item/section/bounding-box/table provenance; LanceDB
hybrid retrieval retains canonical revision prefilters.

Every required C format has an in-app reader independent of extraction:

| Format | Reader and extraction obligation |
| --- | --- |
| PDF | Page/zoom/search/selection/cited jump; physical vs printed pages; scanned text only after OCR. |
| DOCX | Headings/lists/tables/images/search/selection; paragraph/section pins, no invented pages. |
| CSV | Bounded rows/delimiter/encoding/horizontal scroll; literal values/row-column pins, no formula execution. |
| XLSX | Sheets/displayed values/cell-range pins; no macros/formulas, missing cached values explicit. |
| Markdown | Sanitised rendered headings/code/tables; source/section pins. |
| HTML | Inert isolated content/mediated links; no scripts/app bridge/automatic remote resources. |
| XML | Escaped text/tree/search/selection; no entities/network, generic text extraction only. |
| PNG/JPEG/TIFF | Fit/zoom/pan/original, multi-page TIFF; OCR and selected-model vision separately qualified. |

Preserve existing TXT/PPTX without adding EPUB promises. Distinguish preview,
extraction/index ready, restricted, missing/corrupt and unsupported states.
Passage-to-draft retains text and requires Send; preview implies neither model
rights nor Library import. Inert documents cannot acquire authenticated app
authority through same-origin links/forms/resources. Original Open/Save remains
direct mediated commands, not raw filesystem tools.

[SOURCES](../SOURCES.md) remains the acquisition/currentness register.
Per-version/per-asset records retain licence/evidence, access, publication/check
dates, final/draft/replaced/retracted, corrigenda/chapter replacements, permitted
display/local processing/model input/adaptation/distribution and attribution.
Unknown operations remain not-verified; authorised reading/import routes stay
usable. Discovery is not passage evidence. Failed checks never advance currency;
a newer draft never replaces a final.

Use [October 26 licensing research](../research/2026-10-26-content-licensing-delivery-options.md)
as dated evidence: original content/eligible exact licensed assets, link
catalogues and selected authorised personal imports have distinct operation
rights. ERA downloading is confirmed direction, not a blanket AI/redistribution
grant. Drive possession grants neither rights nor crawling. MIT, original CC BY
4.0 and third-party exclusions/notices stay separate. No new cards, shelf
acquisition or authoring gate is added. Reserved assessment items stay outside
teaching retrieval/generation regardless of public content licence.

## 9. Complete learning flows and assessment invariants

Move every producer to native execution: Explain/guided/follow-up, saved/
temporary case/image discussion, generated practice/saved generation,
fictional tests, imported refinement, result narrative, Home, nightly and
Updates digest. Direct Library/Notes/Memory/plans/scoring work without inference.
Offline/account unavailable/no-data leaves reading, history, manual planning
and reviewed tests usable.

5/10/20 generation uses validated batches of five, immutable checkpoints,
deduplicated publication and explicit shorter recovery. Requested count differs
from accepted count. Cancel/refusal preserves validated drafts. Origin/review
quality/Study-Test mode are separate; generated/imported/fictional work never
joins reviewed cohorts by choosing Test. Import preserves terms/hash/candidate
edits and deliberate missing-key resolution.

Study commits only on Submit answer; record help/family exposure before
returning assistance. Test autosaves drafts and submits the whole attempt
atomically after latest displayed choices are durable. Test cannot pause;
profile-wide assistance fence survives navigation/restart and blocks chat,
sources, Memory, Notes, Finder, progress snippets, children, MCP and stale replay.
Cancel/resolve in-flight help at Test start. Neutral recovery/settings and
Question seems wrong remain available without keys.

Scores/unanswered/excluded/evidence are deterministic; narrative cannot alter
them. Pin immutable items/keys; withdrawal permits terminal results with affected
items excluded under C rules, never rewrites old results. Persist start/deadline/
high-water; reconcile reads/writes/sleep/reopen using pre-deadline durable drafts.
Closed-app expiry finalises once on reopen without a service. Timed Study stays
pauseable and never auto-commits pending answers. Finish active Test before
backup/export/restore activation under C policy.

Home uses a dated bundle, five per category, exact saved-five Quick practice,
manual preferences/goals and evidenced progress; no mastery from chat counts.
Nightly is opt-in/app-running, one local-date claim/bounded catch-up; Off/Stop/
restore interrupts publication. Updates keeps source review, corrections/
retractions, affected-content outbox and dated digest provenance. Digest never
confers source-review/currentness authority.

## 10. Reliability, storage and paired recovery

### Budget and native ownership

Requested envelope: **50–150 GB**, not an approved partition. Proposed default:
**100 decimal GB** across managed runtime/helpers, originals, canonical/native
stores, indexes/history, staging/cache and snapshots. Soft allocations: 45 GB
protected records/originals, 15 GB derived indexes, 5 GB helpers/runtime, 10 GB
backups, 5 GB disposable cache, 20 GB peak reserve. These are **unconfirmed,
uncalibrated engineering defaults**; measure logical/allocated/unique/peak
bytes before acceptance. Preserve over-budget existing data and refuse growth.
External collections/development archives are separately reported, never silently
deleted or treated as free app capacity.

Reserve peak before copy/extraction/append/FTS/rebuild/compaction/snapshot.
Charge staging, outstanding cleanup, concurrent workers, Lance versions, Mem0
history and failed originals. Enforce app ceiling and target-volume free space;
retain the **12 GiB floor**. Protected originals/records/memory are not evicted.
Only declared disposable caches may be reclaimed automatically. Offer explicit
relocation/export/user deletion if protected data cannot fit; 50 GB may refuse
a large import rather than promise fit.

Retain [#25/#26 invariants](../implementation/library-index-maintenance.md):
intent before original allocation/body I/O; atomic no-replace publication; exact
Windows identity/no-follow/ancestor/named-stream handling; retained profile/
generation owners; no recursive pathname deletion/raw SDK opener. Imported
native primitive does not mean full #27 adoption. Keep 64 MiB chunked retained
publication. Long paths/aliases/cleanup need actual Windows proof; uncertainty
retains debt.

LanceDB keeps FTS once (`replace=False`), append batches/default hybrid query,
no `fast_search()` skipping unindexed fragments. Coalesce at 32 batches/64 MiB
estimated growth/idle; preserve dirty sequence/removal fence/backoff (one to
300 seconds). Use public `optimize(cleanup_older_than=timedelta(0),
delete_unverified=False)` under owned snapshot/lifetime contract, never delete
internal files. Forecasts are not measured peak guarantees. Failed compaction
preserves ready selector plus maintenance/retirement/original debt. Fail-closed
retirement is not reclamation; governed cleanup must pass before claiming
bounded sustained storage. Mem0/Qdrant/history purges require owned settlement
and measurable tombstone application.

#27 development accounting, #28 shared-helper publication/guardians and #29
development automatic retention remain separately deferred. Product reservations
here do not adopt/close those campaigns.

### Failure and complete-generation recovery

Leases outlive observer/fiber timeouts. Keep reply pumps alive through cancel/
finalizers; release stores only after actual settlement. Process death needs
owned-process proof/reconciliation, not TTL. At-least-once native recovery [U9]
stays held until app-authorised replay; zero budget terminalises, not pauses.
Uncertain effects remain uncertain; local commits reconcile by receipt/outbox.
Low space gives waiting-space/backoff without losing originals/active revision/
validated batches. Restore never starts provider work.

H18 extends `storage/recovery.py`, `recovery_records.py`, `attachment_cleanup.py`
and paired `harness/1`. Close admission logically, drain remote work **before**
engine guards, then snapshot both actual stores, originals, immutable versions,
schema inventory, plugin artifacts/effective selector and hashes as one
generation. Validate/checkpoint stores/flush manifests; publish complete selection
last. No cross-database atomicity claim. Missing/mismatched members refuse activation.

**Ordinary restore remains additive**, matching the existing canonical restore
contract. Build a candidate from a settled copy of the **current** complete
generation plus eligible incoming records/graphs, not by replacing the current
runtime with an older snapshot. Current mutable identities/metadata win;
incoming-only canonical rows and native nodes are added after current deletion,
correction and rights filters. Immutable published content/original/message
identity with different bytes or incompatible parent/tool relations is a hard
conflict: refuse activation and leave the current selector untouched. Do not
silently choose a version or drop a newer conversation/attempt.

The native owner imports eligible incoming-only session/message/tool/child graph
closure and supplies a stable incoming-store→candidate mapping. Rewrite every
canonical native reference/support/receipt through that mapping before candidate
validation, preserving product IDs and current references. Reuse equal immutable
nodes; current mutable session metadata, lifecycle and ordering frontiers win.
Merge missing message nodes only where the native owner validates a complete
consistent order and all parent/tool-call/result/child relations. Incompatible
branches/order refuse the preview; they are not flattened or partially restored.
Summary/checkpoint/Finder projections are derived: retain only validated eligible
coverage or rebuild them, without inference, from merged history. Incoming live
claims/permissions/execution jobs never resume; imported history is inert.

Preview retained/current-only/new/excluded/conflicting counts, mapped references
and complete graph/original availability. Verify closure for both current and
incoming canonical→native links before selection. The current H06 legacy-pair
transfer is not a full native graph importer; BF07/P08 must prove the owner seam
for this merge (or a narrow provenance-tracked injection if unavailable).
Never combine a canonical merge with an old replacement runtime. Whole-generation
rollback is a distinct recovery action with compatibility/no-newer-record-loss
rules; ordinary Restore does not implicitly select rollback semantics.

Restore previews read-only: IDs/counts/relations, original availability/hashes,
schema/authority compatibility, deletion-frontier effects and space. Apply current
typed tombstones/suppressions/corrections/grant revocations before transcripts,
recent tails, children, summaries, indexes/Finder/personalisation. Preserve
independent edited/multi-source facts/shared originals; owned attachment deletion
needs real attachment tombstones. Keep minimal nonreconstructing receipt IDs
after payload erasure. Purge engine history/invalidate readiness; restored sources
receive explicit-capture barriers. No delayed/global Retry may infer from
restored evidence; explicit Capture revalidates/consumes one barrier.

Same-profile recovery requires current deletion frontier. Missing frontier
quarantines affected data from indexing/inference/recovery. A fresh old-backup
restore cannot know later deletions; disclose this limit. Reconstruct local
generations/leases/maintenance journals, never import live claims. Learning
snapshots exclude credentials; missing protected handles require reconnection.
Rollback restores a complete compatible generation, reapplies current frontiers/
grants and refuses downgrades losing newer records. A single-store backup cannot
roll back native conversations.

## 11. Ordered implementation waves and ownership

**BF IDs** group delivery; they do not replace H/DC tickets. Complete waves
sequentially, one reviewed integrated slice at a time. Before implementation
worktrees, commit agreed spec and source/contracts baseline: uncommitted edits
do not copy. Use `codex/` branches/owned synthetic profiles. This spec task
creates no worktree. Preserve isolated H07/other WIP; reconcile through its owner.

F0 owns native host/provider/broker/lifecycle; M1 Learn; M2 Knowledge; M3 Cases;
M4 Assessment; M5 Memory; M6 Study/Home; M7 Updates; M8 Content. Only integrator
edits shared contracts/migrations/canonical transactions/facade/Electron startup/
root manifests/locks/cross-module fixtures; owners propose narrow prerequisites.

Each row requires (a) connected compatibility flow with Python sole owner and
(b) final TS target flow on a TS-owned synthetic profile. Record source/contract
hashes/read-only populated migration preview. Production-compatible profiles
remain Python-owned until BF08; failed target proof leaves ownership unchanged.

| Wave / IDs and dependencies | Existing → proposed target paths / owner | Acceptance, failure and recovery |
| --- | --- | --- |
| **BF00 Baseline/contracts**; H00/H01/H24; DC01–03/DC20 | Integrator `packages/contracts/`, `runtime/renulus/storage/` → `packages/backend/src/{contracts,storage,http}/`; F0 host | Freeze identities/outcomes/schema preview/closed cohort. Account-free start/read old records; reject stale owner/schema; crash prepared selection/recover old owner. Reproduce lease/settlement first. |
| **BF01 Composition/dispatch** after BF00; H03/H04/H24; DC02/DC10 | F0 `runtime/renulus/runtime/harness_configuration.py`, gateway/provider/auth, `packages/harness/src/host.ts` → backend `host/dispatch/plugins/workers/` | Selected Explain → native Library tool → receipt; edit/disable/restart/observe registry. Failed candidate/restored old bytes/queued revoke/broker death stay held, no redispatch. Account/counters separate. |
| **BF02 Saved/history/Library/memory** after BF01; H02/H05/H06; DC04/05/07–11 | M1/M3 conversation seams, M2 knowledge/reader/note, M5 memory, integrator `storage/search.py` → backend `domain/`, Python workers | Import/read/cite → saved chat → capture → correct/delete → native Finder/reopen; immediate Archive/project unlink/all reader parity. Crash/delete during extraction/native lookup/Mem0 callback cannot publish stale data; retry reconciles cleanup/barriers. |
| **BF03 Children/skills/MCP/developer tools** after BF02; H07/H08/H09; DC04/DC10 | F0 `packages/harness/src/child-authority.ts`, native hooks/config → native plugins/backend grants and broker transport | Integrate H07; child/curated skill/authenticated MCP → parent. Prove every native developer family; Code Mode per-fetch mediation; MCP full transport/auth bridge; owned browser attachment/tunnel lease, endpoint/byte enforcement, delayed traffic/streams/revoke/stale attach; trusted shell/local-server descendants. Revoke pending “always”/inherited grants, change endpoint/schema, Stop/closed-death/reopen; no unmediated transport or premature settlement. |
| **BF04 Temporary/context/images** after BF03; H21 then H10; DC04/07/08 | M1/M3 temporary/Save, F0 context/media, M5 ancestry → volatile graph/context/retention modules | Temporary PDF/image case → exact history → Save/reopen; sentinel absent before Save. Mid-flight disconnect with child/worker work cancels/settles/discards; race disconnect against Save on both activation sides. Saved detach continues. Saturate qualified 128K/256K/reinject old detail; failed summary/Save/crash keeps correct visibility/no raw fictionalisation residue. |
| **BF05 Assessments/generation/import** after BF04; H12→H13/H14/H22/H23, H00 consumed; DC12–18 | M4 generation/import/fictionalisation/attempt services, M8 keys/versions → backend assessment/content; Python extraction | Every origin → immutable Ready → whole Study/help/timed Test/result. 5/10/20 lost ACK/cancel/reopen/shorter acceptance, ambiguity/privacy review/deadline/late-help fences. Local scoring survives quota/offline. |
| **BF06 Home/nightly/Updates** after BF05; H15/H16/H17; DC06/09/10/19 | M6 `home_service.py`, `nightly_service.py`; M7 `updates/service.py` → backend study/updates | Suggestions → exact-five Study; opt-in occurrence → saved set; correction → source → digest. Off/revoke/restore/timezone/restart/failed check preserves one occurrence/manual overrides/honest currentness. |
| **BF07 Complete recovery/storage** after BF06; H18; DC02/DC20, #25/#26 | Integrator recovery/frontiers/transactions, M2/M5 engines → backend storage/owned Python cleanup | Paired G0 snapshot → newer M2/new conversation D/attempt A → additive restore preserves all current work and eligible incoming-only graphs. Conflicting native identity refuses selection; verify mappings/tool-child closure/reopen without inference. Also delete/correct/frontiers, low space/locked stream/engine death/incomplete snapshot; preserve originals/debt and measure growth/rebuild peaks. |
| **BF08 Authority/package cutover** after BF07; H20/DC21 | Integrator/F0 Electron backend/`packaging/`, Python server/harness main → Node main/worker main | Profile-wide writer+dispatch handoff/complete rollback. Matching bundle/populated migration/auth/dialogs/shortcut/reopen. Crash selector boundaries; no Python canonical connection/developer PATH/runtime acquisition/data or grant resurrection. |

H11 adds optional derived history only after extended H18; H19 stays outside
default allowlist. All H00–H24/DC01–DC21 are consumed, retained or explicitly
dispositioned. This is conservative integration order, not reopening accepted
DC implementation or closing account/package gaps by declaration.

## 12. Acceptance matrix and falsifiable completion

Evidence classes: **C** contract/synthetic; **E** actual selected engines/native;
**A** hidden owned app; **L** authorised real selected account; **W** matching
packaged Windows. C never labels L/W complete. Record source/cohort/config/tool/
model/counter/fixture hashes, failures and scope. No incidental provider calls.

| Journey/fault | Evidence and pass condition |
| --- | --- |
| Breadth | C/E/A across electrolytes/acid–base, AKI/critical care, CKD/diabetes, glomerular disease and transplantation; text/PDF/table/image, no single-topic gate. |
| Tools/plugins | C/E/A final registry parity, add/edit/disable/remove/dependency refusal, old-byte fallback/failed cleanup/restart; no ambient tools/packages/accounts. |
| Accounts/counters | C every purpose/request kind; L exact selected routes for text/tools/image where supported/supported context. Test advertised capabilities for each available selected model; unqualified/unavailable remains labelled. Preserve historical Go/Sol limits. |
| Local/offline/no data | E/A/W cold start without account/network: readers/history/manual Memory/Notes/plans/reviewed scoring/Settings work; generation/retrieval fails without switch. |
| Memory/lineage | E Mem0/Qdrant/FastEmbed/LanceDB; correction/delete/restore/echo/child/summary races do not recapture. Positive default capture/relevant recall across domains. |
| Temporary/Save | C/E/A disk/log/export/snapshot sentinel covers full graph/children/media/spills/jobs; disconnect/cancel/crash leaves no raw payload after actual settlement. Save-vs-disconnect both orderings; Save once/failed staging hidden/fictional artifact has no source reconstructor. Saved detach remains independent. |
| Assessment | C/E/A/W all origins/cohorts/reserved isolation, Study exposure, Test latest-draft atomic commit/late fence, sleep/closed-app expiry/withdrawal/provider failure. |
| Queues/Stop/crash | C/E/A overload before effects, retained leases/reverse callback pump/cancel vs settle, host/Python/renderer death/uncertain debit; no duplicate attempt. |
| Storage/native IO | E/W pinned engines/Windows handles/long paths/aliases/streams; logical/allocated/unique/peak, appended keyword/vector freshness, repeated maintenance/low space/failed retirement. Protected originals/records intact. |
| Migration/recovery | C/E/A/W populated schema-1/2 JSON/ZIP, old→new writer, paired backup/delete/additive restore/reopen/missing frontiers/rollback. Diverged current/incoming history preserves newer work plus incoming-only graphs; identity conflict leaves selector unchanged. Exact originals/native history/Finder, no resumed inference/capture. |
| Windows/handoffs | W unsigned current-PC: bundled Node/Python/helpers, no developer PATH, exact artifact, shortcut/start/close/reopen/install/recovery. Physical auth/dialog/original handoffs/accessibility have scoped native proof. |

Interactive checks use only [APP_CONTROL](../implementation/APP_CONTROL.md),
hidden nonfocusable windows/owned synthetic backend/profile. No Computer Use,
OS input, focus/bringToFront or owner's profile. Hidden upload does not prove
physical dialogs/auth/accessibility. No mandatory signing/clean VM/external panel.

**Ready means all of the following have evidence:**

- Every required catalogue row has a connected journey including local failure/
  recovery; no producer silently bypasses dispatch.
- TS exclusively owns selected-profile canonical transactions/config/dispatch;
  Python is engine/broker-only; native OpenCode owns execution/messages.
- Effective plugins/tools/prompts match selected hashes; disable/revoke fences
  queued/running authority and retains uncertain effects visibly.
- Positive memory capture, eligible exact history, volatile temporary graph and
  deletion frontiers survive paired restore.
- Assessment/timers/every C reader/5/10/20/Home/nightly/Updates meet H/DC contracts
  across five domains.
- Account claims name real route/counter/tool/image/window. Required selected-
  subscription text/tool capability has live proof; unsupported is not a pass.
- Sustained measured storage/peak reservations satisfy selected 50–150 GB budget,
  preserving protected data and reporting cleanup.
- Matching self-contained current-PC build passes populated handoff, physical
  acceptance and complete-generation recovery within recorded scope.

A failed item leaves its H/BF obligation open. Spec review establishes only an
implementation baseline.

## 13. Decision, review and proof-obligation register

### Selected decisions

| ID | Decision/default and reason | Proof |
| --- | --- | --- |
| D01 | Final TS transaction module; Python sole owner until profile-wide handoff. Preserves cross-domain atomicity with incrementally verified target slices. | BF00/BF07/BF08 parity/selector crash/rollback. |
| D02 | Native plugins/Effect scopes, restart-based immutable activation: SDK lacks unregister and reload can restore old bytes. | BF01 registry/hash/removal [U3], [U4], [U13]. |
| D03 | Native execution/jobs/messages/children/context/MCP, selected Python engines. | BF02–BF06 complete producer proofs. |
| D04 | Required doctor tools; raw coding/browser optional default Off, an engineering default. | Final/indirect catalog and child-grant checks. |
| D05 | Proposed 100 GB/measured allocations, 64 MiB artifacts/bounded IPC. | BF07 peak/growth calibration; adjust with rationale before release. |

### Open implementation proofs, with fixed outcomes

| ID | Concrete proof owed | Failure disposition |
| --- | --- | --- |
| P01 | Pin-supported candidate identity/final registry/omission on restart. | Hold activation; reproduce supported-Seam failure before patch proposal. |
| P02 | Child grant intersection/rehydration; MCP full broker transport/auth; Code Mode fetch replacement; browser attachment/network lease, target/byte checks, stream closure/revoke/stale reattach; trusted developer descendants. | Deny mediated capability until interceptable; bounded seam investigation then narrow injection patch if needed. State TCP endpoint vs URL granularity and trusted page lifetime; never claim arbitrary OS-code confinement. |
| P03 | Volatile database/tool/media/summary graph/guarded promotion. | Temporary capability unavailable until no-spill proof; saved routes preserved. |
| P04 | Educational summary/exact history hooks, production counters/qualified capacities. | Refuse unsupported compaction/window; readable exact history preserved. |
| P05 | H06 immediate-Archive hidden closure, integrated H07/native-message Finder. | H criteria remain open; isolated WIP preserved. |
| P06 | Go/tool/image/counter qualification, reproducible closed cohort/package/relocation/notices. | Unqualified label/no fallback; H03/H20 open. |
| P07 | Sustained growth/retirement, governed original cleanup, long paths/worker settlement. | Preserve owners/originals/debt, refuse unsafe growth/release claim. |
| P08 | TS cross-domain parity, paired handoff/frontiers and additive native-graph merge with current precedence, mapped closure and conflict refusal. | Python authority until BF08; no partial writer migration or old-runtime replacement during additive restore. |

These are bounded implementation experiments, not architecture menus or evidence
of success. They add no content-authoring campaign.

### Sequential independent review record

| Round | State | Parent record required before approval |
| --- | --- | --- |
| Wave 1 audit | Completed, Sol/xhigh; facts incorporated. | Audited source hash/evidence limits retained. |
| Wave 2 design | Completed, Sol/xhigh; not self-approved. | Draft passed to independent reviews; parent consolidated required developer delivery and qualified Finder coverage. |
| Adversarial 1 | Completed, Astra/xhigh; changes required: A01/A02 high, A03 medium. | Reviewed `43591ed234e75783008e412499965c99876739d1ca25b7233de676b5dcd9f456`; all three accepted and repaired below. |
| Adversarial 2 | Completed, Sol/xhigh; changes required: B01 high, B02 medium; A repairs accepted at specification level. | Reviewed `e0ed067e2e0b7f785d76f49f9fcbd3aeb1a78e4d725eb799d9b8e121b5f64db5`; both accepted and repaired below. |
| Final re-review 1 | Completed, Astra/xhigh; changes required: F01 high; A01–A03/B01–B02 accepted as repaired. | Reviewed `edfeeb6ae96ae3bdc2bdb204bcaf28ce11156a814f9079c891e3edc02e3f8484`; F01 accepted/repaired below. |
| Final re-review 2 | Completed, fresh Sol/xhigh; **approved as an implementation specification baseline only; zero material findings**. | Reviewed `bb2e4f18638ec5cd41df48629b978261a069a401071bff8c0becdb1a3a617fd8`; independently accepted all six repairs. P01–P08 remain open implementation gates. |

Six sequential delegated waves completed: source audit, design, adversarial A,
adversarial B, final re-review 1 and fresh final re-review 2. The register below
records every material finding; none was rejected or silently deferred. Ignored
wave notes are supporting inputs, not competing public specifications.

The final reviewer approved the exact bytes named above. Closeout changed only
this header/review record; the reviewed body digest remains
`af556bac2647e5ae3b8d85472ecaef3d236719c524ad84f6c84af5e6be18a10b`.
Reproduce it by decoding UTF-8, removing a leading BOM, normalising CRLF to LF,
then concatenating section 1 through immediately before this review-record
heading with section 14 through EOF, without a separator, and hashing UTF-8
bytes with SHA-256. This includes selected decisions/open proof requirements
but excludes review metadata. Substantive changes need fresh review.
Specification approval is not implemented-backend, account or release acceptance.

Closeout checks passed: all 30 local Markdown links/anchors, both JSON examples,
the unchanged reviewed-body digest and `git diff --check`. Root README/AGENTS
copies agree between the canonical checkout and T3 view. No runtime, package or
immutable handoff-snapshot file changed; no build/provider/deployment acceptance
is inferred from these documentation checks.

| Finding | Parent disposition and changed requirement | Remaining implementation proof |
| --- | --- | --- |
| A01 high: global Code Mode fetch bypass | Accepted; section 4 requires replacement of the direct-fetch extension, per-attempt broker admission, redirect/size/revocation checks. BF03/P02 include this path. | Verify the exact extension seam or narrow injection patch; test fetch after revoke and oversized/redirected responses. |
| A02 high: native MCP auth/transport conflicts with broker | Accepted; section 6 selects credential-free native transport over Python broker, disables native token persistence, separates connection/tool/cleanup authority and names the missing injection seam. | Authenticated synthetic initialize/list/call/refresh/reconnect/termination; token sentinel and bypass checks in BF03/P02. |
| A03 medium: root grants do not confine shell | Accepted; section 4 explicitly chooses trusted OS execution only in the separate developer configuration, with minimal environment/owned descendants and an accurate exception to mediated guarantees. | Out-of-root/network/descendant scenarios and doctor-mode denial; no same-user sandbox claim. |
| B01 high: restore can lose newer native history | Accepted; section 10 preserves additive current+incoming candidate construction, current mutable precedence, native graph/mapping closure, immutable conflict refusal and separate rollback semantics. | BF07/P08 G0→M2/D/A divergence plus incoming-only graph and conflicting-identity scenarios, without inference. |
| B02 medium: temporary disconnect semantics | Accepted; sections 4/5/7 distinguish saved observer detach from temporary family cancellation/settlement/discard and specify the Save activation race. | BF04 and section 12 mid-flight child/worker disconnect and Save-vs-cancel on both sides of activation. |
| F01 high: continuing browser traffic bypass | Accepted; section 4 selects owned attachment/continuing-page lease, broker tunnel open/read/write authority, explicit TCP endpoint granularity/trusted same-endpoint page exception, proxy-only client and complete revoke/stream/context teardown. BF03/P02 include stale reattach/native allows. | Distinct endpoint A→B, delayed scripts/redirects/subresources, live streams/expiry/bytes/revoke, actual socket/client settlement and no native direct-tunnel fallback. |

## 14. Evidence and pinned source index

Public evidence: [source handoff](../implementation/DESIGN_C_OPENCODE_HANDOFF.md),
[foundations](../implementation/OPENCODE_FOUNDATIONS_HANDOFF.md),
[H02–H08](../implementation/OPENCODE_H02_H08_HANDOFF.md),
[MVP](../implementation/MVP_20261019.md),
[harness contract](../../packages/contracts/harness.md),
[Design C contract](../../packages/contracts/design-c.md),
[cohort/provenance](../../upstream/opencode/UPSTREAM.md),
[patch register](../../upstream/opencode/PATCHES.md),
[index maintenance](../implementation/library-index-maintenance.md),
[Library tools](../../packages/harness/src/domain-tools.ts),
[host protections](../../packages/harness/src/host.ts),
[default assembly](../../runtime/renulus/runtime/desktop_harness.py),
[Finder](../../runtime/renulus/storage/search.py),
[helper pins](../../packaging/runtime/requirements-helpers.txt).

Native source cohort: **4b6fea2875e4f2e3e8a8fee181803e54f7056845**,
twelve source packages labelled 2.0.26, one Effect 4.0.1 graph, Node 26.4.0,
Bun 1.4.2 build-only. Registry SDK 2.0.26/current-main documentation is not
interchangeable API evidence. Zero current Renulus OpenCode source patches;
dependency/bootstrap patches retain separate provenance. Exact API evidence,
audited in wave 1 and selectively inspected locally in wave 2:

- [U1 Effect embedding][U1]; [U2 host composition][U2].
- [U3 tool transforms/hooks/registry][U3]; [U4 reload fallback][U4].
- [U5 session/context/generate hooks][U5]; [U6 MCP reconnect][U6].
- [U7 pending permissions][U7]; [U8 subagent inheritance][U8].
- [U9 restart/replay][U9]; [U10 internal plugin inventory][U10].
- [U11 Code Mode execute][U11]; [U12 browser registration][U12].
- [U13 SDK registration/no unregister][U13]; [U14 tool schemas][U14].
- [U15 dynamic MCP tools][U15]; [U16 browser operations][U16].
- [U17 Code Mode global fetch][U17]; [U18 MCP transport construction][U18];
  [U19 MCP OAuth/native fetch][U19].
- [U20 browser attachment authority][U20]; [U21 raw browser tunnels][U21].

[U1]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/effect/opencode.ts#L36-L66
[U2]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/host.ts#L18-L56
[U3]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin/src/effect/tool.ts#L8-L59
[U4]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin.ts#L125-L169
[U5]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin/src/effect/session.ts#L14-L172
[U6]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/mcp/index.ts#L338-L364
[U7]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/permission.ts#L265-L306
[U8]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/tool/plugin/subagent.ts#L129-L238
[U9]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution/restart.ts#L46-L61
[U10]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin/internal.ts#L216-L269
[U11]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/codemode/tool.ts#L57-L76
[U12]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin-browser/src/tools.ts#L34-L55
[U13]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin/sdk.ts#L12-L43
[U14]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/schema/src/tool.ts#L14-L101
[U15]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/tool/mcp.ts#L37-L65
[U16]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin-browser/src/rpc.ts#L155-L496
[U17]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/codemode/web.ts#L13-L40
[U18]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/mcp/client.ts#L263-L340
[U19]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/mcp/oauth.ts#L40-L65
[U20]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin-browser/src/connection.ts#L30-L162
[U21]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin-browser/src/tunnel.ts#L21-L124
