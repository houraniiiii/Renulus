# Learn, Cases and Memory acceptance at fdc2356d

Bounded audit of GitHub issues #5, #7 and #9 on isolated
branch `build/learner-acceptance`, worktree `Renulus-wt-learner-acceptance`,
based on `fdc2356dbd17757101927ba9b07bafc00847622f`. The issue descriptions,
implementation comments, README, project brief, workspace rules and current
module code/evidence were read before changes. The parent shared development
profile was not accessed.

## Material findings and corrections

Learn had no guard on an outstanding thread resume. An older GET could restore
content after New study, successful deletion or a newer selected thread. The
renderer now cancels pending resume requests and checks a view generation,
component lifetime and completed deletions before accepting their responses.
The controlled responses deliberately ignore cancellation, so the proof also
checks the state guard. Successful deletion cannot restore the removed thread
through a stale list/resume response during that mounted session.

Learn also treated SSE EOF without a terminal event as normal completion. Stop
before a new thread finished reloading left its question empty and could lose
the binding used by a deliberate retry. The renderer now identifies an
interrupted stream, retains the question and the thread ID from `started`,
cancels unfinished runs and reloads canonical thread/run state after Stop or
transport failure. If that state shows the answer committed, it displays the
stored answer, removes the partial/error/retry draft and reports Complete. It
does not start another generation to recover a lost completed event. If the
history reload fails, the known canonical thread ID remains available to the
next deliberate request. A failed resume has its own error/retry action that
reloads the same thread. Case branches never enter this durable reconciliation.

The backend cancellation path previously called the adapter before recording
local cancellation. An adapter exception turned a cancelled explanation into
an error state. Local cancellation is now recorded first; adapter cancellation
is bounded to two seconds and its failure body is neither exposed nor logged.
The same helper handles request cancellation. The existing completed-wins
semantics remain in place. The existing cancellation proof was expanded with
an adapter-failure variant instead of adding a redundant test family.

Six renderer reproductions failed before the lifecycle correction, covering
three stale resume outcomes, unterminated transport, a lost completed event
and Stop. The adapter-failure cancellation variant also failed before the
backend change. All pass after the corrections; the final renderer proof also
covers retry of a failed thread load without any generation request.

## Observed retention and learner flows

The new integrated API proofs use the real FastAPI routes, SQLite records,
Cases handoff guards, Memory reference outbox and installed content catalogue.
Their provider is synthetic. Background lifespan workers are deliberately not
started in these three proofs; the actual Memory outbox is processed explicitly.
No CPU helper inference is enabled, and public sockets are blocked.

| Flow | Observed behavior | Scope of the evidence |
| --- | --- | --- |
| Saved daily case to Learn, failed and successful answers | Handoff retains temporary scope. Forged study promotion is refused. The saved canonical snapshot is byte-for-byte unchanged until explicit Save; the live answer can be returned to Cases. | Real integrated API, SQLite and retention guards; synthetic generation. |
| Restart and explicit Save of that follow-up | Restart restores only the earlier saved snapshot. Save then retains the permitted live discussion, and the next restart resumes it. Delete removes both saved sentinels from app-profile files. | Real API, canonical state, export projection and file inventory. |
| Case exclusion from learner memory | Failed/successful case explanations produce no study threads, learning evidence, memory jobs or facts. Unsaved derivatives are absent from export and profile files. Processing the real outbox does not capture them. | Real producer/consumer classification and persistence boundary. |
| Ordinary study to automatic memory | A completed T21 study produces one reference-only capture and one activity fact, `I explored T21 in Explain.` Replaying the completed request does not add another answer, capture or fact. | Real Learn evidence, Memory outbox and canonical capture. This is an activity observation, not a mastery claim. |
| Memory correction, history removal and deletion | Revision-guarded correction succeeds without helpers; history can be inspected/removed; deletion reports cleanup complete, remains suppressed after another outbox scan/restart, and its synthetic fact text is absent from profile files. The ordinary study thread remains resumable. | Canonical/physical SQLite and no-helper cleanup behavior. This lane does not claim a new Mem0/Qdrant inference proof. |
| Staged teaching across two installed topics | The first narrative and revealed second stage match their installed pinned versions. Reveal/close neither saves a case nor creates learning evidence. | Actual installed Content/Cases producer rather than a substituted teaching catalogue. |
| Existing Cases and Memory renderer flows | Module suites cover explicit Save/discard/handoffs, late response guards, attachment review and scope exclusions, and Memory CRUD/conflict/recall states. | Real React controls/transport with controlled API responses, not native or live-provider proof. |

The earlier actual Mem0 OSS/Qdrant/FastEmbed evidence is in
[MEMORY.md](MEMORY.md). Actual temporary attachment extraction and its native
limits are in [cases-evidence.md](cases-evidence.md). Neither was repeated here.
Study activity and reviewed-assessment metadata are the present automatic
producers; this audit does not claim that arbitrary answer text automatically
becomes reviewed general learning facts.

## Closure recommendations

| Ticket | Recommendation | Concrete remaining acceptance boundary |
| --- | --- | --- |
| #5 — Ask, explain, cancel and resume | Hold full closure; integrate this Learn handoff. Local persistence, volatile exclusions, failure retention and corrected cancel/retry/reconciliation behavior have evidence. | An authorised live approved-subscription Explain journey, including the direct/guided and connection-failure/cancel outcome, is still absent from the current module/runtime evidence. |
| #7 — Daily and staged cases | Retention, saved restart, guarded handoffs and installed stages pass local acceptance. Hold full closure for the shared disclosure fix and generation gate. | `apps/desktop/src/shell/App.tsx:47` still unconditionally says **Temporary case · not saved** during temporary context. After Save, the actual Cases page correctly says **Saved snapshot** and explains unsaved follow-ups. The parent owns correcting the shell wording while preserving temporary processing scope. Live daily discussion shares the approved-subscription gate. |
| #9 — Capture and correct learner memory | Canonical activity capture/idempotency, correction/history deletion, case exclusion and retryable helper failure pass local acceptance. Hold full closure of the general-point generation claim. | Earlier selected-engine proof used a synthetic extraction response; an authorised general-learning-point extraction through the approved live provider remains unverified. No case transcript may be used to establish that proof. |

The current [runtime evidence](runtime-evidence.md) records deliberate sign-in
start/cancel and both providers remaining disconnected, with no account exchange
or inference. This audit reads that public evidence, not host credentials or
current connection state. [Execution rules](EXECUTION.md) say: “Do not close a
ticket on a mock, typecheck or prototype when a real producer remains absent.”
The recommendations distinguish implemented application behavior from that
remaining shared producer proof. No ticket was closed by this lane.

Read-only Git inspection of parent snapshot
`35f874b52eb86fe71aa94949b0c8c69b482c8f18` also retained the same shell
wording; this finding is not confined to the older audit baseline. No parent
working file or runtime profile was read for that check.

The shell is a confirmed misleading disclosure, not evidence that Save failed.
Image interpretation remains explicitly unsupported; existing attachment cold
startup/native diagnostics and signed/clean-machine delivery remain with their
owners. This audit does not broaden these tickets into new platform work.

## Verification and handoff

The final backend command passed 141 checks with the existing TestClient
deprecation warning. The two opt-in actual-engine files were deliberately
excluded; they are not claimed as passing in this audit.

~~~powershell
$env:PYTHONPATH=(Join-Path (Get-Location) 'runtime')
$env:PYTHONDONTWRITEBYTECODE='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
& ../Renulus-wt-integration/.venv/Scripts/python.exe -m pytest tests/learn tests/cases tests/memory tests/integration/test_case_learn_handoff.py --ignore=tests/memory/test_mem0_real.py --ignore=tests/cases/test_offline_attachment_flow.py -q --basetemp .local/runtime/learner-acceptance/pytest --tb=short
~~~

Final renderer verification passed 77 checks across seven files, including
the seven lifecycle proofs. Full desktop typecheck and renderer production
build passed. The existing preview dynamic-import analysis warning remains;
the build transformed 1,947 modules and finished in 2.08 seconds. Working and
staged whitespace checks passed at handoff. These establish renderer/API
behavior, not a native desktop or live provider journey.
The ignored local verification wrapper imports the existing Memory preview
configuration, selects Learn/Cases/Memory tests with one worker and writes
cache/build output under `.local/runtime/learner-acceptance`. It changes no
shared build files or dependencies.

~~~powershell
node ../Renulus-wt-integration/apps/desktop/node_modules/vitest/vitest.mjs run --config .local/runtime/learner-acceptance/verification.config.mjs --configLoader runner --reporter=dot
node apps/desktop/src/modules/memory/typecheck.mjs
node ../Renulus-wt-integration/apps/desktop/node_modules/vite/bin/vite.js build --config .local/runtime/learner-acceptance/verification.config.mjs --configLoader runner
git diff --check
~~~

Owned edits are the Learn renderer/service, its focused lifecycle and retention
proofs, the expanded existing Learn cancellation proof, and this evidence.
Cases/Memory implementation, schema, shared shell/platform/runtime/recovery and
the parent profile are unchanged. No live provider, helper download, training,
credentials, private correspondence, patient input or external original was
read, copied or used.
