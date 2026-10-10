# OpenCode planning snapshot for the Design C handoff

This is a deliberate documentation handoff, captured from the **working files**
of `C:/Users/karol/.codex/worktrees/a11f/repo`, not a merge of its older source.
The planning task is `01a123f8-2409-7870-b688-57e632054d72`; its HEAD was
`528025ff0b22477c12ee1512e0e7d15297a6e888`. The [manifest](manifest.json) records
the exact UTC time, uncommitted status, source/destination paths, byte sizes and
SHA-256 of all 99 captured files (1,104,430 bytes). Source files were checked
again before copying. The planning worktree was not modified or staged.

The complete captured version is documentation commit
`75b4b503085b3592d89f5114b282073847b2159d`. Later canonical H00/H20 and findings
updates are deliberate reconciliation, not edits to that historical snapshot;
use `git show 75b4b503:<destination>` with the manifest's committed hashes to
recover the captured documents.

New planning/research documents are preserved at their corresponding `docs/`
paths, including the [integration plan](../../planning/OPENCODE_V2_INTEGRATION_PLAN.md),
[three specs and H tickets](../../planning/opencode-v2/README.md), and
[findings ledger](../../research/2026-10-10-opencode-integration/findings-disposition.md).
The older working DECISIONS and user-answer files are stored under
`source-documents/` here solely as source evidence. They do not replace their
newer canonical counterparts. Research probe code is preserved as research,
not executed or installed by this handoff.

The captured files retain their original draft labels and content. The manifest
records exact source bytes and committed bytes separately for existing Git
line-ending normalization. Original EOF blank lines are deliberately retained.
Apply
these current reconciliation rules when reading them:

- The owner selected OpenCode v2 for the next migration. This task authorizes
  Design C UI closeout, H00's existing-generation repair and documentation only;
  it does not authorize implementing OpenCode or publishing the issue drafts.
- H00 is repaired in the Design C baseline by `fa3b590c`. Its commit/evidence in
  the integration handoff supersedes the snapshot's unchecked prerequisite;
  H12 must consume it rather than implement the same repair twice.
- The Temporary storage row of the captured findings ledger predates its own
  final split: **H21 (+H01 substrate)** owns volatile graphs, spills and Save;
  **H06** owns saved conversation migration and deleted saved receipts.
- H05 lineage/recapture, H06/H18 deleted receipt payloads, H24 actual worker
  settlement and H03 authentication availability remain open. The current
  single-store recovery evidence does not satisfy those or OpenCode's paired
  store acceptance.
- DC21's original final default release is **deferred to H20**. Retain Design C
  requirements as migration regression obligations, not false passed tickets.

Future planning edits should explicitly reconcile against this captured
manifest and the final Design C product commit. No source from the planning
worktree was merged; no execution/configuration/transcript authority was added.
