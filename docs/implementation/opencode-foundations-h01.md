# H01 managed OpenCode host evidence

2026-10-10. Implementation from the completed Design C handoff
`c2bd896420fb88f76d63ca576414dbbba182f4c2`, in `codex/opencode-foundations`.
The current owner request authorizes this foundation implementation and UI
checks. H00 is already present in that baseline. H01 and the independent H24
settlement repair are this batch; H02 is the next connected product slice.

## What changed

- `packages/harness/src/host.ts` embeds the **real** source-built SDK loop and
  durable store behind a small saved-profile facade. Python remains the domain
  owner; no second execution scheduler or transcript database was introduced.
- The prepared paired-store contract binds the profile and both store
  identities before SDK schema writes. Canonical schema 2 and its existing
  conversion remain unchanged. No active snapshot or paired-restore result is
  claimed by a prepared manifest.
- An exclusive store lease survives a bounded close timeout. Recovery of a
  dead PID is serialized; malformed/ambiguous ownership fails closed.
- Policy and the model request gate exist before any model dispatch. Native
  title generation is disabled, compaction is not automatic, and unknown
  generation/compaction paths are denied. A retryable model error does not
  consume another attempt without a new admitted request.
- Native interrupted claims are held on reopen. Policy activation and fresh
  unrelated work do not reopen the recovery gate. Deliberate recovery requires
  the complete held selection, matching configuration, no admitted writes and
  no active native execution. The original upstream sweep remains intact.
- `main.ts` keeps desktop reply connections available until the existing
  backend's authenticated drain settles. H24 supplies that drain and actual
  memory-worker lifetime accounting.

## Evidence and scope of the tests

The direct SDK tests use real OpenCode services, its real SQLite persistence,
native execution and its public counting `TestLLM` adapter. Only inference is
synthetic. No subscription, paid provider, GPU inference or private profile is
used. Event-controlled responses model an external operation that remains
uninterruptible until its finalizer can settle.

Observed red/green cycles in this implementation session:

| Behavior | Reproduced failure | Checked result |
| --- | --- | --- |
| First SDK turn | Missing host module, then real import/runtime failures | Saved native transcript reopens unchanged; model count remains one |
| Store ownership | A second real SDK host opened the same store | Second owner is rejected; settled owner can reopen |
| Bounded close | Close observer did not return while external work was held | Timeout is blocked/uncertain; lease remains until actual settlement |
| Recovery | Activation inserted a restart notice into the held transcript | Activation leaves it unchanged; explicit quiescent recovery succeeds |
| Paired selection | A mismatched runtime-store ID still created a database | Mismatch is rejected before runtime database creation |
| Cancellation | No facade cancellation/settlement operation | Native finalizers finish before cancellation acknowledgement |
| Admission/recovery race | Recovery overtook an admitted session creation | Logical write lease blocks the sweep until admission settles |
| Redirected store path | A missing database beneath a Windows junction passed validation | Nearest existing ancestor is checked before opening the SDK store |
| Long transcript observation | Only the oldest fixed page was exposed | Native cursors and bounded pages cover the full transcript and survive reopen |
| Failed recovery inspection | A malformed native claim table left an owner after failed startup | Dispose the real runtime before lease release; repair and reopen without a dangling owner |

The retryable-provider-error regression additionally verifies one failed attempt
without an implicit retry. The ownership suite uses a real separate Node
process and checks reclamation only after its actual exit. Python contracts and
profile preparation separately exercise concurrent initialization, Windows
junctions, stale identities, strict finite JSON and path/control-file collisions.

Final direct checkpoint: **11 SDK behavior tests and 2 ownership tests**, all
passing against the finalized source cohort; consumer TypeScript checking
passes. Receipts are `C:/Renulus/scratch/oc-foundations/host/sdk-final-02.xml`,
`sdk-final-02.txt` and `typecheck-final-02.txt`. The final startup repair has its
own `startup-red-02.txt` and `startup-green.txt` receipts; `startup-red.txt` was a
fixture setup failure, not the reproduced defect. The cohort inventory
SHA-256 is `146d6a4f63a1a699c749d4ede05cb8fa944181ea62e4dbf8dbd0f11ac3e6bd74`.
IPC/UI results and review dispositions are recorded in the integrated foundation
handoff. This does not establish packaged or live-account acceptance.

## Pinned source and actual corrections

See [cohort provenance](../../upstream/opencode/UPSTREAM.md) and
[cohort research](../research/2026-10-10-opencode-foundation-cohort.md).
The source commit is `4b6fea2875e4f2e3e8a8fee181803e54f7056845`, whose package
version text is 2.0.26. The separately published package graph is different.

Relevant permanent references at that commit:

- [Public Effect embedding API](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/effect/opencode.ts)
  and [owned embedded host](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/host.ts).
- [Original recovery sweep](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution/restart.ts)
  releases child claims, so the gate must protect the whole native owner set.
- [Native interruption and settlement](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution.ts)
  distinguishes interruption acceptance, actual cleanup and shutdown claims.
- [Input identity](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/schema/src/session-inbox.ts)
  is a native inbox/message anchor. Receipts use `inputId`, not an invented
  upstream execution identifier.

Real Node execution first failed because conditional import keys had been
sorted, selecting a Bun default before the Node branch. Preserving upstream
condition order fixed this without an upstream implementation patch. A runtime
import of `@effect/platform-node` also required explicitly retaining that pinned
dependency, despite its upstream development classification. Both corrections
belong in cohort preparation, not an artificial runtime shim.

## Remaining boundaries

The default product entry is observable but has no admitted production model
adapter. H02 connects a native cited Library flow; H03 integrates the confirmed
subscription accounts; subsequent tickets supply role routing, temporary
profiles, lineage, tools, context and workflows. H02 owns the first actual
domain/runtime validation and initial active selection before persisting a saved
conversation mapping; H06 consumes that selection for legacy-history migration.
H18 owns complete paired backup/restore activation across migrated producers.
H20 owns distribution, relocation, complete notices and default cutover.
H24 repairs worker lifetime; it does not claim that every memory-quality or
lineage requirement is solved. Hidden UI tests exercise the existing desktop
with the repaired shutdown path, separately from the new SDK host proof.
