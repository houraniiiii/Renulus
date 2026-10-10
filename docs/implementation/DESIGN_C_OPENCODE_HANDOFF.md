# Design C integration handoff to OpenCode v2

**Bounded closeout complete.** C-01–C-05 are resolved at the scopes recorded
below. Final product source is **`7a6b4955ff560d6694835e661d3745c545448ac6`** on
**`codex/design-c-integration`**. The documentation-only commit containing this
handoff preserves those exact product bytes. OpenCode is not implemented and
DC21's original default Windows release is not passed; it is deferred to H20.

## Authority and source

The owner's October 10 scope change ends this task at the connected Design C UI
baseline and committed handoff. The integration branch is
`codex/design-c-integration` in `C:/Renulus/dev/repo`. Source baseline for this
closeout is `e09fe0b8da162259394f6785562f751949e0c2fe`; documentation checkpoint
`75b4b503` records the finite list and imports the read-only planning snapshot.
Its [manifest](opencode-plan-snapshot/manifest.json) pins the 99 uncommitted
planning/research files, their source and committed hashes, and older baseline
`528025ff`. No older product source was merged and the planning worktree was not
changed. Existing end-of-file blank lines in the captured research were retained
deliberately; only normal repository line-ending conversion applies in Git.

The [snapshot reconciliation](opencode-plan-snapshot/README.md) governs differences
between those dated drafts and this closeout. H00's final evidence below must be
consumed as an existing prerequisite, not implemented a second time. The H01–H24
migration remains future work except this bounded existing-product repair.

## Accepted UI scope and evidence to retain

These are scoped proofs, not a summed test count or a blanket ticket closure.
The [reconciled editable references](design-c-reconciliation.md) remain the
visual contract. Earlier failed receipts and qualifications remain alongside
the later checks. Synthetic external transport proves producer/consumer
integration, not selected-account authentication or educational answer quality.

| Connected experience | Retained proof / practical boundary |
| --- | --- |
| Shell, saved chats, search, retained destinations | Existing typed navigation, saved/default Learn and Case, archive/search/restore, paged history and retained drafts; same-chat refresh `527bd` and actual local search checks. DC10 Memory/Updates hidden evidence is in `bc149c91`. |
| Home and attachment handoff | Home service and actual Home→saved Chat→explicit attachment review→Reader→restart evidence in [Home EVIDENCE](../../apps/desktop/src/modules/home/EVIDENCE.md). Raw File/draft/send intent stay volatile; no automatic upload or second send. |
| Chat, Case and Projects | Actual saved/temporary promotion, Case context/teaching/handoff/image producer retention and rollback, original-owner cleanup; populated project retrieval/unlink fencing. Relevant source checks are `test_design_c_conversations.py`, `test_design_c_context.py`, `test_design_c_projects.py`. Hidden successful live image generation is not claimed. |
| Notes and project membership | [Hidden Notes](design-c-hidden-notes.md), 20 mounted rights/project/Study-help/delete/ZIP cases in `dc59d4c2` (18 plus corrected two, not a single full green run), immutable revisions and prior-source citations retained. |
| Workspace and readers | [Reader evidence](design-c-review-readers.md): eight categories, typed locators, exact originals, inert HTML/XML, table bounds/formula uncertainty, passage-to-draft, rights and reopened services. PDF selected-text/page repair `f4fc986f` and title/Close repair `f5d36ac9`; affected hidden closeout evidence is added below. |
| Saved Tests, Study/Test and results | Immutable version setup, private-key separation, explicit Study commitment, durable Test choices and final submission; [hidden attempts](design-c-hidden-attempts.md) covers timer/pause/restart/narrow/zoom. `eef19`/`dbd189` policy review retains exact 272-operation inventory and 41 distinct checks; no all-suite total is inferred. |
| Import and generation producers | Actual original→candidate review/edit/remove→personal immutable test→Test, Library text/table/OCR and rights-revoked replay checks; full App topic generation and fictional Chat→card/Workspace→one stable Study start in `assessment-producers.connected.test.tsx`. H00 affects saved generation and is rechecked in this closeout. |
| Home suggestions and nightly | Canonical scalar evidence/cohorts and Memory corrections, explicit five-question Quick practice, dated/error/offline state; actual scheduler→saved setup→Study/Test proof and hidden Off/time/count/reopen in [Nightly EVIDENCE](../../apps/desktop/src/modules/nightly/EVIDENCE.md). New H00 regression rechecks the affected owner paths. |

## Domain and API contracts to preserve

The [public contract](../../packages/contracts/design-c.md),
[typed validators](../../runtime/renulus/design_c_contracts.py), and committed
fixture manifest are normative implementation seams. OpenCode must adapt to
these identities and existing owner transactions:

- A conversation is `(kind, id)`, with `learning`/`case` and typed identities
  `learn_thread`/`case`. Equal IDs across namespaces are independent. Saved
  sidecar revision and original Case revision are separate concurrency pins.
  `/api/v1/conversations` returns `{items,next_cursor}`; sends use stable
  `Idempotency-Key`/request IDs, current revision and SSE. Neutral status/Stop
  never returns assistance content during Test.
- Projects own memberships and goals, not their chats or shared Library
  documents. Unlink tombstones membership identities. Notes reuse
  `knowledge_documents`/immutable revisions; `projects.note_saved_in` runs in
  the caller's transaction. An empty linked-revision search scope never widens
  to global retrieval.
- Reader references pin typed target plus revision/attachment and locator.
  Original bytes, SHA, source terms and separate display/cache/model/derivation
  permissions retain their owners. Legacy Case original authority involves no
  byte copying. Opening, selecting a passage or linking a project does not grant
  model-input rights. Temporary data and raw Home intents remain volatile.
- Saved tests use immutable version IDs/ordinals and original provenance;
  collection lifecycle controls new starts. `pinned_version` and
  `pinned_provenance` are private backend seams, not public start authorization.
  `publish_version` is called within its producer's transaction and guards.
- `/assessment/test-attempts` takes a typed saved-version reference, explicit
  `study`/`test`, timing object and stable command key. Navigate by the returned
  attempt ID; never start again from a version-only card. Durable Test drafts
  are not learning evidence. Study commits and final Test submission own scores,
  blanks/exclusions, assistance/repeat flags and bank/personal cohorts.
- Historical `version_id`/`attempt_id` and independent private snapshots are
  retained when live nullable references become unavailable. No hard pruning
  edge may erase attempt/report/job provenance. Public setup/attempt views do
  not expose keys prematurely. Independent report snapshot/2 preserves the
  exact relevant original and private producer metadata; neutral receipts stay
  `{id,status,created_at}`.
- Generation keeps 5/10/20 validated batches, original request/count/hash,
  explicit accepted-shorter count, bounded call budget, checkpoint/execution
  identity, selected route, source/epoch/policy guards and atomic publication.
  Imports preserve exact private originals, offsets and explicit human key
  review. Fictionalisation keeps raw input volatile and independently reviews
  the generalized artifact before durable publication; renderer attestations
  are not trusted.
- SQLite remains canonical. Memory/LanceDB/Qdrant are derived owners with
  explicit rebuild/invalidation. Preserve typed tombstones, complete composite
  keys, migration inventory/checksums, schema1 acceptance and schema2 exports.
  Restore dirties local engines, increments non-exported context generation,
  interrupts jobs and erects old-evidence inference barriers. These are not
  OpenCode paired-store protocols.

## Existing adapters to replace later

Keep these working until the corresponding H consumer is connected:

| Current authority / code seam | Future owner |
| --- | --- |
| `runtime/renulus/runtime/manager.py`, approved subscription/runtime adapter and capability observations | H01/H03/H04; preserve domain policy and unknown availability, repair H03's auth limitation |
| Learn service/repository plus conversation streaming, Case repository/streaming and volatile run events | H02/H05/H06/H21; migrated execution/transcript/context move together, original domain IDs remain |
| Hermes context/compression integration, existing summary/history representation | H10, then optional H11; no duplicate context owner or speculative tree here |
| Saved generation, legacy generated practice, imported refinement, trusted fictionalisation | H12/H13/H22/H23; retain validators, budgets, snapshots and atomic publishers |
| Home, nightly and Updates model dispatch | H15/H17/H16; retain current preference/occurrence/cache/checkpoint contracts |
| Memory capture task/thread lifecycle and canonical evidence material resolver | H24 before H05/H18; retain current scalar resolver and restore barriers while adding actual settlement and transitive dependencies |
| Current single-store backup/deletion and Windows delivery scripts | H18/H20; extend to consistent runtime/domain store generations, retain originals and rollback evidence |

## Explicit research dispositions

The [captured findings ledger](../research/2026-10-10-opencode-integration/findings-disposition.md)
contains dated evidence. This table assigns every finding to its next owner;
planning disposition is not product repair.

| Finding(s) | Current disposition | Owner |
| --- | --- | --- |
| Generation retrieval mismatch | Bounded current-product repair in this closeout; final evidence below | H00, consumed by H12 |
| Memory recapture; current profile-global scopes; resolver RPC lock hazard | **OPEN** transitive lineage and canonical dependency authority required; same-source suppression and restore quietness do not close it | H05 M5+M1+integration; H06 preserves scope |
| Deleted receipt payloads, including create `target=new` | **OPEN** retained/exported result payload/hash after deletion; reference-only live receipts and opaque retired outcomes remain work | H06 M1/M3+F0, integrated H18 |
| Worker close lifetime | **OPEN** coroutine completion is not thread settlement; prior probe did not demonstrate corruption/late facts | H24 M5+F0 before H05/H18 |
| Capability reset / authentication availability | **OPEN** retained connection can appear available after 401 clears observations | H03 F0 |
| Artifact identity; full host acceptance | Deferred pin/build/run one real source cohort; no integrated OpenCode host proof | H01, then H20 |
| Late policy readiness; delayed recovery cleanup | Deferred real activation/admission/quiescence and child ownership proof | H01/H04, H01/H07 |
| Bypass surfaces; failed reload | Deferred all-dispatch policy and effective atomic registry/configuration activation | H03/H04/H09 |
| Temporary storage; IPC/reconnect/Save | Deferred separate volatile graph/spills and explicit Save promotion; correct older H06 label | H21 + H01/H02 substrate |
| Current work already landed; publication fence | Preserve current owners/IDs and existing guarded transactions; bind future IPC authority without recreating domain jobs | All migration slices; H12/H13 |
| Typed cascades | Existing corrected single-store evidence retained; extend typed relations, do not reintroduce obsolete generic cascade fixes | H18 |
| Nightly semantics | Retain cold-restart future boundary versus app-running catch-up; later reconcile runtime occurrence handoff | H17 |
| Model roles; attempt/output ambiguity | Deferred selected-account capability/evaluation and durable dispatch allowances; no measured best-role claims | H03/H04/H10 |
| Context tail; usage estimate; article units | Deferred complete eligible context, route-aware final budgets and separate byte/token accounting | H10/H11 |
| Cross-store consistency | Deferred paired manifests, quiescent generations and compatible rollback; current nine recovery gates are one-store evidence | H01/H06/H18 |
| Current path behavior | Retain dated long-path helper limitation; validate supported delivered paths | H20 |
| Unowned model producers | Explicit future adapters for fictionalisation and import refinement, not accidental fallback execution | H22/H23 |
| Optional strategy blockers | Exact history remains mandatory; evaluated tree/additional providers remain optional beyond their own gates | H10/H11/H18/H20, H19 |
| Instruction precedence | Retain user instruction priority and pinned instruction plus current revocation semantics | H08/H10 |

## Preserved delivery and data evidence

The selected normal installation remains Flow `f1c49444` at
`C:/Renulus/app/Renulus Development.exe`, using the unchanged owner profile
`C:/Renulus/data/learning`. It is not this review baseline.

The isolated packaged Design C candidate is exact
`4c2898682d65b36d0281f890298ac38697e224b7` at
`C:/Renulus/scratch/design-c/delivery/installed-4c289868`. Its manufacture,
inventory and silent installation passed; it predates these closeout repairs.
Core07 `c-d4825308` preserves five admission/chat/project gates and its real
Reader failure screenshot. It is not an eight-reader or final-release pass.
No new package is required merely to satisfy the superseded cutover goal.

Installed recovery `r-179af503` preserves nine gates and six effective local
engine rebuilds before retrieval, originals, deterministic backfill, partial
score and typed deletion across JSON/ZIP1/ZIP2. Receipt SHA-256:
`70494c3dd8bd1d8e5307c336b32979fd3b30023e9a49201466d2edfde6431b1a`.
Journal SHA-256:
`d4fe65c701f68d51fc85664d909c93acbb86924bc4bb9435aa629d9ed9db032f`.
It proves owner reopening within one interpreter, not populated Learn/Case
transcript reopening in fresh Electron: its old seed had empty conversations.
The strengthened seed guard and prepared seed02 inputs remain available but
unexecuted. JSON is records-only; ZIP hydrates originals. Preserve those limits.

Reuse `test_design_c_populated_upgrade.py` and its genuine old runtime
`1b30a896`/schema1 fixture, typed migration/restore tests, exact-original reader
fixtures, actual producer tests, the controlled hidden profiles and
[delivery evidence](design-c-delivery.md). No owner's state or credentials are
part of those fixtures. Final native dialogs, authentication, full installed
eight-reader/fresh-process recovery and default selection remain H20 gates.

## Final closeout evidence and review launch

H00 is fixed by `fa3b590cd40de145c198a64168aa46b82384e2bc`. Shared retrieval
requires an explicit callable; the legacy owner passes its actual run guard,
while the saved owner re-resolves its current job/execution, policy, epoch,
route, source and Nightly authority before and after each retrieval await,
including failures. No transaction is held over that I/O. Existing checkpoint
and final-publication transactions remain in place.

`C:/Renulus/scratch/design-c/h00/red02.xml` reproduces the public route failure;
`green01.xml` has 13 focused passes. `affected-full01.xml` has 160 passes and
one stale missing-owner fixture failure (the real assembled app now registers
Nightly). That test now deliberately removes the capability for its intended
missing-owner case and passes in `nightly-fixture01.xml`. This proves 161 unique
affected cases across 160+1; it is not a single full-green-run claim. The only
production change is the explicit retrieval guard, not a weaker Nightly guard.

The full App Tests-generation and Chat-fictionalisation journeys pass 2/2 in
`connected-ui03.xml`, using real SQLite/HTTP/domain producers and only synthetic
external inference. The reusable test now pins its actual committed source and
always records cleanup diagnostics (`d10aaa66`). Earlier `connected-ui.xml`
refused an outdated hardcoded source snapshot; `connected-ui02.xml` passed both
journeys but failed fixture shutdown reporting. A read-only process check found
no remaining fixture process, and the final rerun reports clean owned cleanup.
Its actual receipt is `C:/Renulus/scratch/design-c/dc-review-data/ap-6NZiue/receipt.json`.

Saved Reader contention is fixed by `e426557800cd53f25e3c040faeb993c8f9436df4`
(worker `b96d6c30`). Canonical saved authority is resolved before volatile owner
locks; temporary contention still fails closed. The worker's actual 52-case
API/SQLite suite and six red failures/two temporary controls are retained under
`C:/Renulus/scratch/design-c/reader-lock/`.

Chat recovery `7a6b4955` (worker `6058d324`) ties Retry to the failed management
or history operation; it cannot send an unrelated draft. An existing-identity
load failure offers read recovery rather than new-chat creation, retaining
local draft/source changes. Case reads `0db0618c` (worker `372aeec7`) distinguish
capability/teaching load failure from real unsupported/empty data and retry
without clearing edits, previews or pinned teaching selection. Focused red and
green receipts are in `scratch/design-c/contracts/chat-closeout/` and
`scratch/design-c/case-read-recovery/`. Final integrated affected checks pass
33/33 in `C:/Renulus/scratch/design-c/h00/closeout-renderer.xml`; TypeScript,
Vite and Electron source build pass. Worker suites overlap and are not added to
this count. These failure-branch tests use controlled API boundaries; they are
not hidden live-provider success claims.

The actual hidden source-app record is
`C:/Renulus/scratch/dcctl/close/c/s-2d0b0169/out/evidence-manifest.json`, SHA-256
`5029fab15136c97baa757cd9fd75149c966259cb3102429e0bd08c2d5d72a30c`.
It pins 17 captures, compiled files, exact originals, read-only canonical checks
and the controller receipt/log hashes. Captures 0001–0007 use `d10aaa66` product
bytes; 0008–0017 use the final `7a6b4955` build. The only intervening product
changes are the two frontend recovery repairs above. The unchanged readers and
repaired backend are present throughout.

| Hidden check | Evidence |
| --- | --- |
| Home File→saved Chat→permissions→Reader | Actual upload and saved original for each of eight categories; no automatic Send. |
| PDF | Page 1 raster/text, page 2, passage to retained draft/typed Source 1, normal process restart and page-2 reopen; captures 0001–0003. Earlier exact selected-offset R7 proof remains separate. |
| DOCX and tables | DOCX paragraph/reflow table/embedded raster 0005; CSV rows 101–106 and selected-cell passage 0007; XLSX second sheet and uncached-formula warning 0008. |
| Markdown, HTML, XML | Actual rendered Markdown 0009, inert HTML view 0010, escaped XML 0011. DTD/entity refusal with an actual prepared original download remains usable in 0013. |
| Image | Real two-frame TIFF raster on physical frame 2, 0012. Standalone PNG/JPEG checks were not redundantly repeated; prior affected API/original evidence is retained. |
| Narrow, zoom and keyboard | PDF 1000×720/200% focused Workspace 0002; final Case 1000×720/200% with keyboard focus visibly on Attach and retained composer 0015. Prior broader screen checks retain their exact source qualifications. |
| Final Chat/Case | Explicit offline send fails safely; saved context, Rename, actual capabilities/teaching loading and terminal reads, retained draft and one user message survive normal restart; 0014–0017. No assistant/provider success is inferred. |

All substantive captures were visually inspected; 0004, 0006 and 0016 are
indexed transition/loading captures only. There were five normal closes
(including two operator-error closes), no forced or remaining PIDs and
`fault:null`. The idle client was then disconnected. The read-only audit proves
nine attachment/original pairs with exact fixture SHA/size; nine Learn chats
with zero messages/runs; one saved Case with one user message, saved context,
exact retained draft and one send command; zero assessment jobs, attempts or
Memory jobs. PDF and CSV source-linked drafts remain canonical. No credentials,
owner state or live inference were used.

Operator mistakes remain qualified: a paragraph-name wait, upload without a
fresh observed input, and an incorrect XLSX option value. The latter two caused
normal controlled closes; corrected observed controls succeeded. An unavailable
suggestions 409 remains in console logs. This is not a zero-error aggregate or
matching installed/native/accessibility acceptance.

The supported reproducible review surface is the
[app-scoped controller](APP_CONTROL.md). From a clean copy of the final commit
with the existing pinned development dependencies prepared:

```powershell
Set-Location C:/Renulus/dev/repo
git rev-parse HEAD
npm run build --prefix apps/desktop
node tools/renulus-control/client.mjs --repo C:/Renulus/dev/repo --python C:/Renulus/dev/python/Scripts/python.exe --state-root C:/Renulus/scratch/dcctl/review --helper-assets C:/Renulus/dev/helper-assets --fixture-root C:/Renulus/scratch/dcfix/closeout
```

Send one JSON request per line: `{"name":"renulus_start","arguments":{}}`,
then `renulus_snapshot` and `renulus_screenshot` to review the real app. The
controller prints a fresh isolated profile and output path; inspect those PNGs.
Use the observed controls and freshly observed upload input, never another
profile or raw account path. `renulus_restart` reopens this owned profile only;
`renulus_close` provides a normal-close receipt before ending the client.
Omit `--fixture-root` for a fresh empty review without uploads. No credential
setup or live provider is needed for the local UI/original/assessment review.

Verify that the checkout is the final handoff commit on the named branch, with
product bytes equal to `7a6b4955`; do not reset another person's work to obtain
it. `git diff 7a6b4955 -- runtime apps/desktop/src apps/desktop/electron` is empty
at handoff. Normalization-only pre-existing flags are preserved and are not a
product difference. The build is from source with the already prepared pinned
development dependencies; this is not a doctor-facing installation procedure.

The fixture root holds only the eleven declared synthetic originals from the
committed `design-c-reader-fixtures.py` set. Its
`.renulus-control-fixtures.json` declares their size/hash for bounded upload;
the retained source manifest is in Core07's `reader-originals/manifest.json`.
The controller verifies public helper hashes and never copies the owner's state.
This launches the source baseline in hidden review mode, not the older packaged
candidate and not the normal shortcut. To reproduce a populated local review,
use Home Attach with the declared fixtures, confirm their synthetic permissions,
open the file and follow the row/page/sheet controls described above. Rename and
save a Case context, then restart through the same controller. The source app
can also create a reviewed saved test and start Study/Test without inference;
synthetic successful generation is proven by the reusable actual-App test, not
by inventing a hidden provider response.

The continuity automation is ended at this committed closeout. Future work
starts from the H tickets under separate migration authorization. H05, H06/H18,
H24 and H03 remain material open limitations; this document does not downgrade
them because current UI and single-store evidence pass.
