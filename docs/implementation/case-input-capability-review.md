# Temporary case input and learning capability review

October 5, 2026, UTC. Isolated branch `build/case-input-capabilities` starts
from `b33ef0f5a60eb3061c498f65f9bc4036b7c61637`: parent `54cbeb6d` plus the
integrated saved-scope fix. Review used current contracts/source and existing
actual-engine evidence. No new source data, helper run, provider or parent
profile was used.

## Concrete correction

The real Cases page offered only **Explore in Learn**. Its hook hard-coded
`target: explain`, although Cases already provides guarded `generated-practice`
tickets and Test already consumes them. Sidebar Test navigation retains the
temporary classification but does not create a practice ticket or carry the
extracted case context. This left the supported case-to-practice route without
an application entry point.

**Practise from this case** now requests the existing generated-practice ticket
for the current revision. It opens Test with the returned temporary scope and
only `{case_handoff_id, case_id}`. The existing practice composer supplies a
separate editable instruction and requires a deliberate Generate action. No
case narrative, extracted text or unsent case question is copied into that
navigation payload or generation request. The backend resolves the current
case through its existing ticket guard. Saved and unsaved cases follow the
same volatile route; the Explain default and late-result guards remain intact.

Owned changes are confined to the Cases page, hook, existing handoff tests and
this evidence. Assessment, shared shell/platform, provider and engine sources
are unchanged. No schema, scheduler, dependency or parser was added.

## Final capability ledger

| Workflow | Current behavior and evidence | Remaining required work or limit |
| --- | --- | --- |
| Daily-case PDF/PNG/JPEG text input | Prepared helpers expose literal verified temporary extraction. Raw bytes become a RAM-only Docling/RapidOCR preview; the doctor reviews/edits and explicitly applies it. Existing actual-engine Cases proof passed all three selected-engine checks, including no-write/socket denial. | Text extraction only. OCR confidence remains unknown; numbers, units and tables require comparison with the user-owned original. |
| Extracted case text to Explain | Current Learn consumer obtains a revision-bound ticket and commits only the permitted completed answer into the live case. Integrated retention proof covers error/success and saved/unsaved snapshots. | Live DailyModel/approved-subscription generation remains #2/#5. No new live proof is claimed here. |
| Extracted case text to generated practice | The correction exposes the existing ticket consumer from Cases. Test receives the ticket and a separate instruction; questions, keys and answers remain volatile and unreviewed. Existing actual Cases/backend tests cover revision and deletion revocation. | Actual engine evidence establishes extraction/guarded inputs, not live generated educational accuracy. |
| Clinical-image/chart interpretation | **Unsupported.** Cases reports `image_interpretation.supported=false` and `image_input_unverified`; its attachment path produces text rather than image model input. | Required by the S2 acceptance wording. Runtime already has controlled inline-image wire mapping, but `image_interpretation_verified` remains false. It needs an authorised verified allowed-model route and a guarded Cases consumer; OCR or a catalogue listing cannot establish it. This is not a safe enablement flag change. |
| Automatic general learning principles from case discussions | **Unsupported.** Cases reports `memory_capture=false`. Case and unclassified scopes are rejected before Memory lookup/jobs/helper use. Memory can consume strictly classified `learning-point` evidence, but Cases/Learn publish no general-principle producer from temporary discussions. | Required M3→M5 behavior remains absent, including the privacy classification boundary. A producer must derive/review scoped general evidence without persisting case facts before the existing Memory outbox can consume it. Relabeling a case as study or enqueueing its transcript is invalid. This remains a Cases/Memory requirement associated with #9. |
| Save, restart and external originals | Save retains reviewed case text and permitted discussion. Restart restores only the explicit snapshot. Selected PDF/image originals stay in the user's location; no attachment copy enters case storage. | Save does not archive the source image/PDF or guarantee that the newest discussion was saved. The interface discloses this. |

Operational limits remain 10 MiB per upload, 20 PDF pages, 12 MP per image,
50,000 characters of preview/combined case text, 16 RAM previews and two native
extraction slots. Input is PDF/PNG/JPEG; teaching cases use their installed
stages. The file picker follows creation of a daily case with a learning
question. Native conversion cannot be forcibly stopped: discard hides text
and rejects late output, while its slot/input remain bounded until completion.

The earlier actual-engine evidence records approximately four minutes of cold
readiness and Windows WMI `0x8007000e` startup diagnostics; an earlier small-page
Docling/PIL access-violation diagnostic is also preserved. Subsequent prepared
Cases checks passed. These records do not establish clean-machine/native
stability; startup/helper/release follow-up remains with the platform owner.

The freeze ledger can claim the local OCR/review/apply/explicit-retention flow
and guarded text handoffs. It must retain the image-interpretation and
case-derived-general-learning gaps rather than claim complete S2/M3 coverage.

## Evidence and checks

The requirements are in [S2](../planning/IMPLEMENTATION_PLAN.md) and the
[temporary-case/Memory architecture](../planning/ARCHITECTURE.md). Inherited
actual-engine records are [Cases](cases-evidence.md),
[Knowledge](knowledge-evidence.md), [runtime image contracts](runtime-evidence.md)
and [Memory](MEMORY.md). The old Cases evidence's shell-banner limit is already
resolved by [the integrated snapshot fix](case-scope-banner.md).

The existing Cases handoff test was extended across both targets and saved
states; two new practice variants fail against the missing action. The practice
variants mount the actual GeneratedPractice consumer and prove its outgoing
temporary ticket request, absence of raw case text, no saved-practice-history
request, no autosave/browser storage, and real Return to Cases after a
controlled generation error. There is no new speculative test family.

```powershell
node ../Renulus-wt-integration/apps/desktop/node_modules/vitest/vitest.mjs run --config .local/runtime/case-input-audit/verification.config.mjs --configLoader runner --reporter=dot
# 31 passed across 5 files: Cases, navigation and scope-banner checks.

& ../Renulus-wt-integration/.venv/Scripts/python.exe -m pytest tests/cases/test_attachments.py tests/assessment/test_generated.py tests/learn/test_retention_acceptance.py -q --tb=short
# 51 passed in 61.83 seconds; existing synthetic API/SQLite/guard checks only.

node apps/desktop/src/modules/memory/typecheck.mjs
node ../Renulus-wt-integration/apps/desktop/node_modules/vite/bin/vite.js build --config .local/runtime/case-input-audit/verification.config.mjs --configLoader runner
& ../Renulus-wt-integration/.venv/Scripts/python.exe scripts/check_workspace.py
git diff --check
```

Typecheck, renderer build, workspace and whitespace checks pass. Existing
preview dynamic-import and TestClient deprecation warnings remain nonblocking.
The `.local` wrapper and generated renderer output are ignored and isolated.
