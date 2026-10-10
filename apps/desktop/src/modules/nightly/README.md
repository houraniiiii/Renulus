# Nightly consumer seam

Settings mounts the named `NightlyPreferences` export from this directory.
Pass the shell's current `assistanceAllowed` policy so enabling/saving remains
unavailable during Test while turning Off is always reachable. `onSaved` receives
the canonical `{enabled, local_time, question_count, revision}` preference receipt.
It can refresh other consumers; it must not start generation.

Tests mounts `NightlyStatus`. `onPreferences()` opens the same Settings form.
`onOpenTest(selection)` receives the existing TestSelection with the exact saved
test and version IDs. `onReviewJob(id)` opens the existing GenerationPanel with
that job ID; its generation owner decides whether a retained set is recoverable.
Opening a status or a retained job does not create work or automatically accept
shorter questions. Every action remains optional until the parent mounts its
actual consumer.

Reads use `/nightly` and `/nightly/preferences`; writes use the approved
`PUT /nightly/preferences` body and neutral
`POST /nightly/jobs/{id}/cancel`. Idempotency-Key receipts live in React memory
for an exact explicit retry. Raw prompts and trusted scheduling metadata never
enter these requests. Safe statuses contain counts, state and typed references,
without generated questions or keys. The backend app-running scheduler alone
claims eligible days and calls saved_generation.

The visual reference is the reconciled C file `zV8JiWybVHP1UxJtLbZjEt`, Nightly
Off `83:7590` and On `83:7750`, preferences child `83:7879`. It is adapted to
Renulus's Source Sans 3, semantic paper/teal tokens and existing controls. The
confirmed 22:00/five defaults supersede prototype values. The frozen recovery
rule supersedes the prototype reopen promise; there is no invented Generate now
producer. Shell and brand assets remain owned by their existing components.

Validation on the exact dc-home worktree: TypeScript passed and 12 colocated
Vitest behavior checks passed. They cover approved defaults, duplicate prevention,
retained preference drafts/exact retry keys, revision conflicts, Test-time Off,
abort, saved-version identity/unavailability, neutral Stop/publication winner,
short-work review and read-only polling. Backend scheduler integration evidence
is in `tests/study/test_design_c_nightly.py` using real migrations, owners and
ProviderManager with synthetic adapters only.

Integrated Settings/Tests preferences, reopen pixels and actual JSON restore
checks are indexed in [EVIDENCE.md](EVIDENCE.md). The shared mounts and storage/
policy baseline were consumed through `837ea3d0`. These checks do not close DC19
or establish live model/content quality; the full saved-result/attempt consumer
journey remains a separate integration gate.
