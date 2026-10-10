# H19 — Validate an optional additional or local provider

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S1](../specs/01-harness-control.md), [S2](../specs/02-memory-context.md)

**Owner:** F0 future optional lane

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

An advanced user explicitly enables a supported extra provider or vLLM/Ollama endpoint under the same purpose and capability controls.

## Existing owner and delta

H04/H10's provider/context contracts; optional future lane, no required local setup. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Record exact endpoint/protocol/model aliases, credential reference, context configuration and adapter identity.
- [ ] Use protocol fixtures for tools, images, structured output, streaming/cancel and unsupported stateful/native features; compatibility labels are not capability proof.
- [ ] Route switches rebuild compatible eligible context and never forward opaque checkpoints/continuation IDs blindly.
- [ ] Show effective limits/failures and preserve initial subscription defaults; no automatic install/model download or fallback activation.
- [ ] Actual target deployment acceptance is required before that connection is advertised as supported; ordinary users need no local runtime.
- [ ] Lower verified windows remain supported; the H10 dependency supplies accounting and reconstruction contracts, not a requirement that the optional endpoint accept 128K/256K.

## Blocked by

- [H04](04-adjust-roles-and-configuration-with-visible-activation.md)
- [H10](10-continue-an-evidence-aware-128k-or-256k-conversation.md)

## Design C coordination

- Future optional scope; not a default-release blocker

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w3-02-capabilities-evaluation.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
