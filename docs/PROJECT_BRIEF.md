# Renulus project brief

Confirmed direction updated on 2026-10-04 from the
[user's answers in rounds 1–3 and subsequent stack approval](planning/2026-10-04-user-answers.md).

Renulus is an independent open-source Windows application for nephrologists
practising in the EU. Its central job is to support education and learning
throughout specialisation, active study and staying up to date. A complete
product is intended. The first implementation must establish reusable learning
capabilities across nephrology. A single-subject product or a plan to perfect
acid–base before supporting the broader discipline has been explicitly rejected.

## Experience

Support topic explanations, educational cases, examination preparation and
guided study. Doctors may visit briefly during the day or spend a focused
session studying. They can discuss questions arising from daily practice as
part of the educational experience.

Organise learning by general nephrology topics with an ESENeph examination
track; add specific national programme mappings where useful. Support text,
summaries, PDFs, images and other useful input methods. Staying current includes
guidelines and selected important research.

Chat/Explain and Test are separate modes. A reviewed question bank supports
scored assessment; generated questions serve practice. Automatically retain
useful learning information without redundant records, with inspection and
editing. Raw daily-practice cases and attachments persist only after explicit
Save. Uploaded study documents can form a reusable personal library with
passage/page citations.

Explain answers directly by default, with optional guided teaching. Offer an
adaptive study plan while preserving free exploration and manual changes.
Automatically retrieve reliable evidence when needed and show sources, dates
and retrieval failures. The home presents Ask, Resume, suggested review and
relevant updates, with easy access to topics and Test.

English is the first product language. Other EU-relevant languages are possible
later. Personal Windows computers are the delivery target. Model and tool configuration
should sit behind a straightforward experience for doctors.

The [single development source register](SOURCES.md) includes open content,
authorised member/institutional downloads, personal imports and research access,
with a user acquisition method for each. The owner confirms ERA user downloads
as an acquisition direction. Use current final guidance with corrections and
supersession tracking. Optional user-supplied keys for web/literature search and
related retrieval tools are supported, with explicit activation and usage
controls; they are separate from the selected generative subscriptions.

## Operating model

Renulus is a harness using existing models, with no retraining or fine-tuning.
The project owner will not host a service or model inference. Use existing
OpenCode Go and/or Codex subscriptions, restricted to this selected model list:

- Codex: GPT 6.1 Sol, GPT 6 Astra and GPT 6 Luna.
- OpenCode Go: MiMo V2.6 Pro and DeepSeek V4.1 Flash.

Authentication and account-specific availability remain integration work.
Do not silently add conversational models, introduce a paid API fallback or
require user-managed local inference. Small CPU models bundled and managed by
Renulus for embeddings/OCR are accepted, without GPU, Docker, model server or
setup for doctors. Select automatically within the user's chosen subscription and
allowed/available models, with manual override and no silent subscription switch.

The backend foundation is a **Hermes fork**. Preserve its licence and upstream
attribution, reuse its existing capabilities, and add Renulus-specific logic
only where needed. Research supports reusing its existing Electron/React desktop
foundation and Python runtime as the engineering baseline. The user has excluded
Supermemory from adoption because the reusable engine itself must be open source.
The user approved **Mem0 OSS + Docling/HybridChunker + FastEmbed + LanceDB OSS**
behind Hermes. Mem0 supplies learner-memory processing; Docling and its chunker
supply structured document ingestion and source mapping; FastEmbed supplies CPU
vectors; LanceDB supplies document keyword/vector retrieval. Reuse Hermes's
context hooks and compressor. Canonical records stay in SQLite, with derived
engine indexes; initial Mem0 storage uses its embedded local Qdrant client.

The [framework research](research/2026-10-04-context-framework-recommendation.md)
and [stack evidence](research/2026-10-04-starting-stack-evidence.md) preserve the
rationale, sources and alternatives. Exact helper/model/package artifacts,
subscription adapters, extraction quality, retention and installed Windows
performance still need verification. The approval is a planning decision, not
a claim of implemented capability or permission to add every optional model.

Every implementation stage must advance the real product: working user flows,
real persistence and real integrations. Prototypes help choose designs; they
do not count as implemented functionality. Divide work into vertical slices
with explicit module ownership and dependencies suitable for parallel worktrees.

## Design and review

The name is **Renulus**. The selected logo is **C — Renal flow**, in the selected
teal treatment. The character is modern medical: calm, precise and approachable,
with a subtle abstract renal reference. See [the brand record](../assets/brand/README.md).

Use Figma for the design process, informed by Impeccable and Interface Design.
The user and assistant lead development, review and validation. Practical checks
of sources, question keys, learner journeys and software behaviour should guide
acceptance; an external review panel is not a prerequisite for starting work.

## Current status

The working integration build now has the Flow renderer, managed local API,
attributed Hermes routes and canonical SQLite records. Learn, Library, Cases,
reviewed Test/generated practice, Memory, Today/study planning and Updates have
real service implementations. The matching Windows app is installed and selected
by the normal shortcut, with bounded local installation, recovery, originals,
deletion, reader and ordinary lifecycle acceptance. On October 7, actual source
journeys completed with Sol and both approved Go models. Explain, follow-up,
Stop/retry, generated practice, automatic capture/recall, Case/image discussion
and Library citation/original access have individually scoped live evidence.
The 1.2.0 content release adds depth across eleven domains and resolves four
objective mismatches; complete content/currency and successful dated external
body retrieval remain open. The matching cb59beb2 Windows installation passed
the real Sol core learning/capture/reopen journey and is selected by the normal
launcher. Its profile and original collection remain on E:.
See [the implementation run](implementation/EXECUTION.md),
[startup guidance](implementation/RUNNING.md) and
[current continuation](implementation/FINISH_20261007.md).
The inherited clinical MVP and batch/research project remain separately archived.
Their code and checks do not establish Renulus's functionality or effectiveness.

Original question/case packs span nephrology and record assistant source/key
review separately from independent human review. Authorised eligible acquired
files are being indexed from the external collection. Actual CPU-backed text,
PDF and image extraction, passage retrieval and learner memory have separate
proof records. Temporary case input remains volatile until explicit Save;
patient files and hospital systems are not part of development verification.
See [source boundaries](SOURCES.md),
[confirmed decisions](DECISIONS.md), [implementation stages](planning/IMPLEMENTATION_PLAN.md)
and [remaining engineering checks](planning/DECISION_QUEUE.md).

Renulus's own code uses MIT and its original teaching content CC BY 4.0, allowing
permissive reuse with attribution. Third-party and personal material retain
their own terms. Add scoped licence files with source/content adoption.
