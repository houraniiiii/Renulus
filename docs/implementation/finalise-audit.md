# Bounded release audit — baseline, October 5, 2026

**Status: baseline evidence ledger; final release judgement awaits parent proof.**
No S0–S6 completion is asserted. Several real local flows and an earlier matching
unsigned installation have completed receipts. They do not establish the
current integrated product, successful live generation, or a complete release.

## Scope, cutoffs and revision identity

Audit ownership is this file and ignored `.local/audit/` notes, on
`build/finalise-audit` at `C:/rn-finalise-20261005/lanes/audit`. The starting
revision is `c6437c44b216c7d686f6328a651320275191c012`; it was clean when read.
Git remained idle until the owner's worktree-repair confirmation. No other lane
was changed, no data reimported, and no app, helper model or provider launched.
There are no audit subagents, issue posts, heartbeat, push or deployment.

The owner confirmed relocation to
`C:/Renulus-native-delivery/desktop-20261005/repo`. The E source path is a
junction; the E collection/profile are unchanged. Active integration was read
at `e219154166de49187277022fa353a75de032b278`, then
`da726ac147f20232cb3941ce50a1833af6d12336`, and the relocation checkpoint
`514e6731b2eb0fb0b7bce7b180ef61e82eb0a78b`. These are successive source
observations, not new installed acceptance. The only remote observed is
`origin`, `houraniiiii/Renulus`. Other edits, generated `.vite/`, sessions and
native/data state are preserved.

The requirements are the [stage plan](../planning/IMPLEMENTATION_PLAN.md) and
[parallel baseline](../planning/PARALLEL_WORK.md), last changed at
`9859fa90c8ba1bd3c42b72056e35b051f0870434`, and the
[architecture](../planning/ARCHITECTURE.md), last changed at
`451fe6f550267f0aca01c3d2d27e57b508b82b62`. README, AGENTS, brief, workspace,
decisions, user answers and decision queue were also read. The active checkout's
`docs/implementation/SESSION_HANDOFF.md` was read at
`e219154166de49187277022fa353a75de032b278`; it is absent from the older audit
checkout. Its old path and not-yet-integrated subscription entry are historical
handoff facts, superseded by the owner's relocation confirmation and R17.

Queue observations cover issues #1–#19 and draft PR #13. Its first observed
head was `e219154166de49187277022fa353a75de032b278`; the later GitHub read
confirmed `514e6731b2eb0fb0b7bce7b180ef61e82eb0a78b`, open/draft, with an
empty returned check rollup (PR updated at 11:16:14 UTC). The newest regression
comment read was October 5 at 11:12:23 UTC. Receipt review cutoff is
**11:15 UTC on October 5, 2026**, with the parent's subsequent relocation/preview
update incorporated at **11:20 UTC**. Further parent proof is reserved for
reconciliation. Closed #4/#8/#10/#11 describe module queue outcomes; they do
not close their whole stages. PR prose still describes live sign-in as unproved
despite the completed account-connection observation in R16; successful
generation remains unproved.

The parent reports 19,483 relocated files / 458.03 MiB, zero mismatches/failures,
unchanged tracked source, and all 16 existing worktree gitfiles repaired. Those
are parent-supplied relocation results; this lane did not repeat the traversal.
The pushed PR head confirms integration of `da726ac1` and `514e6731`. The
existing E learning profile and installed `3ff9b0d6` launcher remain in place.

Report commits below identify immutable documentation. They are **not**
automatically the execution source revision. A run's recorded source, fixture,
artifact and scope govern its acceptance. Where a report does not pin a whole
execution tree, that limitation is retained. `.local/audit/baseline-provenance.json`
records last-change commits and SHA256 hashes of the read reports/artifacts;
selected raw-receipt metadata is retained beside it without copying originals,
credentials, case content or source bodies.

## Evidence register

| ID | Immutable evidence and execution identity | Completed observation and boundary |
| --- | --- | --- |
| R01 | [Runtime](runtime-evidence.md), report `32d72e785fd8f65bba2f9cd3f52d00176fb04ce5`; upstream `af90026aa09949579bd423d24def3d38f743cde0`; `hermes-source.json` at `db7e28257520b07ee072e681fb64cc94516c86fb` | Attributed Hermes source, controlled transport/context, DPAPI, fixed allowlist and scoped cancellation have component evidence. The report's original worker identifier `c83b5549` cannot be resolved in the repaired shared object store; it is not expanded into an invented full SHA. The immutable upstream/manifest anchors remain available. |
| R02 | [Offline helper receipt](../../packaging/runtime/offline-helper-proof.json) and [helper manifest](../../packaging/runtime/helper-assets.json), both at `54b3b38a77f753a5cc048beb6708205a665f1d94` | Actual offline CPU FastEmbed, native/scanned PDF conversion/OCR, HybridChunker and LanceDB round trip. Receipt: Windows x64, Python 3.14.4, two threads, 150.479 s, sampled peak RSS 1,489,821,696 bytes, zero external connection attempts. This does not prove installed resource limits or live image interpretation. |
| R03 | [Matching native checkpoint](final-validation.md#matching-installation-and-normal-library-acceptance), report `dc9c3d442360430c7bbb3c278acd16e9d6a51b2b`; product `3ff9b0d6145c8d52f4c9e9b0a3009f0fc351c4cc`; direct `.local/replacement-shortcut-evidence.json` | Fresh unsigned NSIS installation, isolated embedded-runtime lifecycle, real shortcut/health/profile binding, Library25/search/citation and visually rendered PDF. Native PDF accessibility reported unavailable text extraction; its physical-page control was not independently read. One normal queue observation, not sustained responsiveness or a clean machine. |
| R04 | [Final validation](final-validation.md), same report commit as R03; historical runtime `45defa9da3f37ff6dc03f3756b4f0b46631820c5`; targeted receipt's freeze `ebb2db2e5080f4d42eaf31c2eb63711797704df0` | Completed renderer/build and bounded backend/engine receipts; failed and interrupted full regressions remain separate. Later source changes are not covered by reusing these totals. See the counting ledger below. |
| R05 | [Library retrieval](retrieval-evidence.md), report `5be0aa902eec03fee9b28b1169335272e31b7894`; [exact citation](library-passage-citation-evidence.md), report `84a214baf004000a224c7a38bde08cb055e4a7b2`; [inspector](library-source-inspector-evidence.md), report `8005bd992a4d357ad6b6d26ce2a29879f5ac7e54` | Local extraction/search, revision/scope guards, original identity and passage-bound locators have receipts. Controlled citation/renderer tests and earlier viewer journeys do not prove every acquired file or current installed input format. |
| R06 | [Cases](cases-evidence.md), report `c554e678b703455b5db2552f07bb1157702fe4b6`; [retention](learner-retention-acceptance.md) and [image consumer](case-image-consumer.md), reports `ae271aaa5fa2855a0233732f036193c158f80ffc` | Real SQLite/API Save/restart/delete and volatile handoffs, controlled-provider discussion, and selected-engine temporary PDF/PNG receipts. R04 retains the later complete PDF/PNG reruns and their original scanner failures. Live discussion/interpretation and the final installed combined journey remain open. |
| R07 | [Memory](MEMORY.md), report `50f4a72c33943d02cba806719120abb44d504037`; initial backend `de4946f1eab6ff5ddd3da3bc879b2a55f3313fa4` | Actual Mem0 OSS/Hermes, FastEmbed and local Qdrant recall, correction/history purge, physical cleanup and rebuild on synthetic facts. Extraction response was controlled. This is local-engine evidence, not successful live automatic learning-point extraction. |
| R08 | [Study-answer capture](study-answer-memory-evidence.md), report `63c68ad7e8e658da9c10ba09bf83515f12ee87de`; integration `d9d2e5731bb14207ee74dd84155828880d6c7c25` | Exact eligible assistant-answer references, durable idempotent outbox, case exclusion and guarded commits. Real Mem0 flow uses a controlled subscription boundary and synthetic vectors. The focused 19 checks overlap the earlier 81-pass/two-skip run. |
| R09 | [Today](study-final-evidence.md), report/integration `35f874b52eb86fe71aa94949b0c8c69b482c8f18` | Actual original-pack wrong answer affects planning; manual dates/preferences/overrides survive restart. Mounted failure/focus checks and local browser work have distinct scopes. Activity and interest do not establish mastery. |
| R10 | [Updates acceptance](updates-acceptance-evidence.md), report `14bb101f6308b2f1eae681ac7b5124fddd716bc3`; [exact-copy binding](updates-acquired-version-binding-evidence.md), `2bdcc89ed3ff9da12de929d12e3066d37889b6c6`; [scheduling](updates-scheduling-evidence.md), `a1afba86bb3e68ec2203cdbbd8008534869a3095` | Controlled publisher/currency/review/outbox/retrieval rules and bounded opt-in scheduling. Exactly three free requests at 00:14:58 UTC establish dated reachability only; Europe PMC returned 25 records with truncation. No actual changed publication received educational review in those proofs. |
| R11 | [Content](content-evidence.md), report `1def8fbc99ac1c9e82bb0c6d64fac2d027ee3d47`; 1.1.0 payload/coverage at `a6ed49598e726ed018509f24ece202a79c6b5550` | Actual published original pack, activation/version/review guards and cross-domain item/case links. Direct read confirms 27 topics, 56 objectives, 160 questions, 26 cases, zero declared objective-link gaps, and unchanged minimum 150 questions. Complete curriculum/ESENeph blueprint/independent human review claims are false. |
| R12 | [Assessment](assessment-evidence.md), report `299fcb08214537efa961268475df12f0ecba97b5`; [Flow journeys](flow-final-capabilities.md), `92a997bfd779d0adfb76dbc057b8754ba17e2a10`; [renderer review](renderer-final-review-evidence.md), `840bfc33d981e51a371d1991a406fe780e03bcf3` | Deterministic published-key attempts, exposure, help/repeat/generated separation, historical correction annotations and connected local UI/API journeys. The historical 50-item producer check used pack 1.0.0; it is not an ESENeph simulation or live generated-practice receipt. |
| R13 | [Format-2 recovery](recovery-format2-evidence.md), report `a2913ed25d4274eeaed505ed46e79608f0d5be0f`; [larger data-only profile](complete-delivery-profile-live-proof.md), report `dc9c3d442360430c7bbb3c278acd16e9d6a51b2b` | Supported data-only restore, verified originals and CPU/API retrieval across CKD, dialysis and transplantation; later E preparation reused checked prior vectors, then restored actual FastEmbed for the query audit. That cache seam is explicit. Empty learner-memory delivery is not proof of full learner recovery on a second clean installation. |
| R14 | [Office](office-supplements.md) and [Library UI](library-office-ui.md), reports `e5273669b763276bb3341cad722a1e4ce2545b35`; converter integration `909d296872624f7c4c50fd37d1d80e68f222bf00` | Actual DOCX/PPTX/XLSX Docling/HybridChunker conversion, locators and original bytes through API; vectors controlled. Previously failing shared Office backup gate later passed once, with four deselected. Renderer/build checks passed; acquired-file readiness, native original save and a matching installation remain separate. |
| R15 | [No-text image](image-original-preservation.md), report `4081174cbcf6278da343bb498776af670768f10c`; actual receipt source `55d553d1d18026a0a490f4292c033ac1aadd2595` | Direct `.local/actual-no-text-image-55.json` records actual pinned Docling/RapidOCR success, ready revision with zero passages, exact 1,878-byte PNG, genuine metadata, no fabricated page, zero retrieval and supported deletion; 102.085 s. No native original-viewing or clinical interpretation proof. |
| R16 | [Live account record](live-connections-2026-10-05.md) and [shutdown correction](windows-shutdown-physical-proof.md), reports `4081174cbcf6278da343bb498776af670768f10c`; live app `3ff9b0d6145c8d52f4c9e9b0a3009f0fc351c4cc` | Intentional app-owned sign-in/Go entry, explicit Codex selection, Astra-only Codex catalogue. Deliberate image/text attempts failed `subscription_limit`; text typing was truncated. Old installed normal close failed despite backend absence. Windows physical-child tests/build passed for the correction, not matching installed close/reopen. |
| R17 | Active `docs/implementation/finalise-subscriptions.md` at `da726ac147f20232cb3941ce50a1833af6d12336`; worker `8173736394923e578224ff38f5acb57d6c1291eb`; baseline `9d26f1eedf31cd488b9aab5837a105ee152d9efa` | Stop-before-compaction fix integrated. Reported 183 distinct controlled checks comprise a 180-check completed run and three additional overrides. Learn cancellation terminal and generated-practice public error presentation are concrete parent-owned consumer gaps. No live/native acceptance. |
| R18 | [Classified admission](classified-file-adoption.md), report `4081174cbcf6278da343bb498776af670768f10c`; active `finalise-source-adoption.md` at `7a11da65120b9e8f31054ee12d42fe089cb40582`; direct E06 queued receipt records source `7a11da65` | 29 E07/L03 originals admitted separately; exact 28 E06 supplements admitted at 10:34:39–10:34:53 UTC. Hashes/rights/attribution/idempotency verified, lifespan and extraction disabled. Both are admissions, not ready/searchable totals. E06 receipt 487 remains an EMF format hold; unread component qualifications/currentness limits remain. |
| R19 | Parent relocation/T3-preview update, incorporated October 5 at 11:20 UTC; integration documentation checkpoint `514e6731b2eb0fb0b7bce7b180ef61e82eb0a78b` | Earlier T3 host failure is resolved. Actual API reports all ten modules through the localhost:5196 preview using the synthetic parent profile, without workers/helpers/providers. Current cross-drive Vite `@fs` font request returns HTTP 200 **HTML**, a concrete unresolved parent work item. Neither preview availability nor HTTP status alone proves font delivery, extraction or installed acceptance. |

R02/R07 and the actual CPU portions of R05/R06/R13/R15 are reused **real
backend/helper evidence**, with the recorded synthetic inputs, engine identities
and controlled seams retained. They are distinct from controlled SDK/provider
tests such as R17 and from final installed gates. This audit did not rerun OCR,
embedding, memory inference or a native workload.

The recorded helper evidence uses Docling 2.133.0, Docling-core 2.99.0,
FastEmbed 0.8.1, LanceDB 0.39.0, Mem0ai 2.2.1, Qdrant-client 1.19.1 and
RapidOCR 3.9.2. The pinned BGE-small engineering configuration is 384 dimensions
with a 512-token tokenizer limit. R02's embedding fingerprint is
`25b40d98b74669a55bb1cc39fb0c53564deede37b1e221b24683dfd8f48455ba`;
its Docling fingerprint is
`dac182ddf8ecc911404169678fc29b116396cd82ba490bdae820e60f3b2ac5e0`.
These identify the reused receipts, rather than certifying a new package.

Raw receipt fingerprints independently read from the active C checkout:

| Receipt | SHA256 |
| --- | --- |
| `.local/backend-final-20261005T0301Z/acceptance-summary.json` | `49dee1bc8f9a7bf709d894e8baee595574b82896f374404d383e057bde58d741` |
| `.local/replacement-shortcut-evidence.json` | `bb3333166818b61b1128d711cafc771de26d8a0ac2fe58489ffd8a88c453cb45` |
| `.local/actual-no-text-image-55.json` | `8ebf27fae21f2bde9cbee2a49f9f89a1aabe3d4a0f5cd8011052498e3b7bfa6a` |
| `.local/e06-source-adoption-queued.json` | `ad70440b748fad63d6db27b9c9b00980a251658f683ec0c53fdeff1685857384` |

The E06 plan remains
`d346fc4b7b82a724dfe7cf2b276ddd0ff3e83b99535957ab68f9437567b27e05`.
Pack 1.1.0 manifest-file SHA256 was directly matched as
`85641e86ed3e3b5430737a45ad606e7e768357a2807dd542303b9b8e758a1fbe`;
its reported canonical bundle hash is
`3f0b712fad056a8857fb9fc913432914cad599096c28aa96fd35e7515076c670`.
These are different hash scopes. Restricted originals and private screenshots
were not opened or copied during this audit.

## Counting and native provenance ledger

| Observation | Honest scope at this baseline |
| --- | --- |
| Historical renderer 407/407, 33 files; typecheck/Vite/Electron builds | Completed R04 receipt. Later Office renderer 417/417, 34 files, is a separate R14 receipt. Neither is added to the other or promoted to final source acceptance. |
| Historical full backend collection: 901 | HDD attempt interrupted. SSD attempt reached 100% but disk exhaustion/finalization failed: retained 390 passes, 166 failures, 331 errors, 14 skips. It is a failed run, not 901 passes or diagnosed product defects. |
| Three completed disjoint targeted selections | 39 priority + 44 integrated + 13 capacity = **96 distinct targeted passes**, exits zero. Direct summary says `complete=false`, `expected_tests=901`, and only 52 finalized tests from the full partition. Its 97 distinct finalized observations include the separate compact format-1 diagnostic. Neither 97 nor 96 establishes full regression. |
| Interrupted ordinary/engine attempts | Ordinary selection: 332 passed calls/one setup skip, stopped before finalization; overlapping selections are not added. Interrupted engine attempt: one passed/four failed calls without assertion summary/JUnit. Later serial format-1/format-2/PDF/PNG results remain distinct reruns. |
| Current regression queue receipt, 11:12:23 UTC | Harness/report commit `30e88174ccde852df0ac7254177222a60e55acc8`, runtime/content/dependencies reported identical to baseline `9d26f1eedf31cd488b9aab5837a105ee152d9efa`. 1,146 unique collected; 1,095 application selected; 51 excluded: 13 capacity, 19 actual engine/helper, one external collection, two dedicated native protection, 16 separate harness checks. **In progress; no completed result/JUnit accepted here.** Baseline evidence will still need relevance checks for final integrated changes. |
| Library/Office/subscription focused counts | The 38 parent Library checks, worker overlapping scopes, 60 Office checks with one deselection, repaired one-test Office restore, image/capture suites and R17's 183 controlled checks retain their own inventories. No aggregate product pass count is constructed. |
| Old matching unsigned installer | Product `3ff9b0d6145c8d52f4c9e9b0a3009f0fc351c4cc`; installer 965,928,451 bytes, SHA256 `49f82a58b227c3d572747c3b282fdec20c09fe03777e878c9ba8125281460ed2`; NSIS exit zero, 432.751 s. Installed EXE `38d56a3887c2acf0e8b0db8d45047e59471723cbf3f557253f5f8a77691b3cb9`; ASAR `8ea2cab31aaefb3ea56ca37ad524307c4c342538421811fbebe6ec80225c66f0`. |
| Old native timings and later close failure | Isolated old matching Flow readiness 166.522 s and physical close 8.245 s are development-machine observations. Later loaded normal close failed (R16). The correction and package preflight cannot substitute for new matching normal-queue close/reopen. |
| Dated learning-profile snapshot | October 5, 04:51:26 UTC: 7,307 documents, 16,271 passages, 672 ready jobs, 6,634 queued, one embedding, four historical failed revisions. Subsequent seven selection cancellations and later admissions make this a historical snapshot. No current count or full acquired-corpus readiness is inferred. |

No cumulative clinical, content-review, extraction-accuracy or release pass count
is inferred from software assertions. Actual engines on synthetic fixtures
establish their bounded behavior; they do not complete model-dependent or
installed product journeys by themselves.

## Requirement-by-requirement ledger

IDs below decompose the existing stage requirements for audit reference. They
do not change targets or create new product decisions. “Bounded” means a
completed receipt exists for the stated scope; “open” or “partial” means the
required integrated/release proof is still missing. Every stage retains gates.

### S0 — Runtime adoption and delivery foundation

| ID | Requirement | Evidence at baseline | Remaining gate / disposition |
| --- | --- | --- | --- |
| S0.01 | Immutable Hermes adoption, patch provenance, source layout and scoped licences | R01 pins upstream and manifests; MIT/CC BY scopes are recorded. | Bounded source adoption. Final distributable dependency/artifact notices and inventory still need reconciliation. |
| S0.02 | Controlled runtime/tools/context; no unapproved secondary calls, credential discovery or persistence | R01/R17 actual Hermes/SDK paths with controlled HTTP and filesystem guards. | Bounded policy evidence; preserve the same policy in final packaged paths and all live foreground/background operations. |
| S0.03 | Versioned process contracts, IDs, migration coordinator and isolated storage | R01/R05–R13 use canonical SQLite/contracts and isolated profiles. | Final populated upgrade, interrupted migration, unsupported-version refusal and install identity isolation need matching evidence. |
| S0.04 | Protected deliberate optional retrieval keys, activation and usage/cost controls | Runtime/architecture contracts and controlled retrieval/Updates tests. | No new live keyed adapter accepted here; reconcile adapter-specific auth/quota/cost-cap receipts. Retain a key-free route. |
| S0.05 | Native Windows runtime starts without developer setup | R03: embedded CPython/Electron and child OS-only PATH, actual old installation. | Final matching manufacture/install after source freeze; clean Windows/CPU support matrix is open. |
| S0.06 | Bundled Docling/OCR/FastEmbed/LanceDB/Mem0 helpers perform offline round trips | R02/R07; native old helper readiness imports are separate. | Bounded engine evidence. Final installed helper extraction/OCR/index/memory round trips with exact bundled assets remain to reconcile. |
| S0.07 | Compatible pins, hashes, tokenizer/native binaries, CPU paths and no implicit downloads/cloud fallback | R01/R02 manifests; approved OSS engines retained. | Audit final package payload/terms and source-to-artifact correspondence, including relocation. Selection/import success alone does not complete packaging. |
| S0.08 | Exact five-model/account/input capability matrix, automatic routing/manual override | R01/R17 controlled guards; R16 live Codex catalogue exposes Astra only. | Sol/Luna absence is honest unavailability. Go learning remains paused. No availability row is a successful input/generation row. |
| S0.09 | App-owned authentication, real response per advertised available connection, stream/Stop/restart | R16 intentional connection accepted; deliberate image/text requests failed quota. R17 Stop-before-compaction fixed. | Successful authorised live response/cancel/retry and required image path open. Learn terminal consumer repair is still open. |
| S0.10 | No-save sentinel absence, bounded resource/latency/installer measurements | R01/R02/R06 guard scopes; R03 dated size/timings. | Full installed scope/error/crash/handoff scan and final CPU/RAM/latency/support envelope. Old development measurements are not a clean-machine benchmark. |
| S0.11 | Schema compatibility, no implicit downgrade; app rollback distinct from data restore | R11/R13 immutable pack/canonical restore checks. | Matching upgrade/rollback and newer deletion-ledger preservation need final combined proof. |

### S1 — Ask, explain and resume

| ID | Requirement | Evidence at baseline | Remaining gate / disposition |
| --- | --- | --- | --- |
| S1.01 | Flow shell, connection controls and normal Windows launcher | R03/R12 actual earlier shell and shortcut; R17/R19 are later source/preview evidence. | Resolve the current font response; final matching installed normal launch, ingestion-active close/reopen and profile/account binding. |
| S1.02 | Direct and guided explanations/follow-ups across nephrology | R06/R12 controlled local producers/renderer; broad original topics R11. | Successful approved-subscription direct/guided multi-domain journey; quota-failed input supplies no completion. |
| S1.03 | Streaming, selected-subscription model override, Stop/retry | R01/R17 controlled SDK tests; two Stop-before-summary guards integrated. | Learn deliberate Stop currently lacks its terminal SSE event in the reproduced consumer path; parent repair plus live/matching proof. |
| S1.04 | Ordinary study history resumes/deletes after restart; case branches remain volatile | R06/R08 actual SQLite/API retention, stale-resume and version guards. | Bounded local persistence. Reconcile final installed study resume/delete and crash/error paths. |
| S1.05 | Actionable offline/auth/quota/model errors preserve work, without fallback | R16 real quota failure; R17 controlled restart/retry and catalogue overrides. | Generated-practice presenter still collapses known public codes; parent consumer repair. Live recovery retains the chosen account/model. |
| S1.06 | Sources/unverified answers visibly distinguished; no canned production answer | R05/R12 cited local routes and retrieval failure states. | Source-grounded live answer and freshness lookup without upload, including unavailable retrieval, remain open. |

### S2 — Material, evidence and cases

| ID | Requirement | Evidence at baseline | Remaining gate / disposition |
| --- | --- | --- | --- |
| S2.01 | Useful direct text, text-PDF and scanned-PDF/OCR through selected pipeline | R02/R05 actual offline engines; R06/R04 full temporary PDF/PNG reruns. | Final installed import → ready → query → exact original/citation journeys across domains; fidelity, units/tables/reading order remain bounded to tested material. |
| S2.02 | Preserve valid no-text image originals; separate OCR from model interpretation | R15 actual blank PNG succeeds, viewable original API, zero passages and no fabricated page. | Matching native import/original-view/delete and truthful no-searchable-text state. Successful clinical image interpretation remains a separate live gate. |
| S2.03 | Durable selected Office supplements, actual slide/sheet/item/table locators and original bytes | R14 real three-format conversion/API/restore with controlled vectors. | Matching native DOCX/PPTX/XLSX selection, conversion/search, original Save/Cancel and citation journey; acquired-file readiness and actual embedding path open. |
| S2.04 | Exact revision/passage/page/region citation and original access, unknown locators remain unknown | R05 exact-bound APIs; R03 visual PDF/page-13 link. | Current installed exact-page/Office/image originals and accessibility. Old native physical page was not independently read; exact passage highlighting is not established. |
| S2.05 | Stage eligible revisions; failed/cancelled replacement retains prior active revision | R05/R15 guards and controlled race/rebuild checks. | Bounded implementation; final matching cancel/delete-during-ingestion/replacement and restart must not republish stale results. |
| S2.06 | LanceDB native hybrid retrieval, filters, paraphrases/acronyms across editions/domains | R02/R05/R13 actual local retrieval, CKD/dialysis/transplant passages. | Final current revision/scope/currency and varied paraphrase/abbreviation query evidence; full corpus coverage is not inferred. |
| S2.07 | Authorised local import, official user download, per-file edition/rights/attribution, originals preserved | R18 exact classified/E06 API admissions; source register remains authority. | Admissions are queued. Reconcile eventual selected readiness and visible attribution; retain component/format holds, unknown currentness and operation-specific limits. No reimport. |
| S2.08 | Malformed/encrypted/oversized inputs and cancellation handled before unsafe persistence | R05/R14 container/API boundary checks. | Bounded synthetic refusals. Final installed failures/cancellation preserve originals and prior active revision. |
| S2.09 | Freshness-sensitive Explain automatically retrieves eligible evidence without an upload/paid key | R10 bounded free reachability plus controlled pipeline; R05 retrieval eligibility. | No completed live no-upload Explain → fetched passage/date citation journey accepted. Failure/unverified state must be exercised too. |
| S2.10 | Optional keyed retrieval has deliberate activation, protected keys, quota/cost-cap errors | Controlled adapter/connection scopes exist; no incidental billed calls in this audit. | Reconcile exact selected adapter receipts; key-free required flows remain available. |
| S2.11 | Temporary/unclassified case data and every derivative remain absent from durable stores | R01/R06/R08 sentinel, API/export/file and compaction fences. | Final installed forced-error/crash/mode-handoff/backup scans; case facts must not enter automatic Memory. |
| S2.12 | Explicit Save retains case snapshot/attachments; saved follow-up and restart/delete semantics | R06 real Save/restart/delete and shell disclosure correction. | Final native Save/reopen/follow-up plus discussion using approved subscription; one quiz start or unsaved preview is not completion. |
| S2.13 | Physical derivative cleanup, old Lance versions, delete-during-ingestion and stale-job exclusion | R05/R07/R15 actual/controlled cleanup and canonical guard scopes. | Final index cleanup/restart and cross-module export/restore with retained newer deletion markers. |
| S2.14 | Interactive Library stays usable while the normal queue progresses | R03 one successful native Library25/search observation; earlier timeouts retained; priority implementation later source. | Sustained final installed interactive priority, queue fairness/cancel/restart and resource evidence. Queued/Available/searchable counts must remain distinct. |

### S3 — Assessment and content

| ID | Requirement | Evidence at baseline | Remaining gate / disposition |
| --- | --- | --- | --- |
| S3.01 | Retain measurable broad content targets; original reviewed questions/cases with evidence terms | R11 directly matches 27 topics/56 objectives/160 questions/26 cases; minimum 150 unchanged. | Existing link/count target is met at payload scope. Full explanation/evidence/question/case/update matrix and ESENeph depth are not thereby complete. |
| S3.02 | Actual immutable original pack installs/activates and consumers share it | R11/R12 real SQLite/bootstrap/producer checks; historical versions retained. | Reconcile final installed exact pack, consumer versions and upgrade behavior. No new lowered launch target. |
| S3.03 | Committed deterministic scoring, rationale sources, mistakes, pause/resume | R12 actual published-key producer/API and UI journeys. | Bounded local scoring. Complete final matching Test/feedback journey across domains remains open. |
| S3.04 | Idempotent restart avoids duplicate answers/exposure; stable item/family/key versions | R11/R12 transactional checks and race/history evidence. | Final cross-module restart/cancel/source-help modes retain exact versions and exposure. |
| S3.05 | Corrected/withdrawn keys annotate historical results without rewriting them | R11/R12 immutable predecessors/withdrawals and R10 source annotations. | Bounded correction rules; final installed correction/update/history journey still needs reconciliation. |
| S3.06 | Fresh, assisted, repeat and generated aggregates remain separate after mode switches | R12/R17 actual stores with controlled generated output. | Final UI transitions and source help; no generated score counted as reviewed mastery. |
| S3.07 | Reserved bank never leaks into Explain/practice context | R11/R12 teaching-material and exposure guards. | Preserve final consumer/retrieval boundaries, including new programme selection. |
| S3.08 | Generated practice is labelled, uses approved generation and keeps unreviewed keys separate | R12/R17 controlled SDK/API flows. | Successful live generated set and repaired actionable provider-error presenter; no synthetic completion is promoted. |
| S3.09 | ESENeph insufficient coverage is honest; no complete exam simulation without supported blueprint/length | R11 explicitly false blueprint claim; old `esen_eph` selection has no mapping. Issue #19 remains open. | Formal mapping/version/provenance and Assessment/Cases/Study consumer integration, sufficient session pool and transparent gaps. Mapping authoring alone will not close this row. |

### S4 — Memory, progress, plan and home

| ID | Requirement | Evidence at baseline | Remaining gate / disposition |
| --- | --- | --- | --- |
| S4.01 | Hermes/Mem0 OSS + explicit FastEmbed/local Qdrant; SQLite authority and rebuildable generations | R07 actual local engines, history purge/recall and physical rebuild. | Final installed engine/artifact identity and populated learner-index recovery. |
| S4.02 | Durable idempotent eligible capture queue with references/provenance and correct scope | R06/R08/R17 actual outbox/reference fences; case/noncompleted answers excluded. | Bounded automatic eligibility; reconcile final workers/restarts and no lost distinct lessons. |
| S4.03 | Automatic general learning points through approved live subscription, without case/prompt facts | R08 real Mem0 extraction flow uses controlled generation; R16 live attempts quota-failed. | Successful authorised Learn answer → autonomous capture → canonical point → recall, with provider/model identity and no case data. |
| S4.04 | Deduplication, editable records, revision conflicts, physical history/index purge and suppression | R07/R08 actual/controlled correction/delete/replay guards. | Final correction during summarisation, deletion during capture, queued reindex/restart/restore scans; cleanup pending is never represented as complete. |
| S4.05 | Relevant corrected personal context within separate library/memory budgets, no invented mastery | R01/R07/R08 context/recall guard scopes. | Live multi-domain personalised answer changes after correction; deleted/superseded context stays excluded. |
| S4.06 | Plan uses goals/time/exam date/observed mistakes, with free browsing and manual overrides | R09 real wrong answer and durable manual changes. | Bounded application behavior; reconcile final installed records and programme mapping consumers. |
| S4.07 | Useful new-user home: Ask/Resume/review/updates, real records | R09/R12 local new/existing learner UI and producer evidence. | Matching native empty/history/error/scaling states and complete linked activity return. |
| S4.08 | Versioned export/restore with attachments/provenance and deletion limits on second installation | R07/R13 local engine/canonical restore scopes; larger delivery held zero Memory facts. | Populated learner/case/study restore on clean second installation, rebuilding both derived engines; preserve newer markers and disclose old-backup limits. |
| S4.09 | Expected memory volume, paraphrases/abbreviations, repeated capture and quota/index failure recovery | R07 bounded cross-domain semantic/race tests; R17 no-partial-answer capture. | Expected-volume evidence and live background failure/retry behavior on final source. Generic wrapped memory failures must retain useful recovery. |

### S5 — Current evidence and updates

| ID | Requirement | Evidence at baseline | Remaining gate / disposition |
| --- | --- | --- | --- |
| S5.01 | Bounded in-app source checks, explicit opt-in, durable successes/failures and topic-only queries | R10 actual scheduler/API/store with controlled transport and three dated free requests. | Final installed check/stop/shutdown/reopen behavior; no raw case queries or background actor after app close. |
| S5.02 | Final/draft, chapter replacement, corrigenda, expiry, removal/retraction remain separate | R10 exact source-copy/outbox/journal guards and controlled publisher sequences. | Actual publication/source-review receipts; no fetch/import date or fixture review establishes current final guidance. |
| S5.03 | Detected changes separate from explicitly reviewed educational entries, with dates/source links | R10 pending discovery/review workflow and R12 UI. | An actual eligible changed source reviewed, displayed and linked to affected objectives on final product. |
| S5.04 | Correction flags bank/learning history without rewriting keys/results | R10/R11/R12 local annotations and immutable attempts. | Final combined update → affected item/plan/feedback journey with actual review evidence. |
| S5.05 | Offline/failed/stale/restricted reimport accurate, same-URL change and exact-copy review reproducible | R10 controlled restart/exclusion/dismissal/re-review checks; R13 current-only excluded unreviewed sources. | Final native failure/reimport states and continued current-only exclusion; partial discovery is not complete acquisition. |

### S6 — Complete, installable product

| ID | Requirement | Evidence at baseline | Remaining gate / disposition |
| --- | --- | --- | --- |
| S6.01 | Required broad-topic and ESENeph cells: explanation/evidence/questions/cases/update sources | R11 broad original linked content; #19 mapping lane active. | Full adopted manifest/required cells and consumer behavior. Preserve all 27 topics/56 objectives, existing minimum 150 and breadth; do not reduce the product to a demonstration subject. |
| S6.02 | Case → Explain → practice/Test → feedback → Memory → plan → Updates across domains | R06–R12 bounded parts; earlier parent preview only opened a reviewed quiz question. | Complete matching installed multi-domain journeys, real live generation/capture and return/resume outcomes. A started quiz or connected screen is insufficient. |
| S6.03 | Completed relevant backend/renderer/regression on integrated source, failures/exclusions adjudicated | R04 historical results; latest 1,095-test application run still in progress at read cutoff. | Completed inventories/exits/JUnit, justified skipped/excluded tests with separate required coverage, and changed-source relevance. No partial-event count becomes a full pass. |
| S6.04 | One Flow system; keyboard, screen reader, text scaling/resize/reduced motion; loading/empty/errors | R12 actual route/focus/resize checks and final focus integration `8f6de976e75c211022c3e4ca82f5f68464efff53`; R19 restores preview but identifies an HTML font response. | Actual font content/load plus final screen-reader/text-scaling/reduced-motion and native original-reader access. Preserve Flow/Renal flow rather than redesigning during release. |
| S6.05 | New source freeze → exact payload → manufacture/install → normal lifecycle matching that source | R03 proves only old `3ff9b0d6`; R16 correction and R17 later source are uninstalled. | Final source/installer/EXE/ASAR/backend inventory hashes, normal queue close/reopen and account/profile preservation. NSIS preflight is not manufacture or installed acceptance. |
| S6.06 | Signed distribution, authenticated updates, static release and complete notices | Earlier installer observed unsigned; adopted component terms retained separately. | Publisher signing setup, signature/authenticity and update tests, final artifact notice inventory. No release/deployment performed here. |
| S6.07 | Install/upgrade/rollback, database migration, uninstall/data-retention and isolated installation identity | R03 old install and R11/R13 local version/recovery guards. | Final populated upgrade/interruption/rollback/uninstall/retained-data evidence; compatible app rollback cannot silently downgrade data. |
| S6.08 | Backup/restore incl. Office/image originals, citations and both derived indexes; recovery disclosure | R13 supported data-only recovery; R14 repaired controlled-vector Office round trip; R15 no-text original API. | Matching native backup Save/Cancel/partial failure → restore → populated canonical and index checks on second installation, including deletion-ledger limits. |
| S6.09 | Plain-language onboarding/running/recovery and truthful capability controls | Existing running/handoff/error-copy records; R17 identifies two remaining consumer presenters. | Reconcile docs/launcher to accepted final installation, account quota/image/Go states, original recovery and all required controls. |
| S6.10 | Clean personal Windows installation completes required real journeys without developer tooling/setup | No clean-machine receipt. OS-only PATH evidence was on a development machine. | Signed matching clean-machine installation, managed helpers, user-connected approved models, full journeys and restore; untested platforms are not advertised. |

## Parent proof checklist and reconciliation contract

| Gate | Concrete receipt needed | Current state |
| --- | --- | --- |
| G1 — matching native product | Integrated freeze SHA; payload/artifact hashes and notices; manufacture and installer exit; installed provenance; normal queue launch/close/reopen; preserved chosen profile/account selection; physical ownership observations. | Awaiting parent. Old `3ff9b0d6` is preserved historical acceptance with a later normal-close failure. |
| G2 — completed regression | Exact collected/selected/excluded node IDs, execution source/dependencies, final exits/JUnit, pass/fail/error/skip accounting, resource bounds and separate engine/capacity/native coverage. Reconcile changes after `9d26f1ee`. | In-progress baseline application run; no completed new receipt. Historical failed/partial/overlapping results stay separate. |
| G3 — Library inputs/originals/citations | Matching native text/PDF/scanned-PDF/image and DOCX/PPTX/XLSX admission/ready/error/replacement/delete; actual selected-engine search where text exists; exact original bytes/media/location; original Save/Cancel and citation/reader accessibility; queue priority/fairness. | Partial API/engine/old native evidence. Classified/E06 admissions are queued; no reimport or sibling adoption required by this audit. |
| G4 — broad content/ESENeph | Versioned formal mapping/provenance and coverage gaps; general/ESENeph selectors in actual Assessment, Cases, Study/home; stable pinned attempts and content/recovery compatibility; required pool/length disclosures. | Existing broad 1.1.0 preserved. Formal mapping and connected consumers await lane/parent receipts. |
| G5 — subscriptions/automatic Memory | Consumer fixes for deliberate Learn Stop and known generated-practice errors, assigned by the parent to the Averroes module lane; intentional allowed-account live Explain/direct/guided/cancel/retry/generated/image journeys; automatic general-point capture/correction/recall with exact selected model; honest quota and Go pause. | Connected account accepted; successful generation/image/capture not accepted. Averroes repair/consumer receipts await reconciliation. No fallback or credential borrowing. |
| G6 — recovery/connected product | Complete multi-domain case-to-learning/feedback/Memory/plan/Updates journeys; crash/restart/no-save scans; populated backups incl. Office/images and citation identity; second-install restore and both derived rebuilds; newer deletion markers/old-backup disclosure. | Component/data-only receipts only; final matching connected and second-install proof open. |
| G7 — signed clean-machine release | Signing identity/artifact signature; update authenticity; clean Windows install/upgrade/rollback/uninstall/data retention; no developer setup/download requirement; required live journeys and full notice inventory. | Unsigned earlier installer; signing and clean-machine acceptance unproved. |
| G8 — coverage and Flow access | Adopted full broad-domain/ESENeph required-cell manifest; actual Flow font delivery; final keyboard/screen-reader/scaling/resize/reduced-motion and loading/error controls, including native originals. | T3 preview available; current font response is HTML. Bounded route/focus/resize and content links; complete release cells/accessibility open. |

Each new parent proof should name the source/commit, precise operation and
fixtures, engine/provider/artifact identities, start/finish UTC, final exit or
terminal state, raw receipt/log/JUnit paths, and explicit failures/skips/limits.
The audit will read those artifacts and update the corresponding requirement
rows; changed code does not inherit unrelated old passes. Acquisition receipts,
API admission, ready original availability, searchable passages, source
currentness, medical review and release acceptance remain distinct evidence.

Final report and release disposition are pending that reconciliation. This
baseline is reviewable now and does not authorize a launcher switch, issue
closure, publication, paid request, new import or completion announcement.

Audit-only validation checked all 64 stage-row IDs, 19 evidence IDs, local
document links, five directly read receipt/manifest hashes and the immutable
1.1.0 counts/claims, with no discrepancy. `.local/audit/report-verification.json`
retains that result. This is document/provenance validation, not an additional
application test pass.
