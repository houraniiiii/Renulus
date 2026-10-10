# Renulus product context

<!-- impeccable:product-schema 1 -->

Confirmed product direction updated October 10, 2026. The
[project brief](docs/PROJECT_BRIEF.md) and [decisions](docs/DECISIONS.md) record
the product authority. The [Design C spec](docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md)
defines the replacement UI, connected behaviour and acceptance. Its labelled
planning defaults remain adaptable. Design C is connected in the integration
source; the normal installed app still uses Flow until matching Windows acceptance
and cutover pass. The spec records feature evidence and remaining gates.

## Platform

web

The React renderer runs inside the Windows Electron desktop application and
in a browser during development. Native lifecycle is owned by Electron.

## Stack

User selected React/TypeScript, the Hermes foundation, and one local
FastAPI process. Reuse appropriate upstream Electron lifecycle functions.
Mem0 OSS, Docling/HybridChunker, FastEmbed and LanceDB OSS are approved backend
components; feature and runtime lanes own their implementation.

## Users

Nephrologists practising in the EU on personal Windows computers, during
specialisation, brief daily learning, focused study and examination preparation.

## Product Purpose

Support learning across nephrology: explanations, daily case discussion,
reviewed assessment, generated practice, sources, retained learning and updates.

## Operating Context

English first. Design C brings explanations and case discussion into chats,
organised in projects with shared documents and study goals. Global destinations,
including Library, Tests and Updates, sit above projects/chats on the left.
An optional resizable workspace opens files and contextual material beside chat.

New chat uses the chosen doctor name in a greeting, the composer prompt
"How can I help you today", Attach, and Explain a topic / Discuss a case /
Quick practice actions. Each action reveals five daily personalised suggestions.
The spec owns their generation, cache, failure and connection behaviour.

Chats and context, including case discussions, save by default. Archive and
optional temporary conversations remain distinct actions. Explicit temporary
content follows the spec's retention rules. Study and Test have distinct help,
submission and timing behaviour; reviewed-bank scores remain separate from
generated/imported practice. Their implementation and delivery evidence is tracked
under the C tickets.

## Capabilities and Constraints

Use the exact selected subscription/model allowlist in docs/DECISIONS.md.
No paid-provider inference during implementation verification, no credentials
from another app, and no private datasets. Provider secrets stay outside the
renderer. Synthetic fixtures establish application behaviour only.
No model response, clinical accuracy or clean-machine installer proof is
established by the shell. Feature readiness follows actual integrated APIs.

## Brand Commitments

Renulus, selected C — Renal flow mark, calm precise approachable medical voice.
Design C is the selected interface. Reuse the brand assets, Source Sans 3,
semantic teal tokens and suitable existing components as its coherent foundation.

## Evidence on Hand

The editable C Figma page and screen/state links are indexed in the C spec.
Selected brand exports, attributed Hermes source and dated
[desktop evidence](docs/implementation/desktop-evidence.md) establish the original
baseline. The C spec and [execution record](docs/implementation/EXECUTION.md)
link actual connected source, recovery and hidden UI checks. Matching installed
acceptance is separate. Prototype data is not production content, learner progress
or source verification.

## Product Principles

- Make the next learning action easy to find.
- Keep case scope, assessment mode and source status explicit.
- Preserve originals and isolate app-owned state per development instance.
- Show actionable loading, empty and failure states using real API results.
- Reuse one coherent design system across modules.
