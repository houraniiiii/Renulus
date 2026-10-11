# H06 saved migration and deletion contracts

October 11, 2026. H02–H05 have local acceptance at the e467693e checkpoint.
H06 implementation is released, but connected acceptance remains open.
Temporary execution/cross-store Save and full paired restore remain H21/H18.

## Canonical command retirement

Parent-owned additive learn-005-command-retirement.sql creates
learn_command_tombstones(ledger,idempotency_key,retired_at), with the first two
columns forming its primary key. It has no owner FK, payload, result or request
digest. Applied Learn002/003 are unchanged; Learn004 is reserved for migration
and independent native purge coordinates.

Owner deletion retires conversation receipts bound by explicit target owner,
result.identity or result.conversation.identity. This includes create commands
whose target was new. Payload-bearing rows are deleted in the same owner
transaction, and conversation_command deletion markers preserve the opaque
frontier through existing records-only reconciliation. The deletion command's
own receipt is retired before commit. New exports retain no deleted title,
draft, result or request digest.

Retired replay checks the opaque identity before request hashing or owner
lookup and returns command_terminal_unavailable, HTTP410, retryablefalse.
Changing the payload of a retired key cannot recreate a deleted owner.
Ordinary replay for surviving owners keeps its current-policy check.
Native removal is not performed inside this transaction: a separate durable
purge obligation must retain exact store/session identity through FK cascade,
then settle producers and remove/reconcile native absence outside locks.

Receipts under G:/Renulus-agent-scratch/oc-h02-h08/command-retirement/:

| Receipt | Result | Qualification |
| --- | --- | --- |
| red01.xml | 1 setup error | Missing scratch parent; no behavior exercised |
| red02.xml | 1 failure, 7.25s | Public deletion leaves original title/draft in new export |
| green01.xml | 1 pass, 6.49s | Deletion/export/reopen/three retired-command replays |
| restore01.xml | 1 fixture assertion failure, 5.86s | Used removed count for excluded incoming rows; product assertions not yet reached |
| restore02.xml | 1 pass, 5.69s | Public older records restore cannot reintroduce retired payload |
| final01.xml | 7 passes, 28.39s | Two new cases plus affected rollback, temporary deletion and surviving-owner replay |
| retired-conflict01.xml | 1 pass, 6.28s | Final added changed-payload retired replay returns410 before hashing |

These runs overlap. No aggregate count, native deletion, engine, account or
full paired restore acceptance is claimed. The inherited TestClient warning
remains unrelated. Independent Standards review of e467693e..17acab88 reports
zero material findings. Spec review found one P2: changing a retired creation
request to temporary:true bypassed the durable tombstone. The exact public
reopen replay reproduced201 instead of410 in temporary-red01.xml (1 failure,
8.11s). The guard now runs before the temporary branch; temporary-green01.xml
records1 pass,6.93s. Focused independent Spec and Standards reviews close
this repair with zero remaining findings.

## Canonical migration journal and purge metadata

Learn004 now stores frozen migration references and owner-independent native
purge obligations. HarnessMigrationJournal uses the supplied canonical
transaction for reservation, one import claim and exact mapping/readback
activation. A local savepoint rolls back both reservation writes even when the
caller catches a session conflict and commits its surrounding transaction.
Activation validates the complete mapping contract and engine cohort against
the paired manifest. Legacy message bytes are not stored in the journal.

Conversation owner deletion captures profile/store/session and originating
operation/attempt before cascading mappings/answers. Purge rows have no owner
FK, payload, source digest, manifest or transcript references, and survive
canonical export/reopen. Native removal must run after actual owner settlement
outside canonical transactions; metadata alone does not prove removal.

Native-deletion receipt directory:
G:/Renulus-agent-scratch/oc-h02-h08/native-deletion/receipts/.
journal-red04.xml records two meaningful failures (partial reservation and wrong
engine cohort),8.29s. journal-green04.xml records four passes,16.46s, covering
rollback/activation/reopen, durable purge coordinates and both repairs.
The actual production-main deletion tracer red01.xml still fails: canonical
deletion succeeds but session.find retains the native transcript (1fail,16.97s).
The native purge and connected migration/continuation paths remain open.

## Native logical transfer port

Sartre owns the new native session-transfer module; Ohm owns the canonical
migration state machine. Trusted TransferFrame carries profileId/storeId/
generation/operationId/attemptId separately from model payloads. Commands:

| Command | Payload | Result |
| --- | --- | --- |
| session.import.stage | sessionId,bundleDigest,partIndex,partCount,totalBytes,chunk | staged identity/counts/complete |
| session.import | sessionId,bundleDigest | verified identity/messageCount |
| session.import.inspect | sessionId,bundleDigest | absent or exact verified identity/messageCount |
| session.remove | sessionId | removed identity |
| operation.retire | empty object | pending or retired |

The staged UTF8 document is renulus.saved-session/1 with conversationId,title
and ordered messages(id,role,content,runId,createdAt,completedAt,citations).
Only settled historical user/assistant text is transferred; legacy partial
history must retain its original public rows/outcome and cannot acquire
eligible M5 lineage by receiving an imported storage timestamp.

Session aliases hash compact Unicode JSON arrays containing
renulus-h06-session-v1/profile/store/conversation. Message aliases hash
renulus-h06-message-v1/session/legacyID. Exact original identity/citations
stay in metadata with unknown lineage. Whole-document digest uses exact
ordered UTF8 chunks, not reserialized JSON.

Approved bounds are8MiB/4096messages/256parts,48KiB serialized stage payload,
four staged operations/16MiB aggregate bytes/256 retained operation records.
Capacity refuses admission; it cannot evict active owners or tombstones.
No payload carries filesystem paths. SDK import/get/export/remove are the
supported persistence ports; native database mutation is prohibited.

Repeated commit joins actual retained ownership. A lost import acknowledgement
is reconciled by exact readback. Reopen restages immutable data and inspects
before any potential import. Only the typed missing-session result proves
absence. Empty SDK templates are tracked and cleaned through actual settlement.
Retirement erases staged text/caches only after settlement and keeps opaque
terminal identity without deleted payload digests.
