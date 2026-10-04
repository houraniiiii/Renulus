# Workspace cleanup — 4 October 2026

Renulus has a clean, independent repository and workspace. This cleanup separates
the new nephrology learning product from the inherited clinical MVP and model
research. It does not select an architecture, design a new interface or implement
product features.

## Retained in the active project

- The confirmed product brief, decisions and source-use boundaries.
- The selected C — Renal flow logo board, its generation prompts and existing
  raster/icon exports.
- Reviewed Impeccable and Interface Design files, portable project configuration
  and their third-party notices. Machine-specific trust and credentials were not
  imported.
- A small dated reference shelf and the canonical taxonomy pair: 27 topics and
  199 subtopics. These are historical labels, not an approved curriculum.
- Workspace checks and an optional launcher for the archived implementation.

The inherited flat taxonomy catalog was not retained here: 89 rows have labels
that differ from the canonical split pair. It remains available in the archive.

## Archived intact

The copied baseline is preserved locally outside the active workspaces at:

```text
%USERPROFILE%/Documents/t3-archives/Renulus/inherited-mvp-20261004
```

It retains its Git history, sparse-checkout selection, uncommitted work, inherited
code, plans, research material, build resources and installed environments. This
is a local preservation archive, not part of the public Renulus repository. No
unclassified data or private/native state was opened to perform this cleanup.

Its preserved checkpoint is `574023baa994b1896efd0ba06c5f66523613dd4a` on
`t3/nephro-agent-recovered-20261001`. The separately linked historical worktree
remains available, with its Git link repaired after relocation.

Windows holds the former workspace directory open for this running session. All
31 top-level entries were moved into the archive; the remaining old directory is
empty and hidden, with no Git metadata or source files. It can be removed after
the session releases its directory handle.

The separate original `nephro-agent` workspace and companion repositories remain
unchanged. Their source trees and remotes have not been imported into Renulus.

## Repository separation

The independent bootstrap repository was renamed from `nephro-agent-os` to
`Renulus`; its initial commit,
`8917ce4ea8d12b43aef1b2df797422a45b4330d7`, was preserved. The new active
workspace has only `origin`, pointing to `houraniiiii/Renulus`. It does not carry
the old MVP's recovery branches or remotes.

The existing T3 project is renamed and rooted in Renulus while keeping its
conversation history. Historical threads with a separate worktree retain that
worktree; their old implementation is not the active Renulus source tree.

## Desktop access and local evidence

The Renulus desktop shortcut targets the clean workspace launcher and selected
icon. An ignored `.local/legacy-preview.json` points to the archive. The launcher
opens the inherited app for reference; it is not a prototype of the new learning
product. A fresh clone without the local archive receives a clear message.

Existing application data stays at its previous location. Launcher verification
uses a separate synthetic test directory rather than private application state.
After relocation, the new wrapper passed native startup, rendered-name/workspace,
owned-backend, repeated-launch and clean-shutdown checks. The missing-archive
path returned a clear noninteractive error, and shortcut metadata matched the
new root, wrapper and selected icon. These checks validate reference access only.
Relocated Python activation and package-manager wrappers may still refer to the
old path; the archived launcher invokes its Python interpreter directly. Seven
generated Node workspace junctions also retain their original absolute targets.
Rebuilding that historical development environment needs a separate path review;
the clean Renulus project does not depend on it.

Run `python scripts/check_workspace.py` to check repository separation, retained
taxonomy, required files, ignore rules and local documentation links. It does not
evaluate an app, model, educational effectiveness or clinical accuracy.

Machine-specific preservation and verification receipts are kept outside Git in
the local archive parent and `.local/`.
