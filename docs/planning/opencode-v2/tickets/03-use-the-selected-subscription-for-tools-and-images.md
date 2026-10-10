# H03 — Use the selected subscription for tools and images

**Status:** draft — review pending; implementation not authorised by this research request.

**Spec:** [S1](../specs/01-harness-control.md)

**Owner:** F0

**Current source baseline:** `76cfdff23e259700bec820e174c200540c7c1e1b`. Reconcile later changes before implementation.

## What to build

A user chooses an existing permitted subscription/model and completes a text/tool or image learning turn through the new harness.

## Existing owner and delta

Current ProviderManager protected connections, selected defaults, allowlists and capability records. Preserve existing behavior and extend its integration boundary; do not recreate a landed producer.

## Acceptance criteria

- [ ] Preserve current protected connection references, explicit selected defaults and exact allowlists; do not import ambient OpenCode credentials.
- [ ] Validate catalog versus wire model/protocol/endpoint identity, tool-call/result pairs, image MIME and required input compatibility.
- [ ] All primary/session/stateless/auxiliary/child transport paths deny missing admission; final HTTP and WebSocket paths cannot bypass the policy.
- [ ] Mocked 401 invalidates account-dependent availability/observations without misreporting modality; fix the retained baseline discrepancy.
- [ ] Synthetic transport tests prove routing only; matching account/tool/image acceptance is separately recorded before normal cutover, with no implicit provider switch.
- [ ] Every request kind has a final enforced output/input/window bound; hooks cannot remove it. Synthetic credential canaries never enter transcripts, receipts or diagnostics.

## Blocked by

- [H01](01-run-a-persistent-headless-opencode-conversation.md)
- [H02](02-answer-with-an-eligible-library-passage.md)

## Design C coordination

- DC10 Connections presentation where adopted

Preserve the canonical DC owner and acceptance in the [Design C spec](../../DESIGN_C_IMPLEMENTATION_SPEC.md). These are coordination/contract obligations, not a claim that landed DC tickets remain unimplemented. Review current integration leases before changing shared modules.

## Evidence and validation

[Focused evidence](../../../research/2026-10-10-opencode-integration/w1-05-model-routing.md); [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md). Exercise observable behavior through the existing public domain/conversation facade and shared Harness interface. Record scripted transport, real engine, real account and packaged acceptance separately. Existing failures remain open until the corresponding acceptance proves their resolution.
