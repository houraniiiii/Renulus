# Working in Renulus

Renulus now has its own repository, `houraniiiii/Renulus`, and its own independent
Git history. The active branch is `main`; `origin` is the sole remote. No inherited
MVP branches, recovery remotes, sparse-checkout rules or old Git checkpoints are
part of this repository.

## What belongs here

| Location | Purpose |
| --- | --- |
| `README.md` | Entry point and current project status |
| `docs/` | Confirmed product facts, decisions, source boundaries and workspace/tool guidance |
| `docs/planning/` | User answers, staged implementation, architecture, parallel-work rules and review record |
| `docs/research/` | Bounded, dated investigations supporting those decisions |
| `assets/brand/` | The selected Renulus logo and icon exports, with provenance |
| `references/` | A small, dated reference shelf, including inherited taxonomy labels |
| `scripts/` | Local launcher and workspace checks; no application architecture |
| `.agents/`, `.claude/`, `.codex/` | Portable design skills and reviewed project configuration |
| `.local/` | Ignored machine-specific pointers, per-profile development state, public-source research caches and verification evidence |

The recorded rounds 1–3 settle the product direction, interaction rules and
subscription/model constraints. The implementation baseline adopts Hermes's
Python runtime and suitable existing Electron/React desktop foundation. The
user subsequently approved Mem0 OSS, Docling/HybridChunker, FastEmbed and
LanceDB OSS behind Hermes, with canonical SQLite records. Their selected roles
and remaining checks are recorded in the
[stack evidence](research/2026-10-04-starting-stack-evidence.md). The
[stage plan](planning/IMPLEMENTATION_PLAN.md), [module ownership](planning/ARCHITECTURE.md)
and [worktree rules](planning/PARALLEL_WORK.md) govern future implementation.
Authentication, native packaging and behaviour require real verification in
those stages. Create implementation folders when work needs them; planning has
not imported Hermes or installed the selected stack.

`docs/SOURCES.md` is the single current development source register, including
current editions, access levels and developer/user acquisition methods. Planning
and module work reference its source IDs instead of maintaining competing lists.
Optional web/literature API keys are confirmed retrieval-tool configuration;
they are separate from generative subscriptions and remain explicitly enabled.

## Where the old work lives

The inherited copy is preserved as a separate local archive. It contains its
original code, uncommitted changes, old documentation, Git history, native state
and installed dependencies. Its dated instructions and earlier clinical MVP
scope do not govern this workspace. See [cleanup record](CLEANUP.md).

The former `nephro-agent` project remains a separate project and repository.
Do not add it as an upstream remote to Renulus. Historical provenance is recorded
as documentation, not as a live repository connection.

`Start-Renulus.cmd` and the desktop shortcut can open the archived implementation
for reference through a local, ignored pointer. That inherited UI is not the new
learning product. This is optional and is not a dependency of Renulus itself.
A fresh clone without that local archive shows a clear launcher message.

After moving the clean workspace again, rerun `scripts/install-desktop-shortcut.ps1`
with `-PreviousWorkspaceRoot` set to its previous absolute folder. This permits
repairing that owned shortcut while preserving unrelated shortcuts.

## Keep the environment clean

Use the documented reference shelf before browsing the archive. Preserve useful
material there until a concrete task needs it, then import a reviewed subset with
provenance and applicable rights. Do not copy historical datasets, outputs,
dependency trees, private emails or private records into active source folders.

Collect source originals outside the checkout under
`%USERPROFILE%\Documents\Renulus-data`, using source IDs from the register.
The current machine's folder is recorded in ignored `.local/data-location.txt`.
See [local collection and storage](SOURCES.md#local-collection-and-storage) for
the ERA manual folder, acquisition notes and the proposed installed-app location.
Creating collection folders does not implement import or index any files.

Keep development runtime state under `.local/runtime/<profile>/` and use explicit file lists for commits.
No credentials or private application state are needed to work on product
documents, design assets or synthetic examples.

Run `python scripts/check_workspace.py` for repository, structure, reference and
link checks. It checks workspace organisation only; it is not an app or clinical
evaluation.
