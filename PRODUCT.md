# Renulus product context

<!-- impeccable:product-schema 1 -->

Confirmed context for the authorised implementation on October 4, 2026.
The project brief and decisions remain the product authority.

## Platform

web

The React renderer runs inside the Windows Electron desktop application and
in a browser during development. Native lifecycle is owned by Electron.

## Stack

User selected React/TypeScript, Flow, the Hermes foundation, and one local
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

English first. Separate Learn and Test; reviewed-bank assessment and generated
practice have different roles. Home offers Ask, Resume, review and updates
when real records exist. A temporary case stays volatile until explicit Save.

## Capabilities and Constraints

Use the exact selected subscription/model allowlist in docs/DECISIONS.md.
No paid-provider inference during implementation verification, no credentials
from another app, and no private datasets. Provider secrets stay outside the
renderer. Synthetic fixtures establish application behaviour only.
No model response, clinical accuracy or clean-machine installer proof is
established by the shell. Feature readiness follows actual integrated APIs.

## Brand Commitments

Renulus, selected C — Renal flow mark, calm precise approachable medical voice.
The user selected Flow and authorised reuse of its actual code and assets.

## Evidence on Hand

Flow source and screenshots in the read-only UX worktrees; selected brand
exports; approved plans; attributed Hermes desktop source; implementation
evidence in docs/implementation/desktop-evidence.md. Prototype data is not
production content, learner progress or source verification.

## Product Principles

- Make the next learning action easy to find.
- Keep case scope, assessment mode and source status explicit.
- Preserve originals and isolate app-owned state per development instance.
- Show actionable loading, empty and failure states using real API results.
- Reuse one coherent design system across modules.
