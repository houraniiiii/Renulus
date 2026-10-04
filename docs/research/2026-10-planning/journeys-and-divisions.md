# Learning journeys and product divisions

Planning only · 2026-10-04 · **Confirmed** means the user's answers; **proposed** means a recommendation, not an adopted requirement. No implementation is implied.

**Superseded planning proposals:** rounds 1–3 are now settled. Use the
[architecture](../../planning/ARCHITECTURE.md) for current module ownership and
the [implementation plan](../../planning/IMPLEMENTATION_PLAN.md) for acceptance.
The seven-division table below is historical design input.

Updated after round 2: broad nephrology capability replaces the rejected
single-subject-first proposal. The current subscription/model list, input
requirements and remaining questions are in the
[decision queue](../../planning/DECISION_QUEUE.md).

**What the answers establish**

The audience is practising nephrologists in the EU, with learning throughout specialisation central. Whether experience level warrants tailored journeys remains open. English comes first; other EU languages are optional later. The final application is Windows only.

Confirmed needs cover topic understanding, cases, examinations, programme coverage and current updates. Short daytime use and focused active study are different session lengths within that same product. Proposed consequence: a quick question or saved checkpoint should open directly, while longer sessions connect explanation, application and assessment.

Chat/Explain and Test are distinct modes. Proposed rule: Explain permits questions, hints and correction; Test records a committed answer before revealing feedback. Switching to Explain during an unanswered scored item ends or explicitly marks that attempt as assisted. Reviewed bank items support scores; generated questions support labelled practice and cannot silently enter scored-bank results.

Daily-practice discussion means interactive educational reasoning about a case, with successive findings and alternatives. It does not establish an operational patient-management workflow. Proposed initial cases are synthetic, with explicit learning objectives and staged information.

“Remember important information without redundancy” needs selective continuity, not repeated chat summaries. Proposed memory stores canonical records with stable identities, provenance and revisions; summaries derive from those records and can be rebuilt. Updating one learning note updates its summaries rather than creating another competing fact. Users can inspect, edit, delete and export their records; deletion invalidates derived summaries too. Progress uses observable attempts, case decisions and completed activities, with assistance recorded. Mentioning a topic in chat establishes interest, not competence.

The owner and assistant review and validate content together; an external panel is not a prerequisite. Review records describe what was checked and unresolved concerns, without accuracy guarantees or repeated medical disclaimers.

**Seven proposed vertical divisions**

Each division owns its UI, behavior, authoritative records and small interface; acceptance describes an end-to-end journey. These are modules within one product and repository.

| Division | UI, behavior and owned data/contract | Acceptance journey |
| --- | --- | --- |
| Study programme and resume | Topic outline and next-session view; choose objectives, save checkpoints, resume. Owns programme selections and session checkpoints; references evidence from other modules. | Pause a case, close Windows app, reopen at the same step without inventing completion. |
| Chat/Explain | Conversation with expandable explanations and source links. Owns thread turns, explanation context and source references; offers explicit transfer into practice. | Ask a follow-up, inspect its supporting passage, save one takeaway and start related practice. |
| Educational cases | Staged case workspace; request findings, record reasoning, discuss alternatives. Owns case runs, revealed facts and learner decisions; references approved versions and emits evidence. | Work through a synthetic case, resume after interruption and compare reasoning with its reviewed debrief. |
| Test and practice | Clearly labelled scored-bank and generated-practice sessions; commit answers, reveal feedback, review mistakes. Owns attempts, assistance status and scoring against a fixed item version. | Answer a reviewed item, see its rationale and score; generated practice remains separately identified. |
| Memory and progress | Editable notebook and evidence history. Owns canonical learning records, evidence references and derived summaries; exposes edit/delete/export operations. | Correct a takeaway once, see the corrected summary, inspect the attempt behind a progress entry and export records. |
| Staying current | Dated update list with source and review status; compare changes and connect them to study objectives. Owns update entries, checked-through dates and read/saved status. | Open an update, inspect the original publication, save its learning implication and see when checking last occurred. |
| Content review | Review workspace for sources, cases, questions and rationales; draft, revise, approve or retire versions. Owns content provenance, use status and review records; other modules consume approved versions. | Owner reviews assistant-drafted content, approves a version, then sees it become available; earlier attempts retain their original version. |

**Shared foundations and design evidence**

Shared foundations support those journeys: Windows shell, accessible controls, local persistence, recovery, export plumbing and model connectivity. These are not additional vertical divisions or microservices. Prefer direct use of maintained components and deep modules with small interfaces; add adapters when real variation warrants them, not speculative layers.

The open-source harness must run without owner-hosted services or inference. Existing models only; no retraining. Round 2 selects Codex and/or OpenCode Go subscriptions and an explicit five-model list. Integration remains to be implemented. A proposed unavailable-model state preserves drafts and offers access to saved material.

Local [Impeccable](../../../.agents/skills/impeccable/SKILL.md) prioritises task completion and platform expectations; [interface-design](../../../.agents/skills/interface-design/SKILL.md) prioritises one focal task and meaningful evidence displays. Both read 2026-10-04. Microsoft documents keyboard, screen-reader, text-scaling and contrast support for Windows applications ([official guidance](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/accessibility-overview), accessed 2026-10-04). Proposed acceptance includes those capabilities across the complete journey. These sources support design choices, not learning-effect claims.

**Connected learning across nephrology**

After connecting a selected subscription, the doctor freely chooses a topic, asks a question or supplies text, a PDF or an image. They can explore a mechanism in Explain, discuss a case, explicitly enter Test, inspect feedback and sources, retain useful learning and resume later. Missing model access preserves the checkpoint.

Implement these capabilities across the topic map. Acceptance examples should span different domains such as CKD, glomerular disease, dialysis and transplantation, including cross-topic cases. A subject-specific test fixture must not define product scope. Build bank and case coverage across the discipline, with visible gaps rather than a claim of completeness.

**Current decision status**

General nephrology topics plus an ESENeph track and guidelines plus selected
research are confirmed. The first-topic question is withdrawn. All round 3
recommendations are accepted: see the [answer record](../../planning/2026-10-04-user-answers.md).
No major user decision is pending in the [decision queue](../../planning/DECISION_QUEUE.md).
