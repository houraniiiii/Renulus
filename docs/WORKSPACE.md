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
| `assets/brand/` | The selected Renulus logo and icon exports, with provenance |
| `references/` | A small, dated reference shelf, including inherited taxonomy labels |
| `scripts/` | Local launcher and workspace checks; no application architecture |
| `.agents/`, `.claude/`, `.codex/` | Portable design skills and reviewed project configuration |
| `.local/` | Ignored machine-specific preview pointer and verification evidence |

Future research, planning and prototyping should build on the confirmed brief.
The cleanup does not adopt an application framework, curriculum, model, hosting
strategy or feature roadmap. Create implementation folders when work needs them.

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

Keep local runtime state under `.local/` and use explicit file lists for commits.
No credentials or private application state are needed to work on product
documents, design assets or synthetic examples.

Run `python scripts/check_workspace.py` for repository, structure, reference and
link checks. It checks workspace organisation only; it is not an app or clinical
evaluation.
