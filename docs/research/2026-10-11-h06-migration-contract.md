# H06 saved migration and deletion contract preparation

2026-10-11. **Proposal and bounded capability evidence; H06 acceptance remains open.**
The conversations lane is pinned at `e2c3e5889e63ef4dfcec3c2f49b9d4b4892e6e10`.
The inspected ConversationRepository, conversation API, backup and Learn 003
migration have no diff against parent `7646fb5a`; the parent's dirty context
composition is outside this note. H02/H05 closure and the parent's source lease
precede implementation. No bridge, host, IPC, shared hook, relation or schema
changes accompany this preparation. Temporary migration remains H21.

Required project/ownership documents, foundation handoff, H06, S2/S3 and the
existing W3-01/W4-03 research were read. Investigation used the retained public
source and synthetic local stores; no live requests or descendant agents. The
research skill's primary-source/document workflow was followed directly under
the user's no-descendants instruction.

## Authority and source pins

The selected SDK is the source-built cohort at
`4b6fea2875e4f2e3e8a8fee181803e54f7056845`, package label 2.0.26, Effect 4.0.1
and Node 26.4.0. The published SDK sharing that version string is a different
graph. See [cohort provenance](../../upstream/opencode/UPSTREAM.md#L1) and
[foundation handoff](../implementation/OPENCODE_FOUNDATIONS_HANDOFF.md#L41).
Local source: `C:/Renulus/scratch/ocf/src`; built cohort:
`C:/Renulus/scratch/ocf/cohort`.

| Source | Exact relevant behavior |
| --- | --- |
| [H06](../planning/opencode-v2/tickets/06-continue-saved-and-temporary-chats-through-one-owner.md#L21), lines 21–26 | Stable migration, one writer, retained citations, unknown lineage exclusion, receipt retirement and terminal replay; H02/H05 dependencies |
| [S2](../planning/opencode-v2/specs/02-memory-context.md#L34), implementation decisions | Native transcript authority; unknown lineage is not an empty valid closure; ownership and truth support differ |
| [S3](../planning/opencode-v2/specs/03-workflows-migration.md#L43), lines 43–46, 54–59 | Cross-store reconciliation, frozen legacy writer, manifest validation, receipt erasure and current deletion frontier |
| [Design C](../planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L140), lines 140–173 | Preserve identities, drafts, Archive and original references; disclosed retained-learning deletion rule |
| [SDK Effect API](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/effect/opencode.ts#L20), lines 20–27, 54–59 | Public `sessions` includes client import/export/remove plus direct create/get |
| [Typed client API](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/client/src/effect/api/api.ts#L214), lines 214–234 | Import accepts decoded `info`, `messages`, optional `location`; export accepts `sessionID`, optional `sanitize`; remove accepts `sessionID` |
| [Protocol](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/protocol/src/groups/session.ts#L244), lines 244–274; [handler](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/server/src/handlers/session.ts#L146), lines 146–164, 210–213 | Import is experimental, conflict is explicit, destination location must be supplied, missing removal maps to a typed unavailable response |
| [Native transfer](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/transfer.ts#L64), lines 64–151, 165–170 | Existing session ID rejects import; only settled messages survive; IDs/metadata/order persist; destination project/slug/version/updated time are recomputed |
| [Message schema](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/schema/src/session-message.ts#L23), lines 23–37, 211–237 | Native IDs require `msg_`; arbitrary message metadata is retained; assistant structure requires agent/model and completed time for transfer retention |
| [Native removal](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session.ts#L367), lines 367–377 | Get, interrupt, await idle, close transport, remove children, clear environment, delete projection/event aggregate |

## Supported native contract

Use public `@opencode/sdk/effect` inside the managed embedding scope:

    sdk.sessions.import({ info, messages, location })
    sdk.sessions.get({ sessionID })
    sdk.sessions.export({ sessionID, sanitize: false })
    sdk.sessions.remove({ sessionID })

Import is a complete projected transfer, not an append API or a prompt. It
neither enqueues user inputs nor performs generation in the inspected transfer
path. The proof below tests actual import, automatic host startup/reopen and
removal with an inference adapter that refuses and counts every call. There is
no projector, inbox or SQLite write imitation in the fixture.

Supply the verified destination workspace explicitly: the server otherwise
defaults to its current working directory. Import preserves message text, IDs,
metadata and array order, but not every session field verbatim: destination
project/location, slug, app version and updated time are derived. Therefore
compare a declared retained projection, not whole Session.Info equality.
Import is not idempotent: an existing target ID yields ConflictError; it must
never be treated as proof that the same source payload was imported. These
claims follow the protocol/transfer sources above.

## Proposed saved-only migration

The existing ConversationRepository remains the canonical entry point. Parent
reserves the hook and schema; the following are logical requirements, not a
second migration service or an implemented API.

1. **Freeze and snapshot.** Under the canonical logical writer/admission barrier,
   verify saved retention, owner revision, policy/context/draft/project pins,
   deletion frontier and active paired manifest. Set the pending native owner
   before any native write; the existing Learn pending-mapping guard is reusable.
   Settle already admitted legacy work before snapshotting; a timeout leaves
   migration pending and blocks both writers. Preserve draft, Archive, membership
   and the logical conversation/run/message IDs. Skip temporary buffers.
2. **Stage exact retained rows.** Read all retained user/assistant rows and full
   citation records through a checked owner snapshot. `LearnService.get_thread()`
   retains raw citations; ConversationRepository.messages exposes only
   `content_ref` entries and cannot alone supply full citation provenance. Freeze
   permits a stable paginated snapshot. Record a versioned source digest over
   exact text, role, original ID/run/timestamp and citation JSON. Legacy orphaned
   running receipts remain interrupted; do not queue or resume their inputs.
3. **Import once into a non-admitted stage.** Reserve a stable target session ID
   and native message-ID mapping from profile/store/logical owner identities.
   Legacy IDs that fail `msg_` validation require deterministic native aliases;
   preserve original IDs in metadata and the public read adapter. Native message
   metadata carries original timestamps/citations and `lineage=unknown`. Only
   structurally settled historical assistant rows qualify for import. Do not
   fabricate a new accepted finish, tool result, provider response, cost, lineage
   or publication receipt. The required legacy agent/model labels describe
   provenance and grant no route/tool authority. Retain pending/partial material
   through the legacy read adapter or refuse conversion, rather than accepting
   the SDK's silent settled-message filtering as lossless migration.
4. **Read back, map and activate.** Read the exact reserved session and its full
   exported message projection outside canonical transactions/physical locks.
   Verify profile/store/migration identity, source digest, every mapped ID, role,
   byte-exact text, citation record and order; reject missing/extra rows. Recheck
   the original owner/policy/context/draft/project/deletion pins and manifest
   inside the final transaction before publishing one SavedConversationMapping.
   Pending or mismatched stages remain non-admitted. Never allocate a different
   session after an uncertain acknowledgement.
5. **One writer, two read paths.** OpenCode writes all new turns; old SQL history
   remains explicitly read-only. The public history adapter must include imported
   rows without manufacturing H02 CompletedAnswer publications. Context selection
   excludes every unknown legacy user/assistant range, its tool data and derived
   summaries. Automatic memory capture remains off/ineligible for that lineage.
   H05 may later validate a specific receipt; absence of lineage is never an
   empty eligible closure.

The whole-session import payload may exceed the existing 1 MiB IPC frame. Do not
truncate or split one import into prompts. Proposed bounded ingress: an owned
profile staging artifact selected by a logical stage ID, expected byte count
and digest, with bounded authenticated chunk writes and a final integrity check.
The host consumes that completed stage through the same public SDK import. No
renderer/model-supplied arbitrary filesystem path. Parent must approve the exact
host/IPC contract and retention cleanup; a direct below-limit import can be the
first bounded implementation. SDK export is also whole-session data, so large
readback needs bounded local processing or the existing message-page traversal.

Minimum proposed host commands, for the parent's shared lease: authenticated
`session.import` with a canonical migration/stage identity and expected source
digest, and `session.remove` with the canonical purge identity and session ID.
The operation frame already supplies profile/store/attempt identity; those are
not trusted renderer/model arguments. Import admission validates the active
paired stores and canonical frozen-owner permit without activating model
dispatch or requiring a configured generative route. Both commands execute the
SDK operations above; observation continues through existing get/messages/find.
Large-stage transport and exact field names remain a parent contract decision.

After host loss, reopen under the same admission barrier and consult the
canonical migration receipt. Observe the reserved native session; exact match
permits the original map/activation, absence permits only the same deterministic
import after fresh admission, mismatch stays blocked. Transport/internal errors
are not absence. Replay never dispatches generation. A failed migration does not
automatically restore the legacy writer while a native stage may exist. Before
new native writes, explicit abort can purge the checked stage then release the
freeze; after new writes rollback requires a compatible read/export path.

## Canonical deletion and receipt retirement proposal

H06 line 24 requires: “Delete owners and retire payload-bearing command receipts
transactionally, including creation receipts targeting new through their result
owner; new exports exclude deleted payloads/digests.” Line 25 requires terminal
unavailable replay through opaque tombstones. S3 line 59 extends deduplication
across old backups and disallows active recovery without a trustworthy frontier.

**One owner transaction:** close admission and revoke publication, validate the
expected owner revision, capture native profile/store/session IDs into an
owner-independent purge obligation, retire all owned live command receipts,
delete owned records/links and advance the canonical tombstone/context frontier.
Resolve historical `create` receipts targeting `new` via result.identity before
scrubbing; future live receipts should store a normalized owner reference. Apply
the same retirement hook to ConversationRepository.delete and direct
LearnService.delete_thread, and to owner cascades. Preserve independently owned
Library originals and the existing disclosed retained-memory rule; explicit
delete-related-learning is separate truth-support revocation. Parent owns these
shared insertions and migrations.

**Retired replay record:** retain only opaque operation ID, operation kind, typed
owner identity, terminal-unavailable state and deletion epoch/time. Remove
request/payload digest, title/draft/answer/result bytes and citation payloads.
Consult this tombstone before any payload-digest comparison or effect, returning
terminal unavailable for that key even when the submitted payload differs. This
prevents erased digests from becoming an excuse to repeat work. Current command
policy still applies; neutral run/deletion status remains separately usable.
The current non-null live-ledger columns need a parent-owned schema/replay
change; a placeholder hash is not the proposed contract.

**Native purge outside the transaction:** use supported sessions.remove only
after binding its existing session to the purge obligation. Its actual idle
settlement must complete before marking purge complete; cancellation acceptance
alone is insufficient. On lost acknowledgement, sessions.get reporting the
specific missing-session outcome reconciles success. An existing exact session
permits retry of the deterministic remove under the same purge identity; all
other faults propagate or remain pending. Cascaded mappings cannot be the only
place holding these coordinates. Do not claim synchronous physical SQLite/WAL,
backup or derived-index erasure from native projection absence. H18 supplies
the complete paired-store/current-frontier restore proof.

## Concrete current gaps

| Requirement and source | Current gap and reproducible evidence |
| --- | --- |
| H06:21 stable zero-generation import; [bridge](../../runtime/renulus/learn/harness_bridge.py#L82), lines 82–88, 636–668 | Bridge preparation rejects any learn_messages row; mapped history projects only H02 answer receipts. Supported SDK import alone cannot activate or display migrated rows. Shared lease needed for legacy read ranges and migration admission. |
| H06:23 exact citations; [conversation messages](../../runtime/renulus/learn/conversation_repository.py#L217), lines 217–234; [Learn reader](../../runtime/renulus/learn/service.py#L49), lines 49–59 | Public conversation items discard raw citation entries lacking content_ref. The capability fixture preserves such a passage/page citation using the full legacy reader; the migration snapshot must retain both forms. |
| H06:24–25 receipt retirement; [command](../../runtime/renulus/learn/conversation_repository.py#L29), lines 29–48, create:135–136, delete:337–378; [backup](../../runtime/renulus/storage/backup.py#L21), lines 21–23, 61–99 | Public probe deletes/tombstones the owner, but old draft/title/request hashes remain in a new export; replaying create returns HTTP 201 and the deleted owner identity. Source command returns stored result_json, while delete does not retire earlier receipts. |
| H06:24 single-owner deletion; [Learn 003](../../runtime/renulus/learn/migrations/003-harness-bridge.sql#L3), lines 3–11; same delete paths; [native remove source](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session.ts#L367) | Both canonical deletion paths cascade mappings/answer references without a native purge obligation. Native coordinates must be staged before the owner disappears. Native SDK removal is available, but no shared integration or fault/race acceptance is claimed here. |

These are bounded H06 preparations. The parent context, H03 routing, H05 lineage
composition and complete recovery/release integrations remain their known open
work, not additional defects raised by this note.

## Executed evidence and next implementation gate

[Dedicated test](../../tests/learn/test_harness_migration_contract.py) and
[native fixture](../../packages/harness/test/fixtures/h06-import.mjs) use a fresh
synthetic transplantation conversation and raw passage/page citation. The fixture
uses a temporary empty native template only to obtain valid Session.Info fields;
it removes that template before importing a deterministic target. Historical
assistant completion timestamps are structural fixture data, not verification of
real legacy completion or new publication.

Import acknowledgement is discarded, the native process closes, another opens
the same store and recovers with get/export only. Exact text, roles, stable
native aliases, original IDs and citations survive. A third process removes the
imported session and get returns Session.NotFoundError. All three processes
report **zero inference calls**; legacy public reads remain unchanged and no
canonical native mapping is activated. **1 passed in 16.86s**, no skips.

Final isolated-environment rerun: **1 passed in 20.31s**, no skips. The child
environment contains only selected Windows system paths and synthetic roots;
provider credentials and private profile environment are not copied.

Exact verification from the conversations checkout:

    $env:RENULUS_HARNESS_NODE='C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe'
    & 'C:/Renulus/dev/python/Scripts/python.exe' -m pytest tests/learn/test_harness_migration_contract.py -q --basetemp C:/Renulus/scratch/oc-h02-h08/conversations/h06-native-isolated-state --junitxml C:/Renulus/scratch/oc-h02-h08/conversations/h06-native-isolated.xml

The public deletion probe called create, two draft writes, delete, get, records
export and creation replay through HTTP, without invoking a generation route.
Reproduction script: `C:/Renulus/scratch/oc-h02-h08/conversations/h06-receipt-probe.py`;
receipt: `C:/Renulus/scratch/oc-h02-h08/conversations/h06-receipt-probe.json`.
It reports owner_missing/tombstoned=true, marker/title_in_new_export=true,
payload_hash_retained=true, create_target_new='new', create_replay_status=201,
create_replay_deleted_owner=true and four retained receipts. Run with managed
Python `-B` and a fresh synthetic probe root. No physical erasure is inferred.

After H05 and parent context composition close, reserve the exact owner hook,
migration/purge/retirement schema and host/IPC source leases. First implementation
gate: one public saved migration with zero model calls, exact readback, immutable
legacy reads and one stable active mapping. Then fault-inject before/after import
and map, race draft/project/Test/delete with activation, and prove retired replay
plus native purge interruption. Populated migration, Archive/draft preservation,
shared-original retention, rollback and old-backup tombstone overlay remain
required acceptance beyond this capability test.
