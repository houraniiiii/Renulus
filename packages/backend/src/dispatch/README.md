# BF01 bounded target dispatch

This is the TS target on synthetic profiles. Python remains the production
canonical writer and dispatch authority until BF08. No production transport,
provider login, live account qualification, plugin lifecycle or domain migration
is installed by this module.

## Canonical worker integration

The parent has integrated these exports into the existing storage seam:

```ts
import type { DispatchCommand, DispatchResults } from '../dispatch/contracts.ts';
import { executeDispatch, isDispatchCommand } from './dispatch.ts';

// Existing union and result map:
type StorageCommand = DispatchCommand | ExistingStorageCommand;
interface CommandResults extends DispatchResults { /* existing result entries */ }

// Sender recognition; strict nested validation also runs in the worker transaction:
if (isDispatchCommand(value)) return;

// Canonical worker, after mode and owner checks:
if (isDispatchCommand(command))
  return transaction(true, () => executeDispatch(db, command));
```

The closed cases are `dispatch.snapshot`, `dispatch.stage`, `dispatch.inspect`,
`dispatch.close`, `dispatch.activate`, `dispatch.open`, `dispatch.begin`,
`dispatch.child`, `dispatch.run`, `dispatch.current`, `dispatch.reserve`,
`dispatch.admit`, `dispatch.permit`, `dispatch.complete`, `dispatch.revoke`,
`dispatch.settle`, `dispatch.reconcile`. Their exact payloads and tagged result
map are in `contracts.ts`. The new module opens no connection or transaction.
Every call is synchronous local work inside the canonical worker's existing
`BEGIN IMMEDIATE`/commit/rollback boundary. No schema or migration is added.

The existing `route_json` retains its original route properties. A namespaced
`dispatch_target` property holds the pinned host fence, optional batch size and
bounded per-permit proof metadata. It contains hashes/counter/qualification
metadata and credential references, never request bodies, manifests or secrets.
Legacy runs without this host binding fail closed in the target.

## Host responsibilities

`createNativeDispatchCallbacks` exposes a typed handler for `model.prepare`,
`model.manifest`, `model.dispatch`. Connect it through the parent's
`createNativeDomainAdapter`, using the actual `DomainClient` encode/receive,
cancel and settlement pump. The harness class check and native serializers
are unchanged. The handler returns only the terminal outcome/result/error;
the existing adapter supplies authenticated protocol/binding/callback fields.

The trusted host must supply:

- Exact authenticated run/binding resolution and current profile/store/process,
  input, assessment, context, deletion and cancellation checks. `dispatch.current`
  compares the persisted fence, current grants/ancestry, active Test and the
  existing canonical context preference; it does not manufacture missing
  domain-specific epochs. Parent publication must compose those predicates and
  `dispatch.current` with the canonical domain mutation in the same transaction.
- Exact closed-candidate inspection and actual host/worker settlement receipts
  before activation/reconciliation. Loaded input hashes and registry hashes
  must come from observation, never requested plugin metadata or stopped run pins.
- An immutable route-specific qualification with verified entitlement/window
  evidence and a counter implementation/version covering actual native framing,
  system/history/tool schemas/results/images. The callback rechecks evidence
  identity and revisions after counting. No generic tokenizer or character
  estimate is supplied as account evidence.
- An explicitly injected `fixtureOnly: true` transport for this BF01 target.
  A protected production broker and its opaque one-use permit remain parent/F0
  work. There is no fetch/default transport, credential resolution or retry.

The native adapter currently requests primary/child/explicit tool continuations.
All spec purposes and auxiliary/scheduled/repair admission kinds are represented
by the transaction API for later domain integration. Summary repair shares the
compaction pool. Opaque recovery resends, transport fallback and native retries
are explicitly refused. Recovery observes/reconciles existing permits instead.

## Bounds and receipts

Defaults enable the 13 required roles with positive bounded budgets; optional
title stays off/zero. There are two profile remote slots, one child per parent,
depth one and eight interactive family dispatches. Generation/import/fictional
roles require an explicit batch size: 5/10/20 receive 6/12/24 family dispatches
within a 32-dispatch role ceiling. These are provisional engineering budgets,
not account/model capability claims.

Reservation and final admission are separate commands/transactions. Final
admission sets `dispatched` with the current grant epoch and returns the one-use
`dispatch_allowed=true`; observation/replay always returns false. The serialized
wire hash, body hash/length, manifest hash, token count/output and qualification
are bound to the permit. Revocation narrows current authority and fences late
publication; already admitted remote effects stay charged. Known failure,
confirmed result, pre-send cancellation and uncertain effect retain their ledger
rows. Uncertain effects hold remote capacity until an explicit known receipt
reconciles them. Neither timeout nor restart issues another attempt. Token/cost
usage quantities are not added to the existing ledger schema.

## Verification

Use the prepared Node 26.4.0 artifact:

```powershell
& 'C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe' --test --test-concurrency=1 test/dispatch.test.mjs test/dispatch-worker.test.mjs
```

`dispatch.test.mjs` uses actual Node SQLite files and the existing Python
migration SQL. It exercises configuration proof, every required purpose,
generation budgets, route selection, reservation/admission/revocation,
uncertainty/reopen, children/root budget, qualification/Test/fence refusals and
summary repair. It also runs both selected subscription native serializers with
a complete Library tool pair, an explicitly synthetic counter and a counting
SSE transport fixture.

`dispatch-worker.test.mjs` prepares the complete schema via Python `create_app`,
then uses the real integration-owned `StorageClient`/canonical worker and owner
selector. It verifies stage/inspect/select/open, run/reserve/admit, queued revoke,
uncertain debit, close/reopen, duplicate refusal and late publication fencing.
Protected dispatch tables remain absent from public learning exports/pages.

These are synthetic contracts/native serialization proofs. They do not establish
live account counters/entitlements, plugin restart acceptance, complete domain
journeys or BF08 production ownership/package cutover.
