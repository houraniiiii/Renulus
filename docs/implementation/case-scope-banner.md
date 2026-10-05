# Case snapshot disclosure and local acceptance

October 5, 2026, UTC. This bounded follow-up starts at
`14bb101f6308b2f1eae681ac7b5124fddd716bc3` on `build/case-scope-banner`,
in the isolated `Renulus-wt-case-scope-banner` worktree. The granted write
lease covers `apps/desktop/src/shell/App.tsx`, its focused banner test and this
evidence. The mandatory project/workspace documents, Cases state, navigation
and earlier acceptance evidence were read before the change.

## Corrected disclosure

The shell previously displayed **Temporary case · not saved** after the
doctor explicitly saved a snapshot. It also hid the banner for `saved-case`
scope, although further discussion is temporary. Scope alone does not describe
the latest saved/dirty state. The Cases page already owns that state and its
Save result; its behavior remains the source of the current snapshot cue.

| Application scope | Shell disclosure | Meaning |
| --- | --- | --- |
| `temporary-case` | Temporary case context · Only explicitly saved snapshots are kept. New changes require Save. | Temporary processing can coexist with an earlier explicitly saved snapshot. |
| `saved-case` | Saved case snapshot · New changes stay temporary until you Save again. | The saved scope does not imply that subsequent discussion was persisted. |
| `unclassified` | Unclassified context · not saved | Unclassified material remains volatile. |

Each guarded scope retains the **End temporary context** action and the
temporary footer cue. The existing navigation function performs the handoff
and explicit reset. Ordinary study has no scope banner. The patch introduces
no new request, polling, storage or snapshot state in the shell. The Flow
components, status role and existing responsive banner styles are reused.

## Controlled behavior proof

`scope-banner.test.tsx` mounts the real App, NavigationProvider, Cases page,
case hook and HTTP/SSE transport. Other destinations expose a small scope
probe so unrelated module resources do not participate. The local transport
returns synthetic responses; it rejects unexpected fixture requests.

The four focused reproductions failed against the original shell labels.
After correction they prove:

- A failed explicit Save retains the temporary case. A successful Save shows
  **Saved** and the Cases saved-snapshot notice, while the shell acknowledges
  the snapshot rule without claiming that the case was never saved.
  A later accepted discussion shows **Save changes** and the temporary-changes
  notice. Only the next explicit Save submits the new revision. No browser
  storage is written and the synthetic case text stays out of the URL.
- A reopened saved snapshot hands off from the real Cases control to Learn
  with `temporary-case` scope and its entity identity. An attempted study
  scope on Test navigation retains that temporary identity. End removes the
  banner and clears the volatile handoff; these transitions never call Save.
- A `saved-case` scope shows the snapshot/new-changes disclosure and temporary
  footer. A temporary branch retains the case identity and explicit End clears
  it. The label does not assert that all recent chat is saved.
- Unclassified context has its own label, retains its guard during Test
  navigation and resets only through explicit End.

The existing integrated backend acceptance proof was re-run at this base. It
uses actual FastAPI routes, canonical SQLite, Cases/Learn guards and installed
teaching content with a synthetic provider and external sockets blocked. It
checks saved-case error/success handoffs, unchanged saved bytes until Save,
restart, export/profile exclusion, deletion, memory exclusion and staged
reveals across two installed topics. This is application evidence; it does
not establish a live subscription response. See the broader integrated
[retention audit](learner-retention-acceptance.md) and earlier actual-engine
[Cases evidence](cases-evidence.md).

## Verification

The ignored wrapper under `.local/runtime/case-scope-banner/` reuses the
existing module verification configuration and the integration worktree
packages. All generated output is confined to this isolated worktree.

```powershell
node ../Renulus-wt-integration/apps/desktop/node_modules/vitest/vitest.mjs run --config .local/runtime/case-scope-banner/verification.config.mjs --configLoader runner --reporter=dot
# 29 passed across 5 files: focused banner, existing navigation and Cases tests.

& ../Renulus-wt-integration/.venv/Scripts/python.exe -m pytest tests/learn/test_retention_acceptance.py tests/cases/test_retention.py tests/cases/test_api.py -q --tb=short
# 36 passed in 23.09 seconds.

node apps/desktop/src/modules/memory/typecheck.mjs
node ../Renulus-wt-integration/apps/desktop/node_modules/vite/bin/vite.js build --config .local/runtime/case-scope-banner/verification.config.mjs --configLoader runner
& ../Renulus-wt-integration/.venv/Scripts/python.exe scripts/check_workspace.py
git diff --check
```

Typecheck, production renderer build, workspace and whitespace checks pass.
The existing dynamic-import warning in the reusable preview configuration
and the Starlette TestClient deprecation warning remain nonblocking. Neither
native packaging nor a new CPU-helper engine run is claimed.

## Ticket boundary

This follow-up resolves the shell disclosure blocker. Together with the prior
audit `bdfe6bfd2d6be2e663fb03bc843d5af269890f25`, integrated by the parent as
`e339aa29`, it supports closing **#7 for local retention/stages application
acceptance**. This supersedes the earlier audit recommendation to hold #7 for
the banner and shared generation gate. The user explicitly assigned the
remaining live DailyModel/approved-subscription proof to **#2/#5**.

Saved restart, explicit retention, volatile handoffs and installed stages have
local evidence. Live daily generation, native delivery and clinical accuracy
are outside this closure. This lane uses no provider, credentials, patient
record or parent development profile.
