Bounded installed-gap binding preparation, 2026-10-06

Prepared a consolidated source patch for the parent deployed gap sidecar at
[installed-gap-slice-20261006](C:/Renulus-native-delivery/desktop-20261005/repo/apps/desktop/.local/installed-gap-slice-20261006).
The patch incorporates the existing prepared699938f2 adaptation, accepts the
independently pinned completed inventory from failed699938f2-next01 through the
shared parent admission helper, repairs the admitted field mapping, and fixes the
observed identity-array parsing defect in a gap-local physical-close helper.
Exit observation also uses asynchronous execFile and is awaited by close, keeping
the Node/Playwright event loop responsive during the existing bounded wait.
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

Every gap journey body from uiState onward is unchanged. In stable-flow,
api/ui/navigate/poll/launch remain unchanged; processProof gains only the async
Exit branch, and close awaits that proof. reuse.json records those exceptions.
The work remains one two-page scanned PDF, the existing Flow
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
confirmed the unchanged gap journey and that the latest stable-flow changes
reverse exactly to the previously sealed candidate when the Exit adaptation is
removed. The PowerShell helper still differs only by its one identity-array
assignment. Read-only applicability checks passed both for the current
consolidated patch against original deployed files and the observer delta against
the complete preserved prior candidate. These are syntax and
applicability results; they supply no acceptance or physical-close evidence.

The parent subsequently reported that Connected02 passed Memory, PDF/PNG
Save/view/reopen and wrong-feedback Plan producer/manual override, and saved the
populated ZIP. Its close observation hit the 30-second bound with main remaining
and backend gone; both were gone after driver finally. Those are parent reports
and are not promoted to a gap close or acceptance result here. The observed
source seam is the synchronous execFileSync Exit call blocking the same Node
event loop that serves Playwright while the app quits. The scoped adaptation
uses callback execFile only for Exit and awaits its decoded JSON in close.
Prelaunch and Inspect retain their existing synchronous behavior and 15000ms
timeout. Helper argv, env, windowsHide, UTF-8 parsing, status proof, identity and
creation-time checks remain unchanged. The PowerShell wait budget remains
30000ms total, and the outer Node observer retains its existing 40000ms timeout.
No app-force termination, extra close, replay, gate or workload is introduced.
The shared admission helper stays pinned exactly to 8fa4b8eb5afbc1dfefabdb1cd2f6b78864ec73a7ec513b54423d837e45b3713b;
parent sibling continuation sources do not replace that view.

The preceding report commit e9e32492104d28d56cd8943b489aa76d7abbb84d remains intact.
Its sealed handoff and complete candidate are preserved byte for byte in
[sealed-before-nonblocking-exit](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/sealed-before-nonblocking-exit).
The current manifest records all 18 preserved files with exact paths/bytes/hash.

| File | Bytes | SHA256 |
| --- | ---: | --- |
| [previous consolidated patch](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/sealed-before-nonblocking-exit/installed-gap-binding.patch) | 39924 | `a2067021de0d7a8a46d2e605daa890a1aa7da58a06b80863c3389e22d6f0fad0` |
| [previous handoff manifest](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/sealed-before-nonblocking-exit/manifest.json) | 13831 | `338ff4bed69bfe71baa52c7817be109c0f102441c250acb50916830f0871059a` |
| [previous operational manifest](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/sealed-before-nonblocking-exit/replacement/manifest.json) | 15091 | `b1a3d8a5b856e6d0ec53b13693e811366bda927d0a51ba61f4de200cd74d6c1d` |

The current sealed transfer artifacts are:

| File | Bytes | SHA256 |
| --- | ---: | --- |
| [installed-gap-binding.patch](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/installed-gap-binding.patch) | 44547 | `c5515e19adebc55cec8fe0ec5e74a77e6be64394aaaf8204b664996777f2ba13` |
| [nonblocking-exit.patch (previous-candidate delta)](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/nonblocking-exit.patch) | 10333 | `20ef5e62a3c3d709494244d9128117f25efaed475b3247e12772da4c09389d43` |
| [manifest.json (handoff)](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/manifest.json) | 26791 | `3229a226c9cce0e93bb013635e273e97e548fcf1b4281e5dc43ac0a0f11e9d4c` |
| [manifest.sha256 (handoff)](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/manifest.sha256) | 80 | `244387fbae8d0f770f21fca7ca583694a5f40991c72ad50005c7960a17d2fc20` |
| [replacement/slice.mjs](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/slice.mjs) | 37460 | `66fc787d004726b2f1a3300046ff5ed2f8e42d78630d8322b677070011eef3ee` |
| [replacement/run.ps1](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/run.ps1) | 1187 | `3d6b3ab8553a5f8353a3065aa66cc9a9c23ae286a76feef960f68a1c349cc139` |
| [replacement/parent-binding.template.json](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/parent-binding.template.json) | 2374 | `b93b67b1e747003efeed42ad11cb13f0b23b910945cbcc0af19756ad39c188ee` |
| [replacement/README.md](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/README.md) | 10555 | `27b3bcd575f1aaea56d75127f7b264630de051c6f5e96b076f85afd34a0af715` |
| [replacement/source-pins.json](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/source-pins.json) | 9247 | `501935130ba463120eebef76e996b4cc1e262e63ffeca75d19bb14a75c27f22a` |
| [replacement/reuse.json](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/reuse.json) | 923 | `09236b07387c49b33262b1055fc1fd254a5bb6c49a5a8b5c6dacded54c136795` |
| [replacement/stable-flow.mjs](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/stable-flow.mjs) | 9533 | `48c109d92661ca80a1101f678df938a9744796afe445ec923e7367d766b2bdaf` |
| [replacement/owned-processes.ps1](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/owned-processes.ps1) | 3252 | `ef269920b423905cd5807cfd3bb7693119efcfdcc15ca27800b9d4109e0246a3` |
| [replacement/manifest.json](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/manifest.json) | 15634 | `7c8da94bfc6448ed201eb24955ada34ae45538d11f7a87d4a6ce372cbc1dd282` |
| [replacement/manifest.sha256](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/manifest.sha256) | 80 | `c27e0e26cdb860252c426f194e823e9f7e3e8d35871c4e884ad9949c49ad3bdf` |

The consolidated patch touches ten ignored parent-sidecar paths, with
298 insertions and 83 deletions, including the new gap-local helper and updated
reuse provenance. The optional nonblocking-exit.patch contains only the Exit
adaptation and its preparation metadata changes against the preserved preceding
candidate. The two patches are alternatives: use the consolidated patch against
original deployed6599 files, or the delta against the exact prior sealed candidate.
Do not apply both or apply the prior6999 adaptation separately. The replacement operational
manifest lists 11 prepared files totaling 80119 bytes
and 29 public source/dependency/origin pins. Its excluded
self files are manifest.json and manifest.sha256. The handoff manifest records
absolute base/replacement paths, byte counts and SHA256 for every patch target,
the three unchanged deployed files, preserved original bytes, public metadata,
prior preparations and the source-only limits. The original dated syntax record
is unchanged; it is not relabelled as a current execution result.

Parent integration still requires preserving the old deployed preparation,
reviewing and integrating this single consolidated patch, checking exact
replacement bytes against the handoff manifest, and supplying the replacement
operational manifest SHA256 `7c8da94bfc6448ed201eb24955ada34ae45538d11f7a87d4a6ce372cbc1dd282` externally.
Parent then selects reviewer/date, a unique unused attempt, the exclusive slot
and the deliberate K01 free check in a separate actual approved binding and
seals its external SHA256. Parent owns the urgent Connected fix, close readback,
Connected/live ordering, slot/app state, gap execution and final acceptance.
The present preparation does not assert that a slot has been released or any
gap check accepted. The report-only commit disables hooks and signing; no
additional subagents or production changes were made.

A remaining source-only consumer blocker was found in the pre-existing copied
[stable-flow launch](C:/rn-finalise-20261005/lanes/connected-contracts-20261006/.local/gap-binding-20261006/replacement/stable-flow.mjs:57):
it calls noLinks(profile) without declaring or importing noLinks in that module.
The local function in slice.mjs does not provide that lexical binding to the
imported stable-flow module. Parent should resolve this missing helper seam
before the actual gap run. It was left outside the requested scalar-decoding
and Exit-observation adaptation, and no launch was executed to probe it.
