# Windows storage cleanup — October 8, 2026

The owner authorised removing redundant Renulus storage and consolidating needed
material under `C:/Renulus`. Work is tracked in
[issue #22](https://github.com/houraniiiii/Renulus/issues/22). Product source stays
`f1c49444ba77f03fe0f35f4657e564c1b26724dc`, content 1.4.2. This maintenance does
not extend the accepted product, provider or physical-accessibility scopes.

## Current organisation

| Path | Contents |
| --- | --- |
| `C:/Renulus/app` | Unchanged accepted installed application and bundled runtime |
| `C:/Renulus/dev/repo` | Canonical checkout; `origin` is solely `houraniiiii/Renulus` |
| `C:/Renulus/dev/python` | Retained contributor Python environment |
| `C:/Renulus/dev/node_modules` | Retained desktop dependencies |
| `C:/Renulus/dev/helper-assets` | Pinned public CPU helper files |
| `C:/Renulus/data/sources` | Acquired originals, acquisition metadata, reports and source ZIP |
| `C:/Renulus/data/learning` | Migrated learning/account profile, canonical records and derived indexes |
| `C:/Renulus/releases/f1c49444` | One current installer and delivery provenance |
| `C:/Renulus/evidence` | Successful/failed receipts, source snapshots and required synthetic state |
| `C:/Renulus/archive` | Unique earlier history/edits, canonical state and separate inherited reference |
| `C:/Renulus/scratch` | Owned synthetic controller state |
| `C:/Renulus/maintenance/cleanup-20261008` | Private manifests, scripts and operation ledger |

`C:/Renulus/Start-Renulus.cmd` and the repaired desktop shortcut select the new
app. `C:/Renulus/tools/Control-Renulus.cmd` starts the app-scoped development
controller. The owner learning/account profile is now `C:/Renulus/data/learning`.
The former E: profile path is a compatibility junction to the new location.

Old acquisition and evidence directories are mostly junctions, so their retained
references do not create extra large copies. Two old checkout roots were held
open by other processes: their contents were consolidated, and they now contain
a Git pointer, directory junctions and small compatibility files. Git resolves
both to the canonical checkout. Use `C:/Renulus/dev/repo` for development.

## Removed and retained

- Retired 45 stale linked worktrees after preserving unique commits, patches,
  files and ignored state. The one active checkout remains. The historical Git
  bundle verifies and includes two recovered reflog-only commits; 31 unique
  files/patches and their hashes remain outside Git.
- Removed the obsolete 182,933,352,107-byte derived integration index after
  preserving and hashing canonical SQLite state and Library originals. The
  owner's active profile and accepted final Memory evidence were excluded.
- Removed 62 superseded build/package trees, old Node/helper staging caches and
  the obsolete updater installer. Preserved 260 build/provenance/source files.
- Pruned archived generated backends, obsolete packaged executables and two
  stale virtual environments. Their source, content, notices, dependency
  inventories, locks, receipts and failure records remain. Retained historical
  source/evidence folders are not promised to run with their old dependency
  links; reproduce a historical build deliberately from its recorded source.
- Replaced 65 identical large public helper copies with hardlinks after hash
  comparison, removing 6,266,604,305 duplicate bytes while retaining file content
  and paths. Accepted corrected-Memory state/helpers were left unchanged.
- Consolidated the acquired collection, archive and evidence; restricted data,
  account material and maintenance manifests remain outside Git. Original source
  terms, acquisition dates and currentness qualifications are unchanged.
- Removed 14 obsolete Windows uninstall registrations; the retained current
  registration points to `C:/Renulus/app`. No old uninstaller was executed.

## Verified identities and operation

The final metadata inventory at **16:11:49 UTC on October 8** reported no scan
errors. Renulus-related logical file sizes fell from **504.36 GB to 148.03 GB**,
a **356.33 GB reduction**. Counting each volume/file identity once gives
**141.77 GB** retained file content, all on C: except **439,025 bytes** of
compatibility receipts on E:. The former G: collection contains only its
compatibility link. These are
decimal GB and file-size measurements, not an exact NTFS cluster-allocation or
drive-free-space claim. The live owner profile may change after this snapshot.

| Main retained category | GB, counting hardlinked files once |
| --- | ---: |
| Acquired source collection and metadata | 88.15 |
| Earlier development history/source/state archive | 13.57 |
| Retained run evidence | 12.22 |
| C: delivery evidence/preparation | 8.53 |
| E-origin delivery evidence now on C: | 3.54 |
| Separate inherited reference | 2.63 |
| Older canonical state/originals and recovery preparation | 2.41 |
| Current installed app | 2.60 |
| Current learning/account profile | 1.79 |

Development tools, the current installer, new synthetic control state and
maintenance records account for the remainder. `before.json` and `after.json`
contain the complete inventory; `after-before-profile-cutover.json` preserves
the intermediate measurement. The first after-scan hit Windows long-path
limits; its receipt is retained as `after-preliminary-longpath-failed.json`.
The corrected final scan used extended paths and had zero errors.

| Preserved material | Verification |
| --- | --- |
| Acquired raw collection | 183,973 files; 86,308,626,167 bytes; full source/destination SHA inventory identity `50e00a999b6fb2ab93841a0be69243a93e0f9eff82c6431e7f081f9e863bbd41` |
| Installed app | 39,378 files; 2,603,599,151 bytes; full source/destination SHA inventory identity `d71c030bec602e13a2a587bbe7e1fceef481f1acbeb08ba45fbd1248797faf22` |
| Current installer | SHA256 `7ebfce8a03fe9b3fdd702e7aeb1fd6ba41cdc21784bc70990602ded167de2baf` |
| Earlier Git bundle | 94,155,382 bytes; SHA256 `4d232b5067a1aab84ea9859e681d1fb74e5f00a1c203430572b39dd0141f60d8`; bundle verification passed |
| Old integration canonical state | 3 files; 1,601,180,049 bytes; inventory identity `7d6c207c00248e1962fbc3d966dffdffdd51ff204b6835493678b4579d6ee95d` |
| Old integration Library originals | 7,254 files; 507,308,245 bytes; inventory identity `9fb4b3d73ef726bfeacbf9f27131d34b3125e4a1c921f1f90054f65980be006e` |

The relocated source controller started, returned a snapshot/errors result and
closed normally with its own synthetic profile. The relocated installed app
used its bundled runtime, reached the Today heading, closed/reopened the same
synthetic profile, reached Today again and closed normally. Both terminals exited
0. This verifies relocation/lifecycle at those scopes, not owner-profile migration
or a repeat of live generation, imports, recovery or physical accessibility.

The retained Python editable import resolves to `C:/Renulus/dev/repo/runtime`.
Its console entry points were regenerated from the existing installed package
metadata using distlib; `pytest.exe --version` and Python/import location checks
passed. No dependencies were installed. The initial direct executable rewrite
failed and was restored before regeneration; that attempt remains recorded.
The local Codex MCP registration and controller paths point to the new layout.
The existing single twenty-minute automation remains **paused**.

Private receipts include `app-source.json`, `app-destination.json`,
`raw-sources-transfer.json`, `raw-sources-cutover.json`, `git-preservation.json`,
`worktree-retirements.json`, `held-repo-consolidation.json`, `build-metadata.json`,
`obsolete-build-removals.json`, `archived-build-pruning.json`,
`evidence-moves.json`, `evidence-e-transfers.json`, `final-evidence-layout.json`,
`loose-evidence-transfers.json`, `helper-deduplication.json`,
`python-entrypoint-regeneration.json`, `control-source.*`, `control-installed.*`
and `file-actions.jsonl`. They contain the exact per-file mappings and operation
details; public Git contains this summary only. Interrupted attempts are retained.

## Completed owner-profile cutover

The owner closed Renulus and explicitly requested completion. App/backend absence
was verified before copying. The complete profile contained **14,993 files** and
**26,550,364,321 bytes**, larger than the earlier snapshot because the owner app
had remained in use. Source and destination inventory SHA256 identities matched:
`a5b08a53dbc39e33712353da9750e4f0e204925f136654434a8a19e447a6f7e3`.

One protected subscription record was present; the retrieval-key record was
absent. The existing record was decrypted/re-encrypted locally in memory for
the C: resolved path, with exact plaintext equality checked. Only ciphertext
rollback material was retained privately; no plaintext credentials were logged
or written. Owner/SYSTEM/Administrators access restrictions were verified.

The actual packaged app opened the migrated owner profile twice and reached
Today with authenticated local API readiness. Both normal quits completed.
All **62 table counts** and content digests for saved learning, Memory, Cases
and Library revision records remained unchanged; SQLite integrity, configured
connections and exact selected provider/model settings passed. No provider
generation, model refresh, imports, synthetic content or account resets were
performed. These checks do not re-establish live provider availability.

The ordinary startups also compacted/replaced derived search-index files. The
post-lifecycle inventory is **7,413 files / 1,792,755,283 bytes**. Comparison with
the verified copy shows that **all 7,339 Library files and all 20 helper files
are byte-for-byte unchanged**. Removed paths were exclusively derived indexes:
24,953,058,334 bytes of old Lance search-index/data/version files and 164,447
bytes of the previous learner-memory generation. Current index files remain
(195,581,104 bytes); canonical records retain the checks above. Most removed
bytes were old full-text index files within the same Lance generation. The
existing app implements Lance history compaction and rebuilds its derived
Memory index on restart. No cleanup script deleted files from the migrated
profile. This maintenance does not claim a new retrieval/provider test.

Only after those checks passed were the old physical profile and installation
copies removed. Their old paths are compatibility junctions. The desktop
shortcut and `C:/Renulus/Start-Renulus.cmd` select the C: app/profile; executable
and ASAR hashes still match the accepted product. The app/backend are closed
after validation, and the normal launcher is ready for the owner.

Final private receipts: `owner-shutdown-confirmation.json`,
`learning-profile-{source,destination,transfer,cutover}.json`,
`protected-profile-rebinding.json`, `profile-before-open.json`,
`owner-profile-lifecycle.json`, `profile-after-reopen.json`,
`learning-profile-after-lifecycle.json`, `profile-lifecycle-file-delta.json`,
`learning-profile-acl.json` and `final-retirement.json`. The transfer receipt
records the state at initial copy; cutover/final-retirement receipts establish
later removal and completion. Failed attempts and prior snapshots remain.

Issue #22 is complete. Issue #21's physical speech/display observations and the
corresponding product acceptance qualification remain separate and open.
