# Bounded lifecycle acceptance preparation — October 5, 2026

**Prepared, not completed proof.** Lease: C:/rn-finalise-20261005/lanes/lifecycle-acceptance,
branch codex/finalise-lifecycle-acceptance, base
0618e3fb84571495a2f42a7cd1a24ce86a24de00. Read workspace instructions, README,
brief, workspace, decisions, stage/architecture/parallel rules and the relevant
native, connected, live, packaging and saved-originals records. Recovered the
existing final-acceptance-audit lifecycle-preparation directory read-only. Its
four file hashes and source paths are retained in the ignored metadata.

The parent supplied accepted source freeze
035ca7bd07337c65266c17f9b762ca1f97238e11 on October 5. Expected delivery roots are
C:/Renulus-native-delivery/desktop-20261005/matching-035ca7bd and installed-035ca7bd.
Package was reported running in parent session 61735; no Package completion,
Install or native17 receipt was supplied. This lane does not query that process
or credit an unperformed gate. The new migration and UI are integrated at the
supplied freeze; receipt binding and all actual lifecycle execution remain pending.

The parent owns the freeze, manufacture, installation, matching native17,
connected/live acceptance and serial execution. No app, Python interpreter,
profile, helper/model, provider/network, installer/uninstaller or pytest run
occurred in this lane. Only owned ignored scripts/metadata and this report change.
No watchers, heartbeats or delegated chats were started.

The useful new prerequisite is real schema evolution. The installed f316 bundle
metadata names f3160c596eb3132fc7599c08d5973c3f7ddd9acb; its cases-001 SQL is
present and it lacks cases/migrations/002-originals.sql. The leased source adds
immutable cases-002-originals with case_attachments and case_attachment_parts.
The earlier 3ff/f316 same-schema observation cannot establish this migration.
SUPPORTED_SCHEMA remains 1; the additive checked ledger/table change is the
evolution under test. Current installed source and artifact identity must be
supplied later through actual receipts and matched to expected 035ca7bd;
base 0618e3fb is not relabelled as the accepted freeze.

| Parent gate | Small executable recipe and required observation |
| --- | --- |
| Admission | bind-lifecycle.ps1 requires actual matching Package/Install/native17, passed connected and live journeys with ordinary closes, f316 predecessor receipts and actual NSIS policy-provenance.json. Derive revision, installer, exact compiled target and closed native17 restored-profile from those inputs. Refuse partial/fixture/stale identities; preserve E and both checkpoints. |
| Populated forward migration, interruption and refusal | run-storage.ps1 creates one small owned scratch/profile. Installed f316 Database seeds a saved synthetic case, preference, evidence and deletion marker. Current bundled Database executes actual 002 SQL; one self-owned unclean exit occurs after both DDL statements and before ledger commit. A fresh process must find neither tables nor ledger and unchanged populated rows. Complete/replay migration without changing cases-001; actual installed originals functions save/read a PDF across two base64 parts. Reopen, checksum-drift and schema-99 refusal retain records/integrity. |
| Installation lifecycle after live proof | run-maintenance.ps1 snapshots only the retired synthetic profile, uninstalls the exact accepted current target once, verifies retention while closed, reinstalls the same installer to the same now-absent target with test-installer.ps1 -InstallOnly, then performs one ordinary reopen/close and canonical/original comparison. The actual new install receipt must match the earlier installer, EXE, ASAR and source identity. |
| Optional exact old/current compatible opens | run-compatible-open.ps1 opens receipt-bound f316/current on the same closed native17 restored-profile, with ordinary owning main/backend exit and identical canonical/original snapshots after each. No restore/downgrade, imports, models, quizzes or native17 repetition. An old API/content incompatibility remains a failed result; app compatibility does not replace the real migration gate. |

The NSIS policy source in apps/desktop/scripts/restage-nsis.py compiles
StrCmp "$INSTDIR" "<exact target>" +3 0, SetErrorLevel 13, Quit. The binder checks
the actual generated header and its recorded SHA256. test-installer.ps1 refuses
an existing target before NSIS execution; a second disposable /D is not a valid
alternative. Current target deletion is the user's explicitly authorised scoped
maintenance. Residual handling admits only the observed expected uninstaller
with unchanged hash and a verified empty exact directory, with literal
nonrecursive removal. Unexpected residuals stop the run. No broad/forced delete,
registry bypass, renaming, unowned process termination or checkpoint uninstall.

Maintenance uses f316 bundled Python only as a stdlib read-only snapshot reader
while current Python is absent. App children use OS-only PATH. Actual migration
imports are limited to installed storage and installed originals functions;
there are no engine/model/rebuild/import/quiz/provider operations. Snapshot
signatures include saved cases/base64 parts, attempts/pins, content, memory,
manual study records, preferences, deletion markers, passages and synthetic
original hashes, excluding credential stores and derived queues/index state.
The normal E learning profile, raw source originals and PID 38448 are preserved.

Use PowerShell 7 and the existing parent harness Node. The following values are
the parent's actual completed receipt paths, frozen public C repository and
assigned exclusive slot. The expected revision is the parent-supplied freeze,
not a manufacture/install claim.

~~~powershell
$prep = 'C:/rn-finalise-20261005/lanes/lifecycle-acceptance/.local/lifecycle-acceptance'
$inputs = @{
    ExpectedRevision = '035ca7bd07337c65266c17f9b762ca1f97238e11'
    PackageReceipt = $actualCurrentPackageReceipt
    InstallReceipt = $actualCurrentInstallReceipt
    Native17Receipt = $actualCurrentNative17Receipt
    ConnectedReceipt = $actualCurrentConnectedReceipt
    LiveReceipt = $actualCurrentLiveJourneysReceipt
    PredecessorPackageReceipt = $actualF316PackageReceipt
    PredecessorInstallReceipt = $actualF316InstallReceipt
    NsisPolicyReceipt = $actualCurrentPolicyProvenance
    Repository = $actualFrozenPublicDeliveryRepository
}
$bound = & "$prep/bind-lifecycle.ps1" @inputs
$storage = & "$prep/run-storage.ps1" -Run -Binding $bound.binding -Slot $parentLifecycleSlot
& "$prep/run-maintenance.ps1" -Run -Binding $bound.binding -StorageReceipt $storage.receipt -Slot $parentLifecycleSlot -NodeExecutable $parentExistingHarnessNode
# Optional compatibility evidence, separately scheduled before maintenance:
# & "$prep/run-compatible-open.ps1" -Run -Binding $bound.binding -Slot $parentLifecycleSlot -NodeExecutable $parentExistingHarnessNode
~~~

With no arguments the PowerShell entry points return metadata plans and launch
nothing. Each execution mode has a single-attempt latch. Failure, timeout,
changed receipt/source, unknown residual or unconfirmed ordinary close stops
without replay or forced cleanup. A timeout retains the exact owned identity
for the parent to inspect. The parent keeps actual storage-evidence.json,
maintenance-evidence.json, new installer-evidence.json, reopen-evidence.json and
snapshot comparisons; optional comparison has its own receipts.

Ignored executable sidecar: C:/rn-finalise-20261005/lanes/lifecycle-acceptance/.local/lifecycle-acceptance.
README.md contains the receipt contracts and bounded invocations;
preparation.json contains the checks, hashes and recovered input provenance.
Cherry-picking this report does not transport ignored scripts; run them from
this dedicated worktree. All five PowerShell files parse without AST errors;
the JavaScript file passes node --check without imports. Python files received
source inspection only; no interpreter was invoked. No current receipt was
bound, no scratch/profile was created, and no runtime acceptance is claimed.

| Ignored executable | SHA256 |
| --- | --- |
| bind-lifecycle.ps1 | 26b106822611a1a3a10b937d4a06c3f093cbc1dc36cbd9a6ed36a022e6d3be92 |
| common.ps1 | 792d774f294e13e1b3086963b3a63ee5a0032a6845fe453ca5b775852619ab54 |
| reopen-synthetic.mjs | 514140b83c51aca407afa1f846062caa0c5e72d705c452567194d2a142d88d0e |
| run-compatible-open.ps1 | 810cbd3395f65c9279b88ed71c5cf9dd6399a59c314b96cbd3a35118beb3fa6a |
| run-maintenance.ps1 | 8d6e81673fd49f8c01da09c62b0c9e95e66dc76ca6a3aa1a6633f2e8d49f8612 |
| run-storage.ps1 | 88a4fac3e9ef7b7ed7289da4dff46fb8ed1265068f9e9d77b488564c333ed060 |
| snapshot-synthetic.py | 32efb0d7a1552c0a5f175ad8c96db97b7a8fb109aab14932bf76d1c502563b57 |
| storage-gates.py | e4e494fb7b9122c26ec3e2d9f4c68eb9b9b72f083d0ecc4550ab40592e61ac38 |

Remaining acceptance is parent execution on the matching accepted current
installation. Storage receipts establish the actual coordinator/SQL boundary,
not native refusal presentation or a physical power-loss event. Same-profile
opens establish only observed compatibility. Synthetic retention proves only
the explicit owned profile. Source, artifact, native, connected and live gates
remain prerequisites; preparation does not close S0/S6 lifecycle requirements.
