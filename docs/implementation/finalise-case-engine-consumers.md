# Changed Cases engine consumers — October 5, 2026

The single authorized run at product freeze
`035ca7bd07337c65266c17f9b762ca1f97238e11` passed both changed PDF/PNG consumers:
exit 0, two passing JUnit cases, six passing setup/call/teardown records,
`complete=true`, `source_unchanged=true`, `accepted_stage_pass=true`. Every source
check passed; collection errors, unexpected modules and guard violations are
empty. This is source-running engine/Cases API evidence with synthetic inputs.

The exact two identities were:

```text
tests/cases/test_offline_attachment_flow.py::test_actual_proven_byte_extractor_through_case_preview_apply_save_delete[pdf]
tests/cases/test_offline_attachment_flow.py::test_actual_proven_byte_extractor_through_case_preview_apply_save_delete[png]
```

Their genuinely new assertions cover original metadata/byte count/SHA256 and
exact View bytes before Save, canonical Save, metadata and exact bytes after
close/reopen, and HTTP 410 plus deletion of canonical parts. Views require
`Cache-Control: no-store`. The unchanged third native-stream no-write identity
and all other successful IDs were excluded. Historical 19-ID evidence remains
4 historical transfers + 7 r1 passes + 8 r3 passes; this two-ID slice does not
inflate that reconciliation or create a full sweep. Old failed receipts and
accepted r3 flags remain unchanged. There was no replay or product/test edit.

Parent released `engine-case-consumers-035ca7bd-20261005`. The immediate metadata
check at 21:15:17.635869 UTC measured 3,947,936 KiB available physical memory,
above the 2 GiB floor of 2,097,152 KiB. Observer session `34887` ran the prepared
wrapper once with `--selection changed-cases-two`, fresh
`.local/case-engine-consumers/r1` receipts and `C:/rn-ec1-1005` state/caches.
Pytest reported 2 passed / 7 dependency warnings in 167.38 seconds. The wrapper
finalized at 21:18:16.509112 UTC; actual observer exit 0 followed at
21:18:18.837213 UTC. All times here are October 5, 2026 UTC.

Runner `39548` was created at 21:15:18.960521 UTC, launcher `40944` at
21:15:18.878272 UTC and observer `39068` at 21:15:17.842461 UTC. Creation
identities/command lines and the actual runner's FILETIME are durable. All three
owned PIDs and children were physically absent at 21:18:42.025370 UTC; the
serial slot was released. Parent owns installation and worktree retirement.

HEAD, production, tests/runner, ten source Git objects, fifteen producer/test/
helper/recorder file hashes and the helper manifest were unchanged through the
guarded finalizer. Runtime object was `834fe2d4b843ed2e904a30e0b6f3cec87d67da1c`;
tests object was `ead52cf329afe9c3704afbdd37c8cde09e09604c`. Independent
reconciliation matched raw JUnit/outcomes and all three unique passing phases
for each ID, and checked all 95 module sources. The recorder retains the exact
adopted Hermes Mem0 module exception. The r3 mutation/subprocess/NUL audit
policy is unchanged; only bare Windows `nul` writable open has its existing
exception. Strict guards remained active during tests and finalization.

Pinned public Python 3.14.4 and all thirteen package pins matched. Interpreter:
`C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe`.
Helpers were read from existing public-only `C:/rn-ef3-1005/profile/helpers`,
whose origin is
`C:/Renulus-native-delivery/desktop-20261005/environment/helper-assets-3ff9b0d6`.
Manifest SHA256: `7d5375bf81d4c4dc3c5a9b6a1304d99286f465998a4e23ecc4da5a8103dcfa7d`.
The production validator verified assets; there were no extra model copies or
preparation warmups. Two CPU threads and the 12 GiB disk reserve were enforced.
Private profiles, parent integration inputs/preview ports, held E inputs,
external traffic/DNS and ordinary outside writes stayed denied by the inherited
Python-level guard. No provider, native-application or compression actions ran.

Terminal receipt SHA256 values:

| Receipt | SHA256 |
| --- | --- |
| `r1/results.xml` | `db1f8ff12543edc1251ab60639962e357f6733721be0f41449a747466269a732` |
| `r1/result.json` | `e9745f10ed8d0c517fa440a92ad9017770083dc3c0cdac7c16cf03422f370681` |
| `r1/events.jsonl` | `b8dcc62ea612f04ae3fd2772e1c99ca0f509183688d3e03884736d3f8c05bc6c` |
| `r1-exit.json` | `8fe47d503716a8a53a1b1e7fe67646ef49e645ebee867a52c8a83ac5188ca205` |
| `r1-terminal.log` | `84d7c790dafc55398524b7d82f2838090b898bfc6c2814a1ec2ed55891d91e5d` |
| `r1-slot-release.json` | `4ff72c56467f03990dd2db71a7b645137861d076e2f090d4c7b65b1d80bc53cc` |
| `r1-reconciliation.json` | `fc5615c86b0dc4bb1d58052386aa86b0022c009e5c3fe3a1e30bc812f5352f17` |

Original run snapshots retain wrapper SHA256
`3c733306bb695c3b56147069bd107464dd4bfde30e657a8c42ff2d63f05f7ede`, plan
SHA256 `8aa584cac244fea10058e7b8f6ca52f54214d28fbbe439e440348ceff8f7272e`, and
observer SHA256 `e41647453f687428750e3be801913fdd168977ae24c970c0e3c0c55d78687db6`.
The original held readiness record remains preparation evidence.

All 26 ignored public wrapper/receipt files (124,484 bytes) are preserved under
`C:/rn-finalise-20261005/preserved-lanes/case-engine-consumers/.local/case-engine-consumers`.
Every original, after-copy original and preserved copy hash matches. Manifest:
`C:/rn-finalise-20261005/preserved-lanes/case-engine-consumers/hash-manifest-20261005T212211Z.json`,
SHA256 `7b77a195d6eabc388fa5172b04d30cb23ea1a5294a06840eb7bce92bf6688d15`.
Only public metadata/wrappers were copied; payloads/profiles/model assets were
excluded. This report is the sole tracked change. Later documentation
integration does not reinterpret terminal acceptance anchored to `035ca7bd`.
