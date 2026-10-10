# H00 handoff reconciliation

2026-10-10. **H00 is a consumed current-product prerequisite at
`fa3b590cd40de145c198a64168aa46b82384e2bc`. Do not implement it again under H12.**
This is a later documentation revision after the six-wave research, not an
OpenCode implementation or a Windows-release acceptance.

## Independently inspected source and provenance

Read the local Git commit and diff on `codex/design-c-integration`. It changes
only the shared retrieval helper, the saved-generation caller and its tests:
96 insertions and 14 deletions in three files. Source can be reproduced with
`git show fa3b590cd40de145c198a64168aa46b82384e2bc`.

- Shared retrieval requires an explicit callable guard. Each retrieval query
  attempt is guarded before I/O and in `finally` afterward, including failures.
  This describes the guarded attempt, not an assertion that a new guard runs
  between every internal await in an awaitable-returning implementation.
- The saved caller re-reads the actual job in a short canonical transaction and
  calls its existing `_check` with the execution token. That check covers active
  state, execution identity, policy, Nightly authority, route, context/settings
  and pinned sources. No transaction is held over retrieval I/O.
- The legacy caller passes its real `guard_run`. There is no no-op compatibility
  method or replacement execution authority. Publication, checkpoint and
  shorter-set implementation are unchanged by this diff.
- The missing-Nightly-owner fixture now explicitly removes that registered
  capability for its intended test, instead of relying on outdated assembly.

The earlier documentation handoff is local commit
`75b4b503085b3592d89f5114b282073847b2159d`. Its canonical manifest at
`docs/implementation/opencode-plan-snapshot/manifest.json` has 99 file entries;
the inspected SHA-256 matches
`d611c558d43fcaa4a8060e3ff9d30a235a17cdab4cc80e81683b15ec8e7b0c41`.
That snapshot and the canonical checkout were not modified here. Older decisions
and research remain dated evidence; this local planning revision is subsequent
to the captured snapshot.

## Inspected test receipts

Parsed existing JUnit files under `C:/Renulus/scratch/design-c/h00`, inspecting
test identities and outcomes and hashing the raw files. Their association with
the repair was supplied by the integration owner; this chat inspected the source
and receipts but did not rerun the suites or obtain new App acceptance.

| Receipt | Observed result | SHA-256 |
| --- | --- | --- |
| `red02.xml` | One public generation-route failure retained | `356c6c24d246e9651093d6a57dda2a1caf4e1c4a6634fedfb262d97b8f5e2bcd` |
| `green01.xml` | 13 passed | `a376da7686d79bd52d2eea61a201cae56d3dc29f2be0081c4e1942d7662436ef` |
| `affected-full01.xml` | 160 passed, one missing-owner fixture failed | `38ad8bef686ef0942605fae91784c56259d5ddb15ba663521a757039753e1054` |
| `nightly-fixture01.xml` | The corrected missing-owner case passed | `7ed7818b91e85ece3f862d1dacc05832ba9cb4233abf1a99c8c60136cd152c0a` |
| `connected-ui.xml` | One suite-level failure, two skipped flow cases | `d7eea3e4c9428a1ae1fc8b50ab45f1af32cf3eb057646a087c5ca2ecb1346aeb` |
| `connected-ui02.xml` | Two flow cases passed; one suite-level failure remains | `f7a95416cbbf4cf45cd14a57062da4c31630e1794b1f7feb7b8d835f7ef69b7e` |

The corrected case has the same class/name identity as the sole failure in the
161-case affected inventory. The union contains **161 distinct affected cases
with passing evidence across the 160+1 runs**. This is not one fully green
affected-suite run, and the focused 13 are not added to that total. The inspected
App receipts do not establish a fully green App producer/consumer rerun; the
integration owner's final rerun evidence remains pending.

## Planning effect

- H00 is consumed. Retain its original scope and failing evidence for provenance.
  H12 must start from a current canonical baseline containing this repair,
  preserve its caller-specific authority across the new boundary and test that
  adaptation. Do not reimplement the prerequisite or mix the old research source
  into the newer integration branch.
- H01 and H24 are the remaining independent initial planned slices. H03, H05,
  H06 and H24 retain their open defect ownership; H00 does not close them.
- Temporary runtime isolation belongs to H21 with the H01 host substrate; H06
  is saved-history migration and receipt retirement.
- OpenCode migration is still unimplemented here. Default Windows delivery
  remains H20. Full App closeout and native/account acceptance are separate.

Read-only checks used `git show`, `git status`, SHA-256, Python XML parsing and
AST/source inspection. No product code, snapshot manifest, canonical working
file, profile, service or provider was changed by this reconciliation.

## Subsequent final-closeout and implementation note — October 10, 2026

The complete dated reconciliation above is copied intact from the a11f research
worktree. Its preliminary App receipts and pending-final-evidence statements
remain historical. The later canonical [Design C handoff](../../implementation/DESIGN_C_OPENCODE_HANDOFF.md#final-closeout-evidence-and-review-launch)
records the subsequent `connected-ui03.xml` rerun: **2/2 full App producer
journeys passed with clean owned shutdown**. It also retains the earlier failed
receipts and 161 unique affected cases across 160+1 runs, without converting
those receipts into a single full-green affected-suite claim.

Final handoff commit `c2bd896420fb88f76d63ca576414dbbba182f4c2` preserves product revision
`7a6b4955ff560d6694835e661d3745c545448ac6`. Its bounded Design C closeout is
complete. The immutable 99-file snapshot in `75b4b503` and its manifest remain
unchanged; this note is a later reconciliation, not a rewritten snapshot.
DC21's final default Windows release remains deferred to H20; neither is passed.

The owner's [subsequent implementation instruction](../../planning/2026-10-04-user-answers.md#october-10-first-opencode-foundation-implementation-authorisation)
authorises the first foundation batch from `c2bd8964` using the existing planned
public test seams. The integration task selected H01/H24; their subsequent
[implementation handoff](../../implementation/OPENCODE_FOUNDATIONS_HANDOFF.md)
records completed local host/worker acceptance. H02 is planned next, and other
uncompleted tickets remain planned. No tracker publication is required. H00
remains consumed; H05 lineage, H06/H18 receipt retirement and H03 authentication
remain open. H24 settlement is closed by its own later implementation evidence.

## Manifest hash correction from foundation integration

The preserved earlier note reports `d611c558...` as the manifest SHA-256.
Fresh byte-level verification against both `75b4b503` and the final Design C
baseline instead establishes
`446ccf39b0d86afca914b36b43973759f14384771452dbfd2aaef39701901938`
for the 44,937-byte committed manifest and the current checkout. All 99 captured
Git blobs match that manifest's `committed_bytes` and `committed_sha256` values.
The earlier hash is not accepted as current manifest evidence; its origin is
not established by this check. The snapshot itself has not been modified.
Receipt: `C:/Renulus/scratch/oc-foundations/parent/snapshot-verification.json`.
