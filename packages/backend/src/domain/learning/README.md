# Bounded BF02 saved-learning target

This is an isolated TS-owned target slice prepared against BF01. It does not
change Python production ownership, complete BF02, establish BF01 dependency
acceptance, or authorize the BF08 profile cutover.

## Parent integration

The parent owns shared storage contracts, the canonical writer worker, native
host changes, facade routes, build manifests and BF01 activation/dispatch.
No changes to those files are made by this lane.
The parent has now registered the union/results, sender validation and synchronous
worker dispatch below. Keep these signatures stable for HTTP/Library wiring.

In `storage/contracts.ts`:

```ts
import type { LearningCommand, LearningResults } from '../domain/learning/contracts.ts';
import { isLearningCommand, validateLearningCommand } from './learning.ts';
// Add LearningCommand to StorageCommand and LearningResults to CommandResults.
// Before the shared validation switch:
if (isLearningCommand(value)) { validateLearningCommand(value); return; }
```

In `storage/worker.ts`, import `executeLearning` and `isLearningCommand`, then
dispatch before the shared switch, after ownership/selector checks:

```ts
if (isLearningCommand(command)) {
  return transaction(true, () => executeLearning(db!, command));
}
```

All learning commands are synchronous and require an already-open local
transaction. The write transaction for reads is deliberately conservative and
can be narrowed by the integrator. They do not open canonical connections,
migrate schemas, invoke engines or wait for native work. `learning.rename`
continues using the parent's existing command/function.

The added cases are exported as `LearningCommand`/`LearningResults`:

- `learning.begin`, `current`, `map`, `bind`, `consume`, `consumeMemory`, `context`, `publish`, `stop`.
- `learning.lifecycle`, `project`, `delete`.
- `learning.view`, `read.check`, `scan`.
- `learning.library.plan`, `library.resolve`.
- `learning.purge.enqueue`, `purge.list`, `purge.ack`.

`openSavedLearningTarget({storage,harness,model,library,modelCallbacks,onBegin})` composes
the parent's real in-process `DomainClient` adapter and existing
`openLearningHarness`. `harness.processGeneration` is required for native
transfer/removal. The parent supplies paired-store preparation/activation and
the BF01 selected immutable configuration; use `target.native.activateStores()`
and BF01 activation/inspection in that order. The public target exposes
`send`, `cancel`, `change`, `delete`, `range`, `messages`, `find`, `reconcilePurges`, `status`
and `close`. `native` is a trusted embedding surface, never a renderer API.

The model factory receives the real `DomainClient`. Production assembly must
return its app-owned gateway preserving the exact subscription route.
`modelCallbacks(request)` can call BF01's existing
`createNativeDispatchCallbacks().handle(request.binding, request.command,
request.payload, {signal:request.signal})`. BF01 `resolve/checkCurrent` must
use this slice's `learning.current` and exact authenticated binding in addition
to its own dispatch fences. An absent model callback fails closed; this slice
installs no production transport, paid API or fallback. Only tests use native
TestLLM. Opening/reopening/range/Finder never submit native input.

### Saved text send intent and observation

`SavedSend.intent?: SavedSendIntent` is the exact fully defaulted text
`Send.model_dump(mode='json')` object:

```ts
{ expected_revision, text, request_id, teaching_style: 'direct',
  topic_id: null, model: null, freshness: null, content_refs: [] }
```

The trusted sender and writer validate matching outer `expectedRevision`,
`text` and `idempotencyKey`. Omitted intent uses the same Python defaults for
older synthetic callers. The hash contains the original Python operation,
target type/ID and these eight exact request fields. `expectedDraftRevision`
is an additional host-only concurrency fence, excluded from that hash.
Replay retains the original receipt without repinning or native submission,
including when the current host draft revision differs.

Media fields and nonempty content references refuse explicitly before any
draft or receipt mutation. Nonempty saved draft references also refuse without
discarding the pins. There is no implicit image/ref fallback in this slice.

`onBegin(run, request)` runs once for a fresh canonical receipt, before native
session creation/submission. BF01 uses it to admit/pin the exact manual model
and freshness intent. An explicit model or `freshness:true` with no such
callback refuses before admission. Callback failure settles the saved receipt
as interrupted and preserves submitted draft text; it never starts inference.
The request is detached from caller mutation and frozen, and the pending
checkpoint retains its metadata plus the text digest, without another saved
message body. The writer/native model boundary verifies those pins again.

`modelCallbacks(nativeRequest, {run,request})` receives the exact trusted intent
and current canonical binding; one-argument implementations remain compatible.
The native final-primary preparation seam adds the pinned direct/guided teaching
instruction before invoking BF01's underlying preparation/digest. This uses the
existing native runner and does not introduce a second model loop.

`send(input, {accepted,signal})` calls `accepted(receipt)` after canonical
admission and before native work, including receipt replay. The callback sees
a detached copy. Sync throws and async observer rejections are isolated from
the owned job. HTTP renderer disconnect detaches observation; the HTTP owner
must reserve `signal` for explicit cancellation. Native events have no reliable
public subscription seam in the current host, so parent streaming can initially
use canonical started/final events without polling or another execution loop.

`messages(threadId,{limit,cursor})` projects the owning-host bounded raw range
to the existing public `{conversation,items,next_cursor}` shape. Each item is
`{id,run_id,role,content,created_at,content_refs}`. The canonical answer reference
assigns each native input/assistant ID to its exact run, rather than trusting
message metadata. Timestamps come from native messages; completed text-only
items have empty content refs. It rechecks the canonical view after projection.
`range()` retains raw native tool parts for existing tooling/tests. Required
input/reference/image flows and imported legacy message parity remain separate.

`LibraryQueryBridge.query` is the narrow app-owned worker seam. It receives
canonical eligible revision IDs, query, bounded count, operation/attempt and
abort signal. Return ranked `{passage_id,revision_id}` values only, after actual
engine settlement. Wire it to the selected worker client's `library.query`
and read its bounded result artifact using the owning worker adapter. The
bridge is injected in this lane's tests; engine/query extraction is a separate
owner's work. Native tools and the real callback protocol are exercised.

`createLearningHistory(storage,native)` uses only the owning host's bounded
`observe` pages. It does exact case-sensitive literal substring matching in
committed native message references and returns exact message IDs/offsets.
Finder scans one native page per call; callers follow `next_cursor`, including
empty result pages. Cursors bind query, filters, policy/context epoch and the
current conversation's canonical stamp. Range and Finder recheck canonical
scope after every native read. Cursors are observation coordinates, never
authority. Reserved/interrupted/temporary messages are omitted.

### Consumed learner memory

The composition's native Memory tool bridge records returned recall pins with
`{type:'learning.consumeMemory',binding,dependencies:MemoryDependency[]}` and
receives `{recorded:true}`. This command accepts only exact `memory_revision`
pins in the form `{target:{type:'memory_revision',id:factId+':'+revision},
expected_revision:String(revision)}`. It checks live canonical support/project
scope with `checkMemoryDependency(db,dep,projectId)` under the existing writer
transaction, then deduplicates the pins into `checkpoint.memory`.

Current-run checks and publication recheck those dependencies. Answer-reference
closure preserves them exactly, including inherited eligible answer pins.
History eligibility delegates memory revisions to that same memory owner,
including support and cycle checks. An answer with revoked/corrected memory
ancestry is omitted from new native context; already consumed stale pins refuse
publication. No recalled fact text is copied into canonical answer storage by
this command. The native Memory tool/plugin and bridge wiring remain their
existing owners' code.

## Persistence and race behavior

Existing `learn_runs`, `conversation_commands`, `learn_harness_mappings`,
`learn_harness_answers`, evidence, lineage and purge tables are reused.
Pending checkpoints retain hashes, exact consumed source coordinates and local
fences. Completed references preserve the existing `harness/1` mapping and
answer-reference shapes. Canonical tables contain no new message bodies.
The canonical composer draft retains the submitted text on interruption and
clears/increments its draft revision on successful publication. The saved-text
slice refuses nonempty draft references until their owning input/pin adapter
is connected, preserving those references instead of silently dropping them.
Legacy `learn_messages` remain immutable; unmapped legacy conversations refuse
new sends until the existing migration owner imports/maps them.

Receipt replay never creates/submits another native input. Cancellation is
committed before waiting for native settlement. Delete atomically tombstones
receipts and the owner, cancels pending capture jobs and retains a durable
native purge intent; removal/ACK are outside that transaction. Failed cleanup
keeps debt for `reconcilePurges()`, including after reopen. A late native session
created after deletion is independently journaled and removed. Normal close
seals callbacks only after owned native work has settled.

Archive and project membership changes bump canonical context and revision.
`learning.project` accepts `expectedProjectRevision:null` from the public
Python-compatible ProjectMove request and resolves the current active project
within that same writer transaction. A supplied positive trusted revision
still compares exactly; subsequent run admission pins the resolved revision.
They immediately change Finder filters and prevent stale run publication.
After-read changes to Archive/project/policy/delete reject the entire read.
Current canonical active revision, deletion, source scope, rights and excluded
pages are checked around Library engine work, on citation, context reuse and
publication. Tool arguments and echoed envelopes grant no authority.

## Explicit remaining integration

- BF01 acceptance, qualified exact counters and real protected broker transport
  remain parent work. Synthetic model success does not establish live route
  acceptance.
- This slice is saved text only. BF04 owns images, temporary/Save, full long
  context and volatile-family lifecycle.
- Learning and Memory use the Library owner's `effectiveKnowledgeMetadata`
  projection, preserving identical source-dependency fingerprint fields.
  Publication identity/version/scope controls which status events apply;
  unrelated events do not blanket-disable a source. Retraction and unavailable
  metadata still refuse use. Native citation returns the existing Library
  viewer/original route shape; all reader/attachment parity remains separate.
- Existing attachment-bearing chat deletion refuses until canonical attachment
  cleanup is connected. Evidence deletion revokes answer lineage, suppression
  and capture jobs. The parent writer now owns `reconcileMemorySupport(db)`
  in the same transaction after learning deletion, and its composition must
  await `MemoryHost.flushPurges()` before successful deletion acknowledgement.
  This slice opens no second memory writer or engine. Full memory capture/recall/correction/engine
  cleanup and complete cross-domain deletion remain BF02 integration work.
  Receipt/evidence/source ancestry is retained without a replacement Mem0 engine.
- Bounded initial limits are 100 completed references per conversation,
  1,000 Library revisions per plan, 24 native pages/8 MiB per completion and
  one 100-message native page per Finder call. Capacity errors do not trigger
  inference or blind resubmission.
- Focused local tests retain a single-owner synchronous transaction adapter for
  rollback/race assertions. A separate connected test now uses the actual
  `openIsolatedStorage`/`StorageClient` worker, Python-prepared schema-2 inventory,
  selector/owner checks, real native retrieve/cite callbacks, receipt, close/reopen,
  native Finder, Archive and physical native deletion. This is synthetic target
  evidence; parent BF01 dependency acceptance and HTTP/engine integration remain.

Run with prepared Node 26.4.0:

```powershell
& C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe --test --test-concurrency=1 packages/backend/test/learning-target.test.mjs
```

Tests prepare synthetic schema-2 profiles with the real Python `create_app`,
then hold the TS synthetic selector/owner lease. They use native TestLLM/tool
lifecycle only, never owner profiles, accounts or live providers.
The original six native tests are retained. Focused additions compare actual
Python `ConversationStreams.begin` receipts, defaulted/custom Send hashes and
replay; reject changed style/model/topic/freshness and mismatched/media/ref
inputs without draft loss; exercise throwing/detached admission observers,
trusted model/style authority, canonical UI projection and transaction-local
project revision resolution. An integrated writer/native test pins consumed
memory, refuses stale/project-forged pins, verifies publication and inherited
ancestry, and omits revoked ancestry after canonical correction. These tests
do not establish full BF02 completion.

## Saved Learning metadata preparation

`metadata-contracts.ts` exports `LearningMetadataCommand` and
`LearningMetadataResults`. `storage/conversation-metadata.ts` exports the
guard, command/result validators and synchronous `executeLearningMetadata(db,
command)`. The parent canonical writer registers its guard **before** the
broader `isLearningCommand` prefix guard. These functions require the caller's
existing transaction and open no connection of their own.

The seven commands are `learning.create`, `learning.get`, `learning.list`,
`learning.draft.get`, `learning.draft.save`, `learning.runs.list` and
`learning.run.status`. Create takes a fully defaulted, exact Python
`NewConversation` Learning request; draft save takes the exact
`{expected_revision,text,content_refs}` shape. Commands use Python-compatible
request hashes and original receipts for replay. Changing work under the same
key conflicts; replay never increments a revision or starts inference.
Retired command and owner-deletion frontiers prevent old receipts resurfacing
through additive restore.

Draft saves retain every canonical reference and locator. Saving validates
saved version existence, deletion markers, display rights, reserved/source
scope and attachment ownership. Retained historical revisions remain valid
pins; retaining a reference does not grant model-input or currentness authority.
Draft reads/replays preserve old references so an unavailable item is not
silently removed. Generation continues to reject nonempty draft references
until required-file admission is connected. No temporary, Case or image input
producer is introduced. Saving a draft increments both draft and conversation
revisions without bumping context, matching Python. Creating project membership
touches the project and context epoch.

List cursors are process-local signed observation coordinates with a fixed
timestamp boundary and scope checks. All title/draft reads and writes enforce
current Test policy, including replay. Run list/status retain Python's neutral
state visibility during Test; titles and errors are disclosed only when
assistance is allowed. Durable status does not invent partial streamed output.

`test/conversation-metadata.test.mjs` prepares schema 2 with the original Python
app/repositories, compares original receipts, Unicode and locator hashes, stale
replay and draft behavior, and exercises all seven commands through the actual
`StorageClient`, close and reopen. It also checks rollback, retirement/deletion,
scope/pagination and explicit reference-send refusal without draft loss. Run:

```powershell
& C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe --test --test-concurrency=1 packages/backend/test/conversation-metadata.test.mjs
```

This is bounded synthetic preparation against the parent integration. It does
not activate production ownership or establish BF01/BF02/package acceptance.
