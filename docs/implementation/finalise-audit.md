# Bounded finalisation audit — reconciled, October 5, 2026

**Status: this bounded audit is complete; matching current-PC product acceptance
remains open.** No S0–S6 completion is asserted. The recovered receipts establish
specific local application and CPU-engine behavior. They do not establish final
installed journeys, successful live generation or populated recovery.

The owner's October 5 decision supersedes the earlier delivery plan: accept an
**unsigned Windows build validated on this PC**, including a fresh isolated
installation, bundled runtime with OS-only PATH, matching source/artifact hashes,
normal shutdown/reopen and actual required journeys/recovery. Signing and a
separate clean PC/VM are optional future distribution work, not current blockers
or missing external inputs. This decision is committed in `793eddb4` in
[DECISIONS](../DECISIONS.md), [user answers](../planning/2026-10-04-user-answers.md)
and the [implementation plan](../planning/IMPLEMENTATION_PLAN.md).

## Scope, cutoffs and revision identity

Audit ownership is this file and ignored `.local/audit/` notes, on
`build/finalise-audit` at `C:/rn-finalise-20261005/lanes/audit`. This wave recovered
the clean `dd450272a7a61d204e9202a2f4eff51dd2f7824d` report and verified its bytes
match integrated `50aac06c4293c01c6d425b65e474a5d027250334`. The original report
started at `c6437c44b216c7d686f6328a651320275191c012`. Its evidence and ignored
baseline notes remain preserved. No prerequisite commit was replayed into this
lane; immutable Git reads suffice for reconciliation. The new handoff is only
the owned report change.

The active parent is `C:/Renulus-native-delivery/desktop-20261005/repo`; its E
source path is a junction. At the **14:35:12 UTC, October 5, 2026** receipt read,
parent HEAD was `8c6c4b181281a0d5a6057ff032ab504f82f4e20e`, with no tracked
changes and only generated `.vite/`. This is an observed integration source,
not the parent's final freeze or a new installed revision. Sole origin remains
`houraniiiii/Renulus`. Other edits and native/private state were preserved;
no original, credential or private profile was opened. This audit launched no
test, app, provider, helper model, native workload, import, heartbeat, agent,
issue post, push or deployment and changed no launcher.

| Recovered lane / decision | Parent integration | Reconciliation |
| --- | --- | --- |
| Audit `dd450272a7a61d204e9202a2f4eff51dd2f7824d` | `50aac06c4293c01c6d425b65e474a5d027250334` | Identical report; 64 original stage rows retained |
| Current-PC acceptance and C proof confinement `793eddb4` | `793eddb4a7ce6bdfeec59f1741f703157de6673e` | Owner's delivery scope and parent-reported 5/5 confinement checks, R28 |
| Content `604b6d1124fd805513b6a4a991b779e595b0c18e` | `a6b5d597ed102ac0c2cb456445ebf22aaf523509` | Same owned files; immutable 1.1.1 and partial mapping, R21 |
| Assessment `714207160707f9a514f35c00322ba2044f448765` | `16ad199db0cbc6a3a016d5c38439e7da7af38880` | Same owned files; content-track consumer, R22 |
| Packaging `2d923a43011e946483991185dbc3d366e6756ef8` | `c9d145afbf6424db39875d41e6c62fabda619c6f` | Same owned files; machinery/preflight, R23 |
| Runner `30e88174ccde852df0ac7254177222a60e55acc8` | `eb821aa34ddc2d685d60cdc8ae83344cfb6ec78b` | Same owned files; source-attributed receipt harness, R24 |
| Recorder fix `2d16bd58eedad9d42adef071b42ba68afa482eea` | `8c6c4b181281a0d5a6057ff032ab504f82f4e20e` | Same owned files; preserve strict privacy tests, R24 |

Full resolved SHAs, changed paths, identical lane/integrated-file comparisons
and parent ancestry are retained in
`C:/rn-finalise-20261005/lanes/audit/.local/audit/reconciliation-provenance-20261005.json`.
AGENTS, README, brief, workspace, decisions, stage/architecture/parallel plans
and the active parent's `docs/implementation/SESSION_HANDOFF.md` were read.
The handoff is absent from this older tree. The pre-update parallel baseline
and architecture remain dated guidance; the owner's explicit current-PC decision
overrides their older clean-machine/signing language. Exact subscription policy,
Flow/Renal flow, Hermes/Docling/HybridChunker/FastEmbed/LanceDB/Mem0, SQLite
authority, source-operation permissions and temporary-case retention are unchanged.

The baseline's issue/PR observations, 11:15/11:20 UTC evidence cutoffs and
parent-supplied relocation totals remain historical at `dd450272`; no GitHub
read was repeated in this wave. Closed module issues do not establish stage
completion. The existing installed `3ff9b0d6` observations remain historical.

Report commits below identify immutable documentation. They are **not**
automatically the execution source revision. A run's recorded source, fixture,
artifact and scope govern its acceptance. Where a report does not pin a whole
execution tree, that limitation is retained. Baseline hashes remain in
`.local/audit/baseline-provenance.json`; the new provenance receipt records 47
receipt/document observations, XML identities and source comparisons, without
copying originals, credentials, case content or source bodies.

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
| R17 | [Subscriptions](finalise-subscriptions.md), original report `da726ac147f20232cb3941ce50a1833af6d12336`; worker `8173736394923e578224ff38f5acb57d6c1291eb`; baseline `9d26f1eedf31cd488b9aab5837a105ee152d9efa` | Stop-before-compaction fix integrated. Reported 183 distinct controlled checks comprise a 180-check completed run and three additional overrides. The originally reproduced Learn terminal and practice-error gaps are historical, resolved at application level by R25. No live/native acceptance. |
| R18 | [Classified admission](classified-file-adoption.md), report `4081174cbcf6278da343bb498776af670768f10c`; active `finalise-source-adoption.md` at `7a11da65120b9e8f31054ee12d42fe089cb40582`; direct E06 queued receipt records source `7a11da65` | 29 E07/L03 originals admitted separately; exact 28 E06 supplements admitted at 10:34:39–10:34:53 UTC. Hashes/rights/attribution/idempotency verified, lifespan and extraction disabled. Both are admissions, not ready/searchable totals. E06 receipt 487 remains an EMF format hold; unread component qualifications/currentness limits remain. |
| R19 | Parent relocation/T3-preview update, incorporated October 5 at 11:20 UTC; integration documentation checkpoint `514e6731b2eb0fb0b7bce7b180ef61e82eb0a78b` | Earlier T3 host failure resolved; synthetic API reports ten modules without workers/helpers/providers. At that historical observation, the cross-drive Vite `@fs` font request returned HTTP 200 **HTML**. This wave did not query that preview. R22 separately proves the built lane renderer loaded Source Sans 3; neither scope establishes final installed access. |
| R20 | Parent pinned CPU run, source `50aac06c4293c01c6d425b65e474a5d027250334`; `C:/rn-finalise-20261005/parent/engines-50aac06c/{run.json,run.log,pinned-engines.xml}` | October 5, 11:33:49–11:36:12 UTC: exit 0; JUnit **19/19 passed, zero failures/errors/skips**, 138.873 s, seven warnings. Actual local text/PDF/PNG extraction, OCR/page-region/original retrieval, FastEmbed/LanceDB text query/rebuild and HybridChunker tables. Fifteen Office checks use actual Docling conversion and pinned tokenizer, without OCR/model loading or Office embedding/search. No Mem0, live image interpretation or installed proof. |
| R21 | [ESENeph producer](finalise-esen-eph.md), lane `604b6d11` → parent `a6b5d597`; raw `C:/rn-finalise-20261005/lanes/esen-eph/.local/esen-eph/` | Read `validate-1.1.1.log`, `pytest-all-20261005-1.log` and `track-metadata-1.1.1.json`: 121 content tests passed, one warning; valid immutable 1.1.1 retains 27 topics/56 objectives/160 questions/26 cases. Dated C01 mapping: 152 mapped distinct families, eight excluded questions, partial domains, zero best-of-five-format questions; human review, endorsement and exam simulation false. Clinical questions/cases/source/coverage JSON are identical to 1.1.0; this is mapping review, not a new clinical review. |
| R22 | [Assessment consumer](finalise-assessment-track.md), lane `71420716` → parent `16ad199d`; raw `C:/rn-finalise-20261005/lanes/assessment-track/.local/finalise-assessment-track-*.xml` and `finalise-assessment-track-handoff.json` | Direct XML reads: Python 33, catalog 12, final Python 29 and UI 10 passes in overlapping selections; do not sum. Producer projection is key-free, exact mapped selection is guarded, partial coverage/format/date/family shortfalls are disclosed, history retains its track title. Reported typecheck/build and built-font/wide-preview checks are separate. Lane tests use a synthetic mapped adapter; final 1.1.1 producer/consumer combination and narrow/native access are not proved. |
| R23 | [Packaging](finalise-packaging.md), lane `2d923a43` → parent `c9d145af`; raw `C:/rn-finalise-20261005/lanes/packaging/apps/desktop/test-results/` | Recovered `nsis-full-factory-03/preflight-evidence.json`: compile/preprocess machinery passed; stock-include probe exit 1 was expected; `installer_execution=false`. Read relocation logs: ten Python tests and 31 PowerShell boundary refusals passed. `relocated-plan.json` is `plan_only=true` at `9d26f1ee`. No final product Package/Install/Proof, signing or runtime execution was performed. Its historical E-only Proof prerequisite is superseded by R28's C confinement change. |
| R24 | [Backend runner](finalise-regression.md), lanes `30e88174`/`2d16bd58` → parent `eb821aa3`/`8c6c4b18`; production baseline `9d26f1eedf31cd488b9aab5837a105ee152d9efa` | Raw completed harness 16/16, repaired harness 17/17 and exact privacy regression 1/1 have valid JUnit/exit 0, separately. First full `b2` attempt ended exit 1 on recorder/strict-write-guard conflict; repair did not weaken product privacy. New `b3` has 1,147 collected, 1,095 selected and 52 excluded; at this read its result/session/outcomes files were empty and final JUnit absent. No full application pass or final-source acceptance. |
| R25 | [Subscription consumer extension](finalise-subscriptions.md), integrated `15f284b9e06e33d3ba86e404261684bf3eb7d49e`; raw `C:/rn-finalise-20261005/lanes/subscriptions/.local/runtime/finalise-subscriptions/consumer-*.xml` | Focused 47/47; combined Learn/Assessment 127 passes/one readiness-timeout failure; corrected final Learn 46/46. The combined run's 82 Assessment passes plus final Learn cover 128 distinct checks, not a clean combined invocation. Local Stop emits one terminal; external task cancellation propagates; partial outputs create no answer/capture. Fourteen public practice error codes retain safe application-owned recovery text; unknown/provider bodies stay redacted. Live/native/capture completion remains open. |
| R26 | [Library UI](finalise-library-ui.md), integrated `57201c6920af3f486a00f4db00bd73640c00efaa` | Recovered report retains 118 renderer passes, then one final long-title refinement pass/35 unselected skips and a successful build. Draft/idempotent retry, acquired receipt reselection, accurate job/queue/original/no-text states and Office locators are renderer evidence. No new engine or native picker/download acceptance; Office/TIFF use external viewing, without automatic Office jumps/highlighting. |
| R27 | [Ingestion](finalise-ingestion.md), worker `f25da20e` → code `54ced128` / report `eca179d3505bd2c8ec40fbeb4cd981b10c220395` | Parsed owned XML: compatibility 50 passes; latest core 17 passes; API batch 21 passes/two incomplete-fixture replay failures, then corrected two passes. Counts overlap. Actual semchunk plus controlled converter/tokenizer/store seams prove cache and priority rules; 29 selected jobs need 38 synthetic dispatches with fairness, not a native time/RAM improvement. R20 separately checks affected actual engines. Hashless-catalogue replay limitation remains reported. |
| R28 | Owner decision and parent patch `793eddb4`; `docs/DECISIONS.md`, `docs/planning/IMPLEMENTATION_PLAN.md`, `docs/planning/2026-10-04-user-answers.md` and `apps/desktop/scripts/native-evidence-directory.mjs` | Unsigned, fresh isolated installation/current-PC acceptance is confirmed. Parent reports C evidence confinement **5/5 passed** with existing junction guards. Source patch is integrated; a raw test receipt path was not supplied for independent parsing here. This clears the earlier source-level E-only Proof prerequisite, not actual manufacture/installed Proof. Signing and separate clean-PC/VM work are optional. |

R02/R07/R20 and the actual CPU portions of R05/R06/R13/R15 are reused **real
backend/helper evidence**, with the recorded synthetic inputs, engine identities
and controlled seams retained. They are distinct from controlled SDK/provider
tests such as R17/R25 and from final installed gates. This audit did not rerun OCR,
embedding, memory inference or a native workload.

R20's `run.json` records the source/runtime path and engine file SHA256
`7df16dd6dd6c88c47d05a2bb95a48f5c7f74ff5dfb8e779e4376645519f70dd4`.
That SHA matches the parent's current engine file, and Git shows no change
between `50aac06c` and `8c6c4b18` in that file or the three selected test files.
This is bounded source correspondence, not a whole-tree runtime-import receipt.
The run's embedding/Docling fingerprints match R02 below. Its public helper-copy
receipt records Robocopy exit 1; the copy log shows 20 copied files, zero
mismatches and zero failures, and both helper groups are ready in `run.json`.
This is a public helper copy, not a product installation.

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

New raw receipt fingerprints (all under `C:/rn-finalise-20261005/`):

| Exact path relative to that root | SHA256 |
| --- | --- |
| `parent/engines-50aac06c/run.json` | `a6bb4d294a391ea4a0f30654fe200731cf9eba87bcd279c945a3798b768af771` |
| `parent/engines-50aac06c/pinned-engines.xml` | `bc6a3de8227242c765cbe5a2e069714d9d1a22aeab5e87d08d8f0011c30ffba2` |
| `parent/engines-50aac06c/run.log` | `5491acc2c9779e6d8335cfcb3312408f928f78fb75361ddbca0ae94321a476bd` |
| `b3/run.json` | `c3b58f8828cfe21b507033a1803c299525d80a0ee572c1aa7cdda5500a43ff31` |
| `lanes/esen-eph/.local/esen-eph/validate-1.1.1.log` | `472777ab481ba0f49c085ddfb60e789138aec19e87f409157ea34053d14c2ad5` |
| `lanes/esen-eph/.local/esen-eph/pytest-all-20261005-1.log` | `8f6d197852f00c710769ebb831601a2fdc77b029cc4c8b94fbdfe7bd6fcd6e88` |
| `lanes/assessment-track/.local/finalise-assessment-track-final-python.xml` | `eb681b59ddfa48455c55b7140e7bd393c8c7462d54233c7587c063b908297caf` |
| `lanes/assessment-track/.local/finalise-assessment-track-ui.xml` | `6abcfd170cc864191312f6bf5a8e1b9f6d58fa495e889cb58f4ac48fd232df7e` |
| `lanes/packaging/apps/desktop/test-results/nsis-full-factory-03/preflight-evidence.json` | `c8ba3ea61d627eee7e03eb0337eb69b30e3ce13e1eb5f2c41bc069f5db225370` |
| `lanes/packaging/apps/desktop/test-results/relocated-plan.json` | `2534e932e0914a0021c59e6dc042b89e16941b52651ccff50453dc575f40b143` |

The E06 plan remains
`d346fc4b7b82a724dfe7cf2b276ddd0ff3e83b99535957ab68f9437567b27e05`.
Pack 1.1.0 manifest-file SHA256 was directly matched as
`85641e86ed3e3b5430737a45ad606e7e768357a2807dd542303b9b8e758a1fbe`;
its reported canonical bundle hash is
`3f0b712fad056a8857fb9fc913432914cad599096c28aa96fd35e7515076c670`.
These are different hash scopes. Restricted originals and private screenshots
were not opened or copied during this audit.

For 1.1.1, the validated canonical bundle SHA256 is
`6cb81e682328252f5980671e91477330117684c9cc22dc921f7e86206e790fcc`.
Its manifest Git-blob bytes at `604b6d11`/`a6b5d597` hash to
`905bacd815fca300db2d89cc974436764182367d0267814a98c673da6080057b`.
The four inherited clinical payloads were compared as JSON, separately from
those file/bundle hash scopes. Their equality does not assert new clinical
currency or a larger corpus.

## Counting and native provenance ledger

| Observation | Honest scope at this baseline |
| --- | --- |
| Historical renderer 407/407, 33 files; typecheck/Vite/Electron builds | Completed R04 receipt. Later Office renderer 417/417, 34 files, is a separate R14 receipt. Neither is added to the other or promoted to final source acceptance. |
| Historical full backend collection: 901 | HDD attempt interrupted. SSD attempt reached 100% but disk exhaustion/finalization failed: retained 390 passes, 166 failures, 331 errors, 14 skips. It is a failed run, not 901 passes or diagnosed product defects. |
| Three completed disjoint targeted selections | 39 priority + 44 integrated + 13 capacity = **96 distinct targeted passes**, exits zero. Direct summary says `complete=false`, `expected_tests=901`, and only 52 finalized tests from the full partition. Its 97 distinct finalized observations include the separate compact format-1 diagnostic. Neither 97 nor 96 establishes full regression. |
| Interrupted ordinary/engine attempts | Ordinary selection: 332 passed calls/one setup skip, stopped before finalization; overlapping selections are not added. Interrupted engine attempt: one passed/four failed calls without assertion summary/JUnit. Later serial format-1/format-2/PDF/PNG results remain distinct reruns. |
| Historical regression queue receipt, 11:12:23 UTC | Original `b2`: 1,146 collected/1,095 selected/51 excluded, before the extra harness check. R24 now records its terminal recorder-conflict exit 1. Partial progress never became an application pass; this older inventory does not describe `b3`. |
| New application receipt `C:/rn-finalise-20261005/b3/` | `run.json` pins `2d16bd58eedad9d42adef071b42ba68afa482eea`; production paths match `9d26f1ee`, not final parent source. Inventory: **1,147 collected, 1,095 selected, 52 excluded** (13 capacity, 19 engines, one external collection, two native, 17 harness). At 14:35:12 UTC final result/session/outcomes were zero bytes and JUnit absent. Incomplete; no assumption that an actor is still running. |
| New pinned CPU selection R20 | Nineteen finalized passes/exit 0 at `50aac06c`, with complete unique JUnit identities. Only **four** intersect `b3`'s 19 excluded engine IDs: text hybrid, PDF, PNG and HybridChunker table checks. The fifteen Office checks are not those other fifteen exclusions. No exclusion set is closed by matching totals alone. |
| Actual engine checks outside that new selection | Fifteen excluded identities remain outside R20: four backup/recovery, three temporary attachment, three byte-extraction/responsiveness, two actual Mem0, three runtime/helper checks. Earlier receipts R02/R06/R07/R13 retain their scopes; final-source relevance, installed/retention/recovery gates remain separate. Exact IDs are in `.local/audit/reconciliation-provenance-20261005.json`. |
| New content/Assessment/consumer suites | Content 121 terminal passes (R21); Assessment selections 33/12/29 and UI 10 overlap (R22). Consumer focused 47, combined 127/one failed, final Learn 46 (R25). Neither the combined failure nor missing actual producer/consumer integration is concealed by adding totals. |
| Library/Office/subscription focused counts | The 38 parent Library checks, worker overlapping scopes, 60 Office checks with one deselection, repaired one-test Office restore, image/capture suites and R17's 183 controlled checks retain their own inventories. No aggregate product pass count is constructed. |
| Old matching unsigned installer | Product `3ff9b0d6145c8d52f4c9e9b0a3009f0fc351c4cc`; installer 965,928,451 bytes, SHA256 `49f82a58b227c3d572747c3b282fdec20c09fe03777e878c9ba8125281460ed2`; NSIS exit zero, 432.751 s. Installed EXE `38d56a3887c2acf0e8b0db8d45047e59471723cbf3f557253f5f8a77691b3cb9`; ASAR `8ea2cab31aaefb3ea56ca37ad524307c4c342538421811fbebe6ec80225c66f0`. |
| Old native timings and later close failure | Isolated old matching Flow readiness 166.522 s and physical close 8.245 s are development-machine observations. Later loaded normal close failed (R16). The correction and package preflight cannot substitute for new matching normal-queue close/reopen. |
| Dated learning-profile snapshot | October 5, 04:51:26 UTC: 7,307 documents, 16,271 passages, 672 ready jobs, 6,634 queued, one embedding, four historical failed revisions. Subsequent seven selection cancellations and later admissions make this a historical snapshot. No current count or full acquired-corpus readiness is inferred. |

No cumulative clinical, content-review, extraction-accuracy or release pass count
is inferred from software assertions. Actual engines on synthetic fixtures
establish their bounded behavior; they do not complete model-dependent or
installed product journeys by themselves.

## Capability and coverage claims to reject or correct

| Claim | Evidence-based disposition |
| --- | --- |
| “ESENeph has no formal mapping” or “the two consumer code defects remain unfixed” | Obsolete baseline statements. R21 supplies dated partial mapping; R25 resolves the terminal/error defects at application level. Their live/installed gates remain open. |
| “Available ESENeph means complete exam simulation/blueprint, human review or official endorsement” | False. 1.1.1 explicitly reports `status=partial`, `exam_simulation_available=false`, `independent_human_review=false`, `official_endorsement=false` and zero five-option-format questions. The current payload and Assessment copy preserve those limits; no new false full-exam claim was observed. |
| “160 questions, 26 cases and zero objective-link gaps meet every content requirement” | Unsupported. Those are general-bank/link counts. The mapped exam pool has 152 families, eight excluded questions and substantial urology, rare disease, PD/HD, transplant-aftercare and other facet gaps. The complete explanation/evidence/question/case/update matrix still needs adopted-cell accounting; minimum 150 and breadth are unchanged. |
| “Release 1.1.1 refreshed clinical sources or added 121 reviewed clinical items” | False. The 121 is a software-test count. Questions, cases, sources and coverage JSON equal 1.1.0; validation records zero new clinical-review rows. Mapping review dated October 5 is distinct from inherited clinical snapshots. |
| “All programme consumers are verified together” | Unproved. R22's actual UI/API tests use a synthetic producer. Parent has integrated actual 1.1.1 but no combined receipt is read here. R22 covers Assessment; Cases/Study/home consumption is not established by a Study preference selector or mapping producer. |
| “The newest 19 CPU passes close all 19 excluded engine tests or prove all five selected engines” | False. Exact-ID overlap is four; R20 performs no Mem0 extraction/Qdrant recovery. Office conversion checks use pinned tokenizer without Office vectors. Successful OCR is not clinical image interpretation. |
| “The full backend is green” | False at this cutoff. `b3` lacks terminal receipts/JUnit; `b2` failed finalization. A future completed `b3` would still have a pre-wave production baseline and explicit exclusions. Final parent paths changed in knowledge, Learn/runtime, Assessment/content and renderer. |
| “NSIS preflight/Plan and five C confinement checks prove the final installed app” | False. Synthetic compiler outputs were not executed; Plan is read-only and at an older revision. The parent source-level C prerequisite is resolved, but no final freeze/manufacture/install/journey receipt is read. |
| “Available Library originals are searchable/current, Office labels are exact native jumps, or queued E06/E07/L03 files are all ready” | Unsupported. Original availability, extracted passages, eligibility/currentness and indexed readiness are separate. No-text images are valid originals with zero search passages; Office/TIFF use external viewers. Admissions and unread component/EMF holds remain distinct. |
| “Selected-import dispatch counts or eight-page queue bound establish native throughput/peak RAM” | False. R27 uses controlled scheduling and cache seams; it records no native time/RAM guarantee. Normal-queue responsiveness and eventual selected readiness still need matching installed evidence. |
| “Codex connected/Astra available proves successful explanation, image analysis or automatic Memory” | False. Real attempts hit `subscription_limit`. Allowed models remain Codex GPT 6.1 Sol/GPT 6 Astra/GPT 6 Luna and OpenCode Go MiMo V2.6 Pro/DeepSeek V4.1 Flash; Go learning stays paused. No unapproved model, paid API fallback or implicit subscription switch may close this gap. |
| “Unsigned or no separate clean PC/VM prevents current acceptance” | Obsolete under the October 5 owner decision, R28. Current-PC matching installation, OS-only PATH, real journeys and recovery are still required. Historical unsigned/development-machine observations are retained honestly. |

## Requirement-by-requirement ledger

IDs below decompose the existing stage requirements for audit reference. They
do not change targets or create new product decisions. “Bounded” means a
completed receipt exists for the stated scope; “open” or “partial” means the
required integrated/release proof is still missing. Every stage retains gates.

### S0 — Runtime adoption and delivery foundation

| ID | Requirement | Reconciled evidence | Remaining gate / disposition |
| --- | --- | --- | --- |
| S0.01 | Immutable Hermes adoption, patch provenance, source layout and scoped licences | R01 pins upstream and manifests; MIT/CC BY scopes are recorded. | Bounded source adoption. Final distributable dependency/artifact notices and inventory still need reconciliation. |
| S0.02 | Controlled runtime/tools/context; no unapproved secondary calls, credential discovery or persistence | R01/R17 actual Hermes/SDK paths with controlled HTTP and filesystem guards. | Bounded policy evidence; preserve the same policy in final packaged paths and all live foreground/background operations. |
| S0.03 | Versioned process contracts, IDs, migration coordinator and isolated storage | R01/R05–R13 use canonical SQLite/contracts and isolated profiles. | Final populated upgrade, interrupted migration, unsupported-version refusal and install identity isolation need matching evidence. |
| S0.04 | Protected deliberate optional retrieval keys, activation and usage/cost controls | Runtime/architecture contracts and controlled retrieval/Updates tests. | No new live keyed adapter accepted here; reconcile adapter-specific auth/quota/cost-cap receipts. Retain a key-free route. |
| S0.05 | Native Windows runtime starts with OS-only PATH on this PC | R03 embedded CPython/Electron and OS-only PATH on the older installation; current target R28. | Fresh matching unsigned installation on this PC after final freeze. Record actual OS/CPU limits; no separate clean PC/VM is required. |
| S0.06 | Bundled Docling/OCR/FastEmbed/LanceDB/Mem0 helpers perform offline round trips | R02/R07 plus R20 completed pinned CPU checks; Office uses tokenizer-only conversion in that batch. | Selected local engines are established at bounded fixture scope. Final bundled extraction/OCR/index/memory round trips under OS-only PATH and exact assets remain open. |
| S0.07 | Compatible pins, hashes, tokenizer/native binaries, CPU paths and no implicit downloads/cloud fallback | R01/R02 pins and manifests; R20 helper/file fingerprints; R23 public reuse and packaging admission guards. | Revalidate final bundled bytes/terms/source-to-artifact correspondence. Plan/preflight or helper readiness cannot establish final payload acceptance. |
| S0.08 | Exact five-model/account/input capability matrix, automatic routing/manual override | R01/R17 controlled guards; R16 live Codex catalogue exposes Astra only. | Sol/Luna absence is honest unavailability. Go learning remains paused. No availability row is a successful input/generation row. |
| S0.09 | App-owned authentication, real response per advertised available connection, stream/Stop/restart | R16 intentional connection accepted, real image/text requests quota-failed. R17 compaction Stop and R25 terminal/error consumers repaired in controlled tests. | Successful authorised live response, stream/Stop/retry/restart and required image path remain open. Consumer implementation gaps are resolved at test scope. |
| S0.10 | No-save sentinel absence, bounded resource/latency/installer measurements | R01/R02/R06 guard scopes; R03 dated size/timings. | Full matching installed scope/error/crash/handoff scan and same-PC CPU/RAM/latency/support observations. Older-source measurements do not benchmark the final source. |
| S0.11 | Schema compatibility, no implicit downgrade; app rollback distinct from data restore | R11/R13 immutable pack/canonical restore checks. | Matching upgrade/rollback and newer deletion-ledger preservation need final combined proof. |

### S1 — Ask, explain and resume

| ID | Requirement | Reconciled evidence | Remaining gate / disposition |
| --- | --- | --- | --- |
| S1.01 | Flow shell, connection controls and normal Windows launcher | R03/R12 older native shell; R22 built Flow font loaded in a lane preview; R28 current-PC target. | Final matching installed launch, ingestion-active shutdown/reopen and profile/account binding. Do not carry the historical HTML font observation forward as a newly observed failure. |
| S1.02 | Direct and guided explanations/follow-ups across nephrology | R06/R12 controlled local producers/renderer; broad original topics R11. | Successful approved-subscription direct/guided multi-domain journey; quota-failed input supplies no completion. |
| S1.03 | Streaming, selected-subscription model override, Stop/retry | R01/R17 controlled SDK policy/Stop; R25 explicit Stop gives one terminal while external task cancellation propagates. | Final matching UI and deliberate live Stop/retry/model-override journey. No partial output is committed or captured. The old missing-terminal code gap is resolved. |
| S1.04 | Ordinary study history resumes/deletes after restart; case branches remain volatile | R06/R08 actual SQLite/API retention, stale-resume and version guards. | Bounded local persistence. Reconcile final installed study resume/delete and crash/error paths. |
| S1.05 | Actionable offline/auth/quota/model errors preserve work, without fallback | R16 quota failure; R25 known public codes retain safe application-owned recovery, with synthetic retry/unknown-message checks. | Final native/live errors preserve work and selected account/model. Old generated-practice code collapse is resolved; provider or unknown bodies remain redacted. |
| S1.06 | Sources/unverified answers visibly distinguished; no canned production answer | R05/R12 cited local routes and retrieval failure states. | Source-grounded live answer and freshness lookup without upload, including unavailable retrieval, remain open. |

### S2 — Material, evidence and cases

| ID | Requirement | Reconciled evidence | Remaining gate / disposition |
| --- | --- | --- | --- |
| S2.01 | Useful direct text, text-PDF and scanned-PDF/OCR through selected pipeline | R02/R05/R06 historical native/scanned input proofs; R20 actual text, PDF and PNG CPU round trips with exact originals/regions. | Matching native text/text-PDF/scanned-PDF/image import, query and citation across domains; final fidelity/reading-order/units/tables and failure handling. R20 alone does not cover scanned PDF or temporary attachments. |
| S2.02 | Preserve valid no-text image originals; separate OCR from model interpretation | R15 actual zero-passage PNG original API; R26 controlled Available/no-text/original UI states. | Matching native import/view/Save/Cancel/delete with truthful no-searchable-text state. Successful model image interpretation remains a separate live gate. |
| S2.03 | Durable selected Office supplements, actual slide/sheet/item/table locators and original bytes | R14 controlled-vector Office API/recovery; R20 fifteen actual Docling/HybridChunker/tokenizer Office checks; R26 typed locators/download presentation. | Matching native DOCX/PPTX/XLSX admission, actual embedding/search where text exists, original Save/Cancel and citation. No automatic Office jump/highlight or acquired-file readiness is established. |
| S2.04 | Exact revision/passage/page/region citation and original access, unknown locators remain unknown | R05 passage/revision-bound APIs; R20 PDF/PNG exact bytes and page/region assertions; R26 Office/image original presentation. | Final installed exact-page and Office/image original access, Save/Cancel and reader accessibility. A locator label is not an independently observed native jump/highlight. |
| S2.05 | Stage eligible revisions; failed/cancelled replacement retains prior active revision | R05/R15 publication/replacement guards; R26 earlier-original UI continuity; R27 admission/priority canonical race fences. | Final matching cancel/delete during ingest, failed replacement and restart cannot republish stale work. Synthetic scheduling is bounded application evidence. |
| S2.06 | LanceDB native hybrid retrieval, filters, paraphrases/acronyms across editions/domains | R02/R05/R13 earlier local retrieval; R20 actual FastEmbed/LanceDB text retrieval and rebuild, with PDF/PNG evidence retrieval. | Final active-revision/scope/currency and varied paraphrase/abbreviation searches across domains. No full corpus, memory or Office embedding coverage is inferred from R20. |
| S2.07 | Authorised local import, official user download, per-file edition/rights/attribution, originals preserved | R18 exact classified/E06 API admissions; source register remains authority. | Admissions are queued. Reconcile eventual selected readiness and visible attribution; retain component/format holds, unknown currentness and operation-specific limits. No reimport. |
| S2.08 | Malformed/encrypted/oversized inputs and cancellation handled before unsafe persistence | R05/R14 container boundaries; R20 Office empty/malformed/no-link/no-LibreOffice-fallback and temporary-byte refusal checks; R26 draft/retry UI. | Matching installed malformed/encrypted/oversized/error/cancellation states retain originals and prior active revisions. |
| S2.09 | Freshness-sensitive Explain automatically retrieves eligible evidence without an upload/paid key | R10 bounded free reachability plus controlled pipeline; R05 retrieval eligibility. | No completed live no-upload Explain → fetched passage/date citation journey accepted. Failure/unverified state must be exercised too. |
| S2.10 | Optional keyed retrieval has deliberate activation, protected keys, quota/cost-cap errors | Controlled adapter/connection scopes exist; no incidental billed calls in this audit. | Reconcile exact selected adapter receipts; key-free required flows remain available. |
| S2.11 | Temporary/unclassified case data and every derivative remain absent from durable stores | R01/R06/R08 retention fences; R25 controlled temporary cancellation/generated-output absence; R20 temporary Office refused before assets/files. | Final installed forced-error/crash/compaction/handoff/export/backup sentinel scans. R20 did not rerun temporary PDF/PNG no-write checks or Mem0 capture. |
| S2.12 | Explicit Save retains case snapshot/attachments; saved follow-up and restart/delete semantics | R06 real Save/restart/delete and shell disclosure correction. | Final native Save/reopen/follow-up plus discussion using approved subscription; one quiz start or unsaved preview is not completion. |
| S2.13 | Physical derivative cleanup, old Lance versions, delete-during-ingestion and stale-job exclusion | R05/R07/R15 actual/controlled cleanup and canonical guard scopes. | Final index cleanup/restart and cross-module export/restore with retained newer deletion markers. |
| S2.14 | Interactive Library stays usable while the normal queue progresses | R03 older normal Library observation; R27 selected-batch hint/fairness/restart and warm-cache checks are synthetic scheduling evidence. | Sustained matching installed normal-queue responsiveness, selected readiness, resource/latency and close/reopen. Thirty-eight dispatches and queue size eight are not native timing or a total RAM bound. |

### S3 — Assessment and content

| ID | Requirement | Reconciled evidence | Remaining gate / disposition |
| --- | --- | --- | --- |
| S3.01 | Retain measurable broad content targets; original reviewed questions/cases with evidence terms | R11/R21: 1.1.1 retains 27 topics/56 objectives/160 questions/26 cases; minimum 150 unchanged; clinical payload JSON equals 1.1.0. | Payload counts/links are met; complete explanation/evidence/question/case/update cells and exam-domain depth remain to reconcile. Mapping review is not fresh clinical or independent human review. |
| S3.02 | Actual immutable original pack installs/activates and consumers share it | R11/R12 historical installs; R21 content bootstrap/version/restart checks for actual 1.1.1; R22 separately tested synthetic track consumer. | Combined parent producer/consumer checks using active immutable 1.1.1, then matching installed activation/upgrade and consumer pins. Historical attempts retain predecessors. |
| S3.03 | Committed deterministic scoring, rationale sources, mistakes, pause/resume | R12 actual published-key producer/API and UI journeys. | Bounded local scoring. Complete final matching Test/feedback journey across domains remains open. |
| S3.04 | Idempotent restart avoids duplicate answers/exposure; stable item/family/key versions | R11/R12 transactional/exposure rules; R21 actual pinned attempt survives activation/restart; R22 catalog/start/family/version contract checks. | Final integrated Test commit/resume/retry/cancel/help with exact item/family/key versions and no double submission. Overlapping lane tests do not prove the parent combination. |
| S3.05 | Corrected/withdrawn keys annotate historical results without rewriting them | R11/R12 immutable predecessors/withdrawals and R10 source annotations. | Bounded correction rules; final installed correction/update/history journey still needs reconciliation. |
| S3.06 | Fresh, assisted, repeat and generated aggregates remain separate after mode switches | R12/R17 actual stores with controlled generated output. | Final UI transitions and source help; no generated score counted as reviewed mastery. |
| S3.07 | Reserved bank never leaks into Explain/practice context | R11/R12 teaching/exposure guards; R21 key-free metadata; R22 no key resolution during catalog reads, eligibility and exact mapped pin selection. | Final integrated Explain/generated-practice retrieval boundaries and programme consumers keep reserved bank material excluded. |
| S3.08 | Generated practice is labelled, uses approved generation and keeps unreviewed keys separate | R12/R17 controlled generated routes; R25 safe provider codes, explicit retry, failed-output suppression and generated/unreviewed separation. | Successful live generated practice and matching error/retry UI; no synthetic completion or generated result is promoted to reviewed mastery. |
| S3.09 | ESENeph insufficient coverage is honest; no complete exam simulation without supported blueprint/length | R21 dated partial C01 alignment: 152 mapped families, eight excluded, eleven partial/gap domains, zero format-compatible questions. R22 Assessment presents partial preparation. | Test the combined actual 1.1.1 producer/Assessment consumer and Cases/Study/home alignment behavior. Full exam simulation remains unavailable; disclose best-of-five mismatch and domain/depth shortfalls. No complete-blueprint claim. |

### S4 — Memory, progress, plan and home

| ID | Requirement | Reconciled evidence | Remaining gate / disposition |
| --- | --- | --- | --- |
| S4.01 | Hermes/Mem0 OSS + explicit FastEmbed/local Qdrant; SQLite authority and rebuildable generations | R07 actual local engines, history purge/recall and physical rebuild. | Final installed engine/artifact identity and populated learner-index recovery. |
| S4.02 | Durable idempotent eligible capture queue with references/provenance and correct scope | R06/R08/R17 eligible answer/outbox guards; R25 Stop/interruption creates no partial answer or capture job. | Final workers/restarts and distinct-lesson capture require matching evidence; eligibility/outbox tests are not live Mem0 extraction. |
| S4.03 | Automatic general learning points through approved live subscription, without case/prompt facts | R08 real Mem0 extraction flow uses controlled generation; R16 live attempts quota-failed. | Successful authorised Learn answer → autonomous capture → canonical point → recall, with provider/model identity and no case data. |
| S4.04 | Deduplication, editable records, revision conflicts, physical history/index purge and suppression | R07/R08 actual/controlled correction/delete/replay guards. | Final correction during summarisation, deletion during capture, queued reindex/restart/restore scans; cleanup pending is never represented as complete. |
| S4.05 | Relevant corrected personal context within separate library/memory budgets, no invented mastery | R01/R07/R08 context/recall guard scopes. | Live multi-domain personalised answer changes after correction; deleted/superseded context stays excluded. |
| S4.06 | Plan uses goals/time/exam date/observed mistakes, with free browsing and manual overrides | R09 real mistakes/manual persistence; R21 mapping producer; R22 tests Assessment only. | Final installed plan/overrides and Cases/Study/home mapping behavior. Study general/eseneph preference alone does not establish consumption of content-owned domain metadata. |
| S4.07 | Useful new-user home: Ask/Resume/review/updates, real records | R09/R12 local new/existing learner UI and producer evidence. | Matching native empty/history/error/scaling states and complete linked activity return. |
| S4.08 | Versioned export/restore with attachments/provenance and deletion limits on an isolated same-PC target | R07/R13 local engine/canonical restore; earlier larger delivery had zero Memory facts. Current scope R28. | Populated learner/case/study restore in a second isolated installation/profile on this PC, rebuilding LanceDB and Mem0/Qdrant; preserve newer deletion markers and disclose older-backup limits. |
| S4.09 | Expected memory volume, paraphrases/abbreviations, repeated capture and quota/index failure recovery | R07 bounded earlier semantic/race tests; R25 no-partial-answer capture; R24 explicitly excludes actual Mem0 helpers. | Expected-volume and failure/retry recovery on relevant final source. R20 knowledge-only engine passes cannot close learner-memory coverage. |

### S5 — Current evidence and updates

| ID | Requirement | Reconciled evidence | Remaining gate / disposition |
| --- | --- | --- | --- |
| S5.01 | Bounded in-app source checks, explicit opt-in, durable successes/failures and topic-only queries | R10 actual scheduler/API/store with controlled transport and three dated free requests. | Final installed check/stop/shutdown/reopen behavior; no raw case queries or background actor after app close. |
| S5.02 | Final/draft, chapter replacement, corrigenda, expiry, removal/retraction remain separate | R10 exact source-copy/outbox/journal guards and controlled publisher sequences. | Actual publication/source-review receipts; no fetch/import date or fixture review establishes current final guidance. |
| S5.03 | Detected changes separate from explicitly reviewed educational entries, with dates/source links | R10 pending discovery/review workflow and R12 UI. | An actual eligible changed source reviewed, displayed and linked to affected objectives on final product. |
| S5.04 | Correction flags bank/learning history without rewriting keys/results | R10/R11/R12 local annotations and immutable attempts. | Final combined update → affected item/plan/feedback journey with actual review evidence. |
| S5.05 | Offline/failed/stale/restricted reimport accurate, same-URL change and exact-copy review reproducible | R10 controlled restart/exclusion/dismissal/re-review checks; R13 current-only excluded unreviewed sources. | Final native failure/reimport states and continued current-only exclusion; partial discovery is not complete acquisition. |

### S6 — Complete, installable product

| ID | Requirement | Reconciled evidence | Remaining gate / disposition |
| --- | --- | --- | --- |
| S6.01 | Required broad-topic and ESENeph cells: explanation/evidence/questions/cases/update sources | R11 broad original content retained; R21 formal partial 1.1.1 mapping; R22 partial Assessment consumer. | Full adopted required-cell manifest and consumers across all 27 topics/56 objectives and ESENeph domains. Counts and zero declared objective-link gaps are not complete depth or five-column coverage. |
| S6.02 | Case → Explain → practice/Test → feedback → Memory → plan → Updates across domains | R06–R12 bounded parts; R21/R22 producer/consumer parts; R25 controlled subscriptions. Earlier preview only started a quiz. | Matching installed multi-domain case → Explain → reviewed Test/generated practice → feedback → Memory → plan → Updates and return/resume, with real authorised generation/capture. Connected screens are insufficient. |
| S6.03 | Completed relevant backend/renderer/regression on integrated source, failures/exclusions adjudicated | R04 history; R20 19 CPU passes; R21/R22/R25–R27 focused scopes; R24 b3 has no terminal/JUnit at read cutoff. | Finish source-attributed application accounting; reconcile every later changed path and appropriate affected tests, renderer and separately excluded coverage. No partial or overlapping totals become a final-source pass. |
| S6.04 | One Flow system; keyboard, screen reader, text scaling/resize/reduced motion; loading/empty/errors | R12 existing focus/resize checks; historical font observation R19; R22 built Source Sans 3/wide screenshot, with narrow preview unavailable; R26 controlled Library states. | Final matching keyboard/screen-reader/text-scaling/resize/reduced-motion, empty/loading/error and native-original reader access. Retain Flow/Renal flow; no redesign is required by this audit. |
| S6.05 | New source freeze → exact payload → manufacture/install → normal lifecycle matching that source | R03 proves old 3ff9b0d6; R23 compile-only/Plan machinery; R28 integrated C Proof confinement, parent-reported 5/5. | Parent final freeze, refreshed exact payload, real unsigned manufacture/install, artifact/backend hashes, OS-only PATH and normal queue close/reopen with account/profile preservation. C guard/preflight passes are not installed Proof. |
| S6.06 | Unsigned current-PC delivery, update provenance, static distribution and complete notices | R03 older unsigned installer; R23 pin/licence admission; R28 accepts current unsigned delivery. | Final artifact notices/inventory and update source/artifact provenance remain required. Signing and authenticated signed-distribution checks are optional future work, not blockers for this accepted build. |
| S6.07 | Install/upgrade/rollback, database migration, uninstall/data-retention and isolated installation identity | R03 old install and R11/R13 local version/recovery guards. | Final populated upgrade/interruption/rollback/uninstall/retained-data evidence; compatible app rollback cannot silently downgrade data. |
| S6.08 | Backup/restore incl. Office/image originals, citations and both derived indexes; recovery disclosure | R13 data-only recovery; R14 controlled-vector Office round trip; R15 originals; R28 same-PC second isolated target accepted. | Matching native backup Save/Cancel/partial failure → populated restore in an isolated installation/profile on this PC; exact Office/image originals/citations and both derived indexes, with deletion-ledger limits. |
| S6.09 | Plain-language onboarding/running/recovery and truthful capability controls | Existing running/handoff records; R25 consumer error fixes; R26 Library recovery/original controls; R28 current delivery scope. | Reconcile plain-language docs and capability controls to final accepted installation and actual quota/image/Go/currency/recovery states. Launcher acceptance/switch remains parent-owned. |
| S6.10 | Fresh isolated installation on this Windows PC completes required real journeys with bundled runtime | R03 historical development-PC install/OS-only PATH; no final matching journey receipt. Current scope R28. | Unsigned matching installation, app PATH limited to OS/runtime, managed helpers, user-connected approved models, actual journeys and populated recovery on this PC. Record machine limits; separate clean-machine/signing work is optional. |

## Prioritized remaining acceptance and external input

P0 gates precede a final source freeze/manufacture claim. P1 gates establish the
accepted working product on this PC. These priorities organize existing work;
they do not invent a new review panel or require another machine. Signing and
separate clean-machine validation are optional future distribution work.

| Priority / gate | Concrete acceptance receipt needed | Current evidence and required input |
| --- | --- | --- |
| P0 · G2 — terminal regression and source relevance | Recover terminal exit/result/session/outcomes/JUnit and exact inventories for `C:/rn-finalise-20261005/b3/`, or preserve its incomplete outcome. Compare its `9d26f1ee` production trees to the final parent source; enumerate completed affected checks, test exclusions and reasons. Cover content/track, Assessment/provider errors, Learn/Stop, ingestion/queue/API, Library renderer and native confinement changes on matching source. Keep capacity/helper/native scopes separate. | At cutoff `b3` has no terminal/JUnit. R20 is accepted 19-test CPU evidence, not a full or Mem0 pass. Input: parent/lane terminal receipts and final-source affected-test receipts; no provider or user credentials needed. |
| P0 · G4 — actual content/track combination and required coverage | Exercise actual active immutable 1.1.1 → content metadata → Assessment catalog/UI → reviewed attempt/feedback → restart/history; verify exact mapped pins, key-free catalog, family/withdrawal/assistance guards and General versus partial ESENeph counts. Check Cases/Study/home mapping behavior and the adopted explanation/evidence/question/case/update required cells across all topic groups. Preserve minimum 150 and breadth; disclose partial exam-domain depth/format without enabling a full simulation. | R21 producer and R22 synthetic consumer are integrated but not jointly certified. 160 general/152 mapped families; eight excluded; zero best-of-five format; no new clinical review. Input: combined actual-pack receipts and required-cell/review evidence, authored by the existing user/assistant content workflow. Independent human review is not an added prerequisite. |
| P0 · G1 — matching unsigned native product | Parent selects final full SHA after relevant checks, then records exact snapshot/payload/dependencies/helpers/content identities, inventory/notices, actual NSIS manufacture and installer exit, EXE/ASAR/backend hashes and installed provenance. Fresh isolated install must load bundled helpers with OS-only PATH, preserve selected profile/account binding and complete normal queue launch/shutdown/reopen with observed child ownership. | R23 preflight/Plan and R28 C proof confinement resolve source machinery only. Old `3ff9b0d6` remains historical with a later normal-close failure. Input: parent final freeze and serial native/helper slot; final manufacture/install/Proof receipts. No signing identity or separate PC/VM is needed. |
| P1 · G3 — Library inputs, originals, eligibility and queue | On matching install, use synthetic text, text/scanned PDF, PNG/no-text image and DOCX/PPTX/XLSX; record admission → ready/error → actual search where passages exist → exact original/citation → replace/cancel/delete. Exercise native picker, original Save/Cancel/download/decoding, page/region/slide/sheet labels, previous-active-revision recovery and selected/background queue fairness/responsiveness. Record resource/timing observations without extrapolating from dispatch counts. | R20 supplies real bounded CPU evidence and R26/R27 controlled UI/scheduling. Current acquired readiness is not read or inferred. Input: parent matching native/helper receipts. Existing E06/E07/L03 admission identities stay preserved; eventual readiness and only unresolved component/use/format qualifications need reconciliation, not duplicate acquisition or sibling import. |
| P1 · G5 — live approved subscription and automatic Memory | Deliberate app-owned allowed-account tests must complete direct/guided multi-domain Explain, follow-up, streaming/Stop/retry, generated practice and required image interpretation. One completed ordinary answer must autonomously yield a scoped canonical learning point through Mem0, then recall/change after correction and remain excluded after deletion. Record exact connection/model and actionable quota/auth/image/Go states; no partial answer or case facts become Memory. | R25 fixes consumers in synthetic tests; R16 real attempts hit quota. Input: working quota/capability on an explicitly chosen allowed subscription, and intentional app-owned live receipts when the parent schedules them. Catalogue unavailability remains honest; no credential file read, borrowing, fallback or billed API is needed. |
| P1 · G6 — connected journey, retention and populated recovery | Complete installed case → Explain → reviewed Test/generated practice → committed feedback → Memory → plan → Updates/return/resume across varied domains. Force errors/Stop/crash/handoffs and scan every app-owned durable/export/backup path for an unsaved synthetic sentinel. Explicit Save must retain eligible attachments. Native backup Save/Cancel/partial failure → isolated same-PC installation/profile restore must retain populated attempts/study/cases/Memory, exact Office/image originals/citations and rebuild LanceDB plus Mem0/Qdrant. Reconcile newer deletion markers; disclose old-backup limits. | Component/data-only receipts do not establish this final journey; earlier larger recovery contained zero Memory facts. Input: synthetic populated backup and parent-owned isolated same-PC restore/engine slot. A second clean machine is not required. |
| P1 · G7 — current-PC lifecycle and delivery controls | Verify populated upgrade/interrupted migration/version refusal, compatible app rollback, isolated instance identity, uninstall/data retention and source/artifact provenance for any supported update. Record actual Windows/CPU/RAM limits and bundled runtime operation without developer tools in app PATH or first-use helper setup/downloads. Complete final component/content notices and plain-language onboarding/running/recovery against the accepted installed revision. | Unsigned is accepted. Final matching lifecycle/update/migration/recovery notices remain unproved; source guards and a development build alone cannot close them. Input: parent same-PC isolated delivery receipts and final artifact inventory. Optional future signing/clean-machine work does not block this gate. |
| P1 · G8 — Flow access and current evidence behavior | Verify final installed font content/load, keyboard/focus, screen reader, text scaling, narrow/wide resize, reduced motion and loading/empty/error states, including original viewing and partial-track disclosures. Complete eligible changed-source detection → explicit educational review → dates/source links/affected objectives → history/plan flags; exercise draft/final, corrigendum, chapter replacement, retraction, stale/offline/restricted reimport without relabelling old passages current. | R22 proves built wide view/font; narrow verification was unavailable. R10 proves controlled Updates rules/dated reachability, not an actual reviewed changed publication. Input: matching access/journey receipts and an actual dated eligible source/review record with operation-specific rights. Optional paid retrieval keys are not prerequisites. |

G1/G2/G4 are prerequisites for attribution of the P1 installed journeys; work
may proceed in the parent's bounded schedule where dependencies permit. Required
external availability is confined to the chosen account's working quota/capability
and eligible source evidence/use qualifications. Existing source acquisition,
user/assistant review and same-PC isolated verification can satisfy the other
inputs. No additional product decision, external review panel, signing
certificate or second physical/virtual machine is requested by this audit.

Each new parent proof should name the source/commit, precise operation and
fixtures, engine/provider/artifact identities, start/finish UTC, final exit or
terminal state, raw receipt/log/JUnit paths, and explicit failures/skips/limits.
Changed code does not inherit unrelated old passes. Acquisition receipts,
API admission, ready original availability, searchable passages, source
currentness, medical review and release acceptance remain distinct evidence.

The bounded report is ready for the parent. Current-PC product acceptance awaits
the concrete receipts above; no unperformed live/native/recovery work is
certified. Final integration/freeze and launcher changes remain parent-owned.

The preserved baseline verification checked 64 stage rows, 19 evidence IDs and
five receipt/manifest hashes in `.local/audit/report-verification.json`. This
wave retains all 64 stage IDs, updates 36 rows, and adds R20–R28. New audit-only
validation is recorded in
`C:/rn-finalise-20261005/lanes/audit/.local/audit/report-verification-20261005.json`;
provenance/receipt parsing is in `reconciliation-provenance-20261005.json` beside
it. These are document/receipt checks, not additional application tests.
