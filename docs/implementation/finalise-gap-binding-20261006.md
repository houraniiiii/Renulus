Bounded installed-gap binding preparation, 2026-10-06

Prepared a consolidated source patch for the parent deployed gap sidecar at
[installed-gap-slice-20261006](C:/Renulus-native-delivery/desktop-20261005/repo/apps/desktop/.local/installed-gap-slice-20261006).
The patch incorporates the existing prepared699938f2 adaptation, accepts the
independently pinned completed inventory from failed699938f2-next01 through the
shared parent admission helper, repairs the admitted field mapping, and fixes the
observed identity-array parsing defect in a gap-local physical-close helper.
Only this report and the ignored [gap-binding-20261006](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006) directory were
written. No parent files, production code, schema, renderer or tests were edited.
The completed Connected contracts report and all three original sidecars remain
unchanged.

The lane is C:/rn-finalise-20261005/lanes/connected-contracts-20261006 on
codex/connected-contracts-20261006, with this additional task based on
86c2d2cbe9b96149868ac6ee28fcc6525d25cb56. Required repository and planning docs
were read. The exact admitted installed source is
699938f20efb6bbc2cf8df684cc5c6c3450e6eaf and the executable remains
C:/Renulus-native-delivery/desktop-20261005/installed-699938f2/Renulus Development.exe.

The prior [finalise-installed-gap-699938f2.md](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/docs/implementation/finalise-installed-gap-699938f2.md)
and its related source-only preparation were inspected before adaptation. The
preserved prior manifest at
C:/Renulus-native-delivery/desktop-20261005/repo/apps/desktop/.local/installed-gap-699938f2/manifest.json
is 13222 bytes, SHA256 `8a989a2b77071bc5030287fe74ee3c243d2afc3faa78f0de4a6c33c54cd78101`; its
adaptation-source.patch is 17693 bytes, SHA256
`3c5fd2f3ef4fe63d47ea4f65d5f36ad286095a6f11df1cb9aad77507c4fc8ebd`. The actual deployed manifest is
11040 bytes, SHA256
`7da02cd44f6aa86dcbcafeb89cc717d73e48bb791f2fcd2f95bfe5b591e0337c`. This handoff applies directly to that
original deployed sidecar; applying the prior699938f2 patch again would duplicate
changes. The original physical Playwright paths are preserved, avoiding the
junction paths in the prior prepared adaptation.

The consumer reads actualCurrentSlice, executionBinding, originLedger and
sourceFiles returned by the pinned shared helper. It has no dependency on a raw
native.sources map. inventoryCarry.sourceFields supplies these exact mappings:

| Field | Admitted pin |
| --- | --- |
| package_receipt | binding.packageReceipt, checked against admitted identity and executionBinding |
| install_receipt | binding.installReceipt, checked against admitted identity and executionBinding |
| current_slice | native.actualCurrentSlice |
| execution_binding | native.executionBinding |
| origin_ledger | native.originLedger |
| parent_source_qualification | the unique sourceFiles parent-source-qualification pin, SHA256 058c955649bff2434c2a0cdc9dfae1a84ae4404e733587203a4d03e0d5f7313a |
| native_admission | binding.nativeAdmission |
| inventory_origin | completedSameTargetInventory.record, or null for the retained direct fresh-inventory case |

The original fresh inventory contract remains inventoryFreshlyExecuted=true,
inventoryTransfer=null and no carried origin. The continuation contract requires
inventoryFreshlyExecuted=false, the exact independently pinned same699938f2
transfer record, matching sourceRevision, 39255 inventory files and 5742 frozen
files, a failed origin invocation, nativeDriverAccepted=false and the original
passing installed-identity gate. The shared helper retains validation of the
original source, artifacts, receipt, entry, binding, process, stdout/stderr,
terminal and closed-state pins. The gap consumer uses that validated origin;
it does not execute admission here or repeat the installed inventory scan.
Inventory attribution remains explicit with inventoryFreshlyExecutedHere=false,
zero rechecked leaves, original receipt/entry/binding and transfer metadata.
Failed-next01 receives no native-driver, ordinary-close or acceptance credit.
The parent-owned recovery02 gates and three new ordinary closes remain the
current operational boundary; all historical admissions and accepted checks
retain their existing attribution.

The supplied exact public metadata and helper pins are:

| File | Bytes | SHA256 |
| --- | ---: | --- |
| [shared admission helper](C:/Renulus-native-delivery/desktop-20261005/repo/apps/desktop/.local/next-installed-20261006/composite-native-admission.mjs) | 21724 | `8fa4b8eb5afbc1dfefabdb1cd2f6b78864ec73a7ec513b54423d837e45b3713b` |
| [completed current inventory origin](C:/rn-finalise-20261005/parent-native-recovery-699938f2-699938f2-next01/completed-current-inventory.json) | 4111 | `e1c7e2dc03a79b37f5b195d03f4f3fcee22c434ab80daa14f3abde81e0953904` |
| [nativeComposite](C:/Renulus-native-delivery/desktop-20261005/repo/apps/desktop/test-results/installed-product-4c73b819/source-qualified-native17-699938f2.json) | 946792 | `825ae4dbaebe40f5f8c3401f56c453d3b486c5787d61ef05b07bdc2e40592108` |
| [nativeReconciliationReview](C:/Renulus-native-delivery/desktop-20261005/repo/apps/desktop/.local/next-installed-20261006/native-review.json) | 44596 | `03564473e0e97f7214248034e0188205e8e39ee4464b98c9e9c506b1f64dd8d5` |
| [packageReceipt](C:/Renulus-native-delivery/desktop-20261005/matching-699938f2/delivery-provenance.json) | 107668 | `9ab9e469ea4e925c72ec19531521a41ff95a00cea121c6bc7fb7a4d1fd34a2c4` |
| [installReceipt](C:/Renulus-native-delivery/desktop-20261005/proofs/installer-e794e99d/installer-evidence.json) | 1410 | `3bc8ab092a6ef0445f2b80b62f5c589b21059c71d14998b904f65c621a2f62b7` |
| [executionBinding](C:/Renulus-native-delivery/desktop-20261005/repo/apps/desktop/.local/next-installed-20261006/execution-binding.json) | 11428 | `3c661100e737f27f9fa0f16e8728d58888b51c1fabdd685454868ed544cfd1a4` |
| [actualCurrentSlice](C:/Renulus-native-delivery/desktop-20261005/repo/apps/desktop/test-results/installed-product-4c73b819/recovery-resume-699938f2-next02/installed-product-recovery-resume-evidence.json) | 1028876 | `2a7d14a4d2e6b45028d2a9b90342f472baf72fe66d3beeb0598729917f799304` |

The template contains those actual composite, native-review, Package and Install
pins but remains approved=false. parentReviewer, reviewedAt, exclusiveSlot and
attempt remain null; k01FreeCheckSelected remains false. The native-review hash
03564473e0e97f7214248034e0188205e8e39ee4464b98c9e9c506b1f64dd8d5 is distinct from
the retained independent source-qualification hash 058c955649bff2434c2a0cdc9dfae1a84ae4404e733587203a4d03e0d5f7313a.

The parent's 2026-10-06 10:35:05 UTC update identified a Connected01 manual-memory
initial-stage timeout and an Exit-helper parse defect; Connected close remains
unconfirmed until parent readback. Native recovery's three ordinary closes came
from a separate driver and are unaffected by that report. The gap stable-flow
source was found to call a preserved6599 helper with the same parse line.
A copy is now proposed inside the gap sidecar; stable-flow changes only
PROCESS_HELPER to that gap-local path. The original helper's single changed
assignment is:

`$renulusOwners = @(ConvertFrom-Json -InputObject $Identities | ForEach-Object { $_ })`

Piping the decoded array through ForEach-Object emits its individual identities
before the existing integer PID casts. Identity matching, creation times,
protected PID38448, bounded wait and no-force-kill behavior remain unchanged.
The parent-owned shared helper is not patched here. Exact original helper and
stable-flow bytes are preserved as:

| File | Bytes | SHA256 |
| --- | ---: | --- |
| [original/owned-processes.ps1](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/original/owned-processes.ps1) | 3228 | `5e163a494a755708712bf5f2d023b37eedd137203b92cb144a34f9432d7950ff` |
| [original/stable-flow.mjs](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/original/stable-flow.mjs) | 9026 | `bed446f975b58f403091d25f83b237fea1552d2f46fcc1414bb6d1c302dc606a` |

Every gap journey body from uiState onward and every stable-flow function body
is unchanged. The work remains one two-page scanned PDF, the existing Flow
keyboard/AX/reader/size/zoom/reduced-motion observations, one deliberate free K01
check with automation OFF, and ordinary close/reopen/close. No actual K01 fetch,
source import or reimport, fixture generation, model/provider/network operation,
app/runtime/native execution, process inspection or close, test, admission
function or Run/Plan wrapper was performed. Existing unproved spoken-reader,
Windows DPI, complete accessibility, OCR-confidence, parser-error, stale Updates,
educational-review, guidance-currency and clinical-accuracy limits remain.

Node24.15.0 --check --input-type=module through stdin parsed slice.mjs and
stable-flow.mjs without importing either module. PowerShell AST parsing accepted
run.ps1 and owned-processes.ps1 without executing them. Read-only git apply
--check passed against the actual parent deployed files. Source comparisons
confirmed the unchanged gap journey and stable-flow function bodies, and the
helper changed only its one identity-array assignment. These are syntax and
applicability results; they supply no acceptance or physical-close evidence.

The sealed transfer artifacts are:

| File | Bytes | SHA256 |
| --- | ---: | --- |
| [installed-gap-binding.patch](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/installed-gap-binding.patch) | 39924 | `a2067021de0d7a8a46d2e605daa890a1aa7da58a06b80863c3389e22d6f0fad0` |
| [manifest.json (handoff)](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/manifest.json) | 13831 | `338ff4bed69bfe71baa52c7817be109c0f102441c250acb50916830f0871059a` |
| [manifest.sha256 (handoff)](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/manifest.sha256) | 80 | `c0d1076e83b35906f5207c7367b806321a026f8d54cec37a7e66a316f6fba55c` |
| [replacement/slice.mjs](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/slice.mjs) | 37460 | `66fc787d004726b2f1a3300046ff5ed2f8e42d78630d8322b677070011eef3ee` |
| [replacement/run.ps1](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/run.ps1) | 1187 | `3d6b3ab8553a5f8353a3065aa66cc9a9c23ae286a76feef960f68a1c349cc139` |
| [replacement/parent-binding.template.json](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/parent-binding.template.json) | 2374 | `b93b67b1e747003efeed42ad11cb13f0b23b910945cbcc0af19756ad39c188ee` |
| [replacement/README.md](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/README.md) | 9862 | `b2282ba5dcc129492ab1650eb2b65f43ee2be2a0f19e4778cda5fa2218f18063` |
| [replacement/source-pins.json](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/source-pins.json) | 9247 | `501935130ba463120eebef76e996b4cc1e262e63ffeca75d19bb14a75c27f22a` |
| [replacement/stable-flow.mjs](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/stable-flow.mjs) | 9043 | `c52bc9ae615815bf9ff7044a470133eb952ecedc18c15d0b155f565e10be753d` |
| [replacement/owned-processes.ps1](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/owned-processes.ps1) | 3252 | `ef269920b423905cd5807cfd3bb7693119efcfdcc15ca27800b9d4109e0246a3` |
| [replacement/manifest.json](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/manifest.json) | 15091 | `b1a3d8a5b856e6d0ec53b13693e811366bda927d0a51ba61f4de200cd74d6c1d` |
| [replacement/manifest.sha256](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/manifest.sha256) | 80 | `d4a6999c847565a4f17b6addf0c729f847526786c1b1bf03e2c3b4e542e129f7` |

The patch touches nine ignored parent-sidecar paths, with 264 insertions and
76 deletions, including the new gap-local helper. The replacement operational
manifest lists 11 prepared files totaling 78693 bytes
and 29 public source/dependency/origin pins. Its excluded
self files are manifest.json and manifest.sha256. The handoff manifest records
absolute base/replacement paths, byte counts and SHA256 for every patch target,
the four unchanged deployed files, preserved original bytes, public metadata,
prior preparations and the source-only limits. The original dated syntax record
is unchanged; it is not relabelled as a current execution result.

Parent integration still requires preserving the old deployed preparation,
reviewing and integrating this single consolidated patch, checking exact
replacement bytes against the handoff manifest, and supplying the replacement
operational manifest SHA256 `b1a3d8a5b856e6d0ec53b13693e811366bda927d0a51ba61f4de200cd74d6c1d` externally.
Parent then selects reviewer/date, a unique unused attempt, the exclusive slot
and the deliberate K01 free check in a separate actual approved binding and
seals its external SHA256. Parent owns the urgent Connected fix, close readback,
Connected/live ordering, slot/app state, gap execution and final acceptance.
The present preparation does not assert that a slot has been released or any
gap check accepted. The report-only commit disables hooks and signing; no
additional subagents or production changes were made.
