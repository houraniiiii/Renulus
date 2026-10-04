# Renulus decision queue

Updated 2026-10-04 after rounds 1–3, upstream research, adversarial review and
explicit approval of the starting stack.
This file contains remaining decisions; it is not a competing architecture.

## Confirmed and closed

All seven round-3 recommendations are accepted. Model control, learning memory,
explicit case Save, reusable study library, teaching style, adaptive planning,
automatic evidence lookup and home behaviour are recorded in
[the user answers](2026-10-04-user-answers.md) and [DECISIONS](../DECISIONS.md).

Hermes is the confirmed fork foundation. Reuse its existing runtime and suitable
desktop modules. Broad nephrology support, selected subscriptions/models,
text/PDF/image input, personal Windows computers and no owner-hosted inference
remain fixed. The user has also selected MIT for Renulus code and CC BY 4.0 for
original teaching content, preserving third-party terms.

The user has accepted **Hermes + Mem0 OSS + Docling/HybridChunker + FastEmbed +
LanceDB OSS**. Canonical records stay in SQLite; Mem0 initially reuses its local
Qdrant client for derived memory storage. Small bundled CPU helpers and the
no-setup clinician experience are confirmed. The component decision is closed;
runtime/configuration details and acceptance evidence remain engineering work.

The source follow-up confirms one [development source register](../SOURCES.md),
ERA user downloads as an acquisition direction, latest-final source handling,
and optional user-supplied web/literature retrieval keys. Source adapters and
edition/use records are engineering work; these choices need no new product
questionnaire. Optional paid tool use requires the user's explicit activation.

**No further major product decision is currently waiting on the user.**
The licence question identified by reviewers has been answered. Engineering
uncertainty does not turn into another questionnaire.

## Engineering decisions made for the plan

| Area | Baseline | Evidence or acceptance still required |
| --- | --- | --- |
| Desktop/runtime | Reuse Hermes Electron/React foundation and Python runtime; narrow controlled integration | Native Windows package, app-owned subscription authentication, exact main/auxiliary generation allowlist, no-save policy |
| Record authority/context | Canonical SQLite records + Hermes memory/context hooks and compressor | IDs/revisions, scoped context budgets, temporary-case isolation and export/restore |
| Learner memory | User-selected Mem0 OSS through Hermes; initial local Qdrant index | Generative subscription adapter, durable eligible capture, history purge, safe reindexing and expected memory volume |
| Documents/chunking | User-selected Docling CPU pipeline + HybridChunker; PDF.js for viewing | OCR/artifact selection, source-page/region mapping, table/header/unit fidelity, CPU footprint and no-save paths; LiteParse comparison only for a concrete gap |
| Embeddings | User-selected FastEmbed with one explicit app-managed CPU model per index version | Exact model/ONNX/tokenizer revisions, dimensions/token limits, licences, offline loading and resource use |
| Document retrieval | User-selected LanceDB OSS hybrid search | Revision/scope filters, paraphrases/acronyms, citation quality, physical cleanup and recovery |
| Source acquisition/currency | Single SOURCES register; publisher downloads, supported literature datasets/APIs and authorised user imports | Current final edition/corrigenda, chapter replacement, retractions, access/operation records, user import and update journeys |
| Optional retrieval connections | User-supplied web/literature API keys, separately scoped from generative subscriptions | Reused Hermes tool adapters, protected credentials, explicit activation, quotas/cost caps and honest unavailable-key states |
| Supermemory | Excluded from adoption | Preserve earlier evaluation and the [selected-stack evidence](../research/2026-10-04-starting-stack-evidence.md); no replacement decision is pending |
| Distribution | Bundle the selected runtime, native dependencies and helper artifacts | Compatible version lock, hashes/notices, clean Windows installation and no doctor-managed model service |
| Parallel work | One owned vertical slice per branch/worktree, one coordinated shared-contract/migration path | Isolated runtime and installer identities, dependency-first merges, combined real journeys |
| Release | Working features and a measurable broad-domain coverage manifest | Required capabilities/coverage met; real installer, signed updates, migration/restore and accessibility |

These are engineering baselines, not claims of implemented functionality. Exact
pins, capability evidence and failures belong in the implementation record.
Cognee, Hindsight, Mnemosyne, Xberg and other researched projects remain
alternatives. Haystack/LlamaIndex or selected application modules may supply a
narrow reusable missing component if justified; they are not selected extra
layers. Preserve the rationale and sources in the
[research evidence](../research/2026-10-04-starting-stack-evidence.md).
See [stages](IMPLEMENTATION_PLAN.md), [modules/interfaces](ARCHITECTURE.md) and
[parallel work](PARALLEL_WORK.md).

## Escalate only a demonstrated material change

Ask the user if real evidence requires a new mandatory paid service/subscription, an
unapproved generation model, user-operated inference, a material change in data
hosting, a weaker input/retention requirement, incompatible distribution terms,
or abandoning the selected Hermes foundation. Present the actual failure and
concrete alternatives first. Ordinary adapters, packaging fixes, extraction
choices and schema details are engineering work.
Optional user-selected paid retrieval services are already authorised as a
capability; do not mistake them for permission to incur usage during development
or to introduce a paid generative fallback.

Operational inputs will be needed at the relevant stage: users connect their own
accounts; Figma work needs an accessible file/account; public signed releases
need a publisher identity and signing setup. None requires reopening product
scope or reading private account state during planning.

This remains a real-product plan. Prototypes are decision aids; only functioning
integrations and end-to-end behaviour establish implementation completion.
