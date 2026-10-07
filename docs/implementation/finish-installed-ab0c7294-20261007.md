# Matching ab0 manufacture and installed Memory/Home disposition

Receipt review: 2026-10-07. Exact installed source revision:
`ab0c72949124fb188a865be12e8d8ea551f6a55e`.

**Admit the matching unsigned ab0 manufacture/install and the completed
Memory/Home operations as a composite of installed01 and installed02 at the
scope below. Installed01 remains a failed aggregate, exit 1. Installed02 passed,
exit 0. Ready-state recall of the corrected record after reopening remains the
parent's final check.** No full live-provider, compaction-race, physical
accessibility or later-content-successor acceptance is inferred.

This report is the only edit in `codex/final-content-disposition`, starting from
clean `6eb0cb35cea689058290b5db3ef312d6ea7941aa`. It reads only the eight declared
synthetic receipts listed below. Their hashes were computed from the actual
files. Referenced screenshots, profiles, databases, underlying logs, binaries
and earlier receipt bodies were not opened. No tests, native execution, models,
providers, content imports, private data or GitHub operations were used.

## Matching manufacture and installation

`build.terminal.json` records exit **0**, from
**2026-10-07 17:35:56.491721 UTC** to **18:02:08.230269 UTC**
(1571.738564 seconds). `package-result.json` records
`manufactured-and-installed`, `installer_manufactured: true` and
`profile_used_during_build: false`.

The receipt identifies the committed backend, renderer and native source as
the exact ab0 revision. Backend `source_patches` is empty. Renderer and native
typecheck/build are recorded as passed. The native backend adoption's source
and adopted hashes agree. The package uses Electron 44.5.1 and embedded CPython
3.14.4; these are recorded package identities, not newly executed checks.

Both packaged and deployed backend verification record **39,275 files** with
the same inventory SHA256. The receipt records 33,509 unchanged dependency
files from the earlier public payload. The copy phase's `robocopy_exit: 1` is
preserved as a phase value; the completed manufacture/install aggregate is the
separate build exit 0. No source or dependency refresh was performed here.

| Artifact identity recorded in package receipt | SHA256 |
| --- | --- |
| NSIS installer | `b9d8eb990ee708176b223da822cb8290841c96a9324fad1421d79454486fd6c2` |
| Packaged executable | `eefd428a2182cdd3eb4497c6567f97ab7e75dcc72bbc14ecbfe167e83148e10f` |
| `app.asar` | `a780d1e4f88130ccfd4ce142adf28c10f6c8a6ac12fa69e2a19c377bd623ef07` |
| Packaged and deployed backend inventory | `a552fe29019903343256837d8549d60631bbc7ab707a2adb209461ba440be300` |

The installer is recorded at
`C:/Renulus-native-delivery/desktop-20261005/matching-ab0c7294/Renulus-Development-0.1.0-windows-x64-setup.exe`;
the installed executable is
`C:/Renulus-native-delivery/desktop-20261005/installed-ab0c7294/Renulus Development.exe`.
The artifact hashes above are credited from the package receipt, not freshly
recomputed from those binaries. The package's original `native_launch: pending`
field remains unchanged; later installed receipts supply the bounded launch and
lifecycle observations below. This does not establish a signed release or
change the user's normal launcher target.

## Installed composite: exact admissions and remaining boundary

Both installed results pin the same package receipt SHA256 and ab0 source
revision. Installed02 also pins installed01's actual result hash and failure-UI
hash, retains `originalStatus: failed`, and records `reexecuted: false`.

| Scope | Exact supporting receipt and observation | Disposition |
| --- | --- | --- |
| Fresh Home | Installed01 completed `fresh-home-real-empty-state`: `resume: []`, `updates: []`, 27 topics. | Admit the observed synthetic fresh empty state. |
| Canonical correction | Installed01 completed `canonical-memory-correction`: one identified record at revision 2, corrected synthetic learning preference, index ready, helper ready, zero pending jobs, producer `mem0-oss`. | Admit canonical correction and that pre-reopen ready observation. |
| Home question and actual retained-context use | Installed01's failure UI visibly retains the submitted synthetic question and reports use of **1 retained learning record**. It also shows the subscription-connection error and no retrieved scientific evidence. Installed02 corroborates the same durable thread/run as `failed` / `connection_required`, with `retainedQuestion: true`. | Admit actual visible one-record context use and preserved connection-required failure; this is not inferred merely from an available-memory count. No successful explanation is claimed. |
| No answer/capture/provider side effects | Installed02 records zero assistant answers, capture jobs and provider requests for the retained run. Both invocations declare zero provider calls and library imports; installed02 additionally records zero question requests and `questionReexecuted: false`. | Admit continuation without resubmitting the question or generating a new answer/capture. |
| Return Home and Resume | Installed02 completed `home-return-and-resume` against the same retained thread. Its first normal close records no forced or remaining PIDs. | Admit return/Resume and that normal close. |
| Normal reopen and persistence | Installed02 completed `normal-reopen-preserves-corrected-record-and-question`: same record at revision 2, same thread, message count 1, duplicate records 0. Its final normal close again has no forced or remaining PIDs. | Admit persistence of the correction and single retained question, no duplicate record, and normal reopen/close. |
| Corrected-record recall once the reopened index is ready | Installed02's result establishes canonical persistence, not a new ready-state recall. The parent reports its reopen screenshot catches index rebuilding. This sidecar did not open that screenshot. | **Pending parent final check.** Do not promote canonical revision 2 persistence or the screenshot label to proof of ready post-reopen retrieval. |

The receipt join uses record
`memory_cf8937a556fb495f89a756c7fae2514d` and thread
`thread_cad01f77985e4650b246d48852d0677b`. These are declared synthetic acceptance
identities. The one-record UI observation does not expose the selected record's
full payload or establish scientific support. The retained UI explicitly says
that personalization does not verify scientific evidence.

Installed01 ran **20:05:24.089149–20:07:04.950224 UTC**, exit **1**. Its
`installedAcceptance` remains false. After the two completed steps it failed in
`home-ask-canonical-recall-connection-error` while the driver called
`response.text` / `Network.getResponseBody`: the response body was unavailable
after navigation. The driver failure is retained; neither the later durable
state nor the visible UI is used to relabel this aggregate as passed or invent
a recovered response body.

Installed02 ran **20:11:10.451638–20:12:17.913176 UTC**, exit **0**, with
`status: passed` and `installedAcceptance: true` for its stated continuation
scope. Its normal-close observations finish at **20:11:48.011 UTC** and
**20:12:17.887 UTC**. It preserves the earlier operations and adds only the
missing persistence/return/reopen observations. The aggregate pass does not
remove the separate post-reopen ready-recall boundary above.

## Runtime qualification and preserved earlier credit

`runtime-qualification.json` names baseline
`0318c41f916ed6861a7b3be52a1d5fc37a1ca0ff` and ab0 as candidate. It records only
`runtime/renulus/learn/memory_context.py` and
`runtime/renulus/learn/service.py` as production differences. All 18 listed
comparison objects are equal, including desktop, storage, memory, content,
engines, pack trees, Hermes, runtime packaging and dependency contracts.

This supports retaining earlier evidence at its original scope while examining
the changed consumer/lifecycle. The qualification explicitly sets
`fullExecutionAtCurrentTarget: false` and `providerCallsRepeated: 0`; its focused
controlled regression provenance names tested revision
`fab88e1d9070220a56c4b35accc7c6f5f421ee42`, not a newly executed live ab0 run.

Its referenced 0318 content admission preserves the original two failed driver
aggregates. Historical connected, engine, recovery and retention observations
remain chained evidence. The cited controlled regression evidence retains 13
accepted concurrency cases and 14 prior individual passes whose aggregate had
13 setup errors. These are the qualification receipt's recorded scopes; their
underlying files were not reread or reexecuted by this report.

This ab0 admission does not cover the subsequent T18 1.4.1 integration or the
parent's planned immutable ESENeph successor, fixtures or final manufacture.
It does not certify a live connected answer, live compaction race, all source
currentness, all native flows or the owner-operated physical S6.04 observations.
No prior accepted proof or failed aggregate is discarded. Parent owns the final
ready-recall check, later release decision, integration and worktree preservation.

## Actual receipt hashes

All paths below are relative to
`C:/rn-finish-20261007/evidence/release-ab0c7294/`. These SHA256 values were
computed from the eight declared files during this read-only review.

| Receipt | Bytes | SHA256 |
| --- | ---: | --- |
| `package-result.json` | 18233 | `e96a8015c80b8c9fc1645152246c6b85d55e29d69e8875901dd1c10f18443139` |
| `build.terminal.json` | 314 | `066cb21b6cdc3eec35ef596884d96f4b714a671eefeebf9118a8f8ae3538a7ce` |
| `runtime-qualification.json` | 5720 | `f11426dcceeba82d54a4a5f9b93cf72fc7d951839e10947b0c56d9b95dd3bd85` |
| `installed01/result.json` | 2699 | `80e845a182cf0ea994a117c3c52a8f071350dfa05f1dd79f9d4c29519c1ff8ea` |
| `installed01.terminal.json` | 336 | `a9760a7161e0a068db608af8f9e78f09b08fe4c8176832a402ac15e1a127405f` |
| `installed01/failure-ui.txt` | 3980 | `1a2d67d916ff22bd9e7016be9f147889b7677d4efd677e6e2f6149a0d49dee30` |
| `installed02/result.json` | 4027 | `b305a0295a066bb560f9a7b546914b6a529b3e3330029b1560e96f652cccfd91` |
| `installed02.terminal.json` | 335 | `249c2f0d1f8e314acf9bcbf50dae8663541129281463e9ed4698503104192041` |

The package hashes embedded in both installed receipts match the first row.
Installed02's retained-invocation and prior-UI hashes match the installed01
result and failure-UI rows. Original receipts were left byte for byte unchanged.
