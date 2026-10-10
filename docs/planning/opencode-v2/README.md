# OpenCode integration specifications and vertical slices

**Canonical Design C handoff:** H00 is already repaired in `fa3b590c`. H01/H24
are complete for their local foundation scope from
`c2bd896420fb88f76d63ca576414dbbba182f4c2`; see the
[implementation handoff](../../implementation/OPENCODE_FOUNDATIONS_HANDOFF.md).
H02 is the next planned slice; other uncompleted tickets remain planned. DC21 final
delivery remains deferred to H20. Consume the
[integration handoff](../../implementation/DESIGN_C_OPENCODE_HANDOFF.md) and
[exact captured planning snapshot](../../implementation/opencode-plan-snapshot/README.md)
before implementation; the dated review text below is preserved for context.

2026-10-10. **Reviewed baseline: three specs, 56 user stories and 25 tracked slices.** All six adaptive research waves are complete. H00 is consumed, H01/H24 have local foundation acceptance, and 22 slices remain planned. The owner's [implementation instruction](../2026-10-04-user-answers.md#october-10-first-opencode-foundation-implementation-authorisation) accepts the existing seams for this initial work. Tracker publication is not required. Live account, migrated-client and packaged acceptance remain separate gates.

Read the [integration plan](../OPENCODE_V2_INTEGRATION_PLAN.md), then the three specifications:

1. [S1 — Configurable execution harness](specs/01-harness-control.md): host, tools, children, subscriptions, configuration, instructions, skills, plugins and MCP.
2. [S2 — Evidence, memory and long context](specs/02-memory-context.md): answer lineage, correction/deletion, retrieval, temporary scope, educational compaction and history navigation.
3. [S3 — Existing workflows and migration](specs/03-workflows-migration.md): generation/results/Home/nightly/Updates adapters, receipts, backup and Windows cutover.

The files retain stable H IDs and their acceptance criteria. GitHub Issues remains the repository's queue, but no issue creation or ready-for-agent label is needed for the authorised local H01/H24 work. Remaining tickets stay planned; tracker publication is outside this task.

## Vertical slices

Each ticket connects an observable outcome through the existing client/domain facade and OpenCode, with explicit acceptance and current-owner reuse. The research inspected `76cfdff23e259700bec820e174c200540c7c1e1b`; older `528025ff` tests remain dated separately. The first implementation wave starts from the reconciled Design C baseline `c2bd896420fb88f76d63ca576414dbbba182f4c2`. DC IDs are coordination/contract obligations, not an assertion that those implementations are still missing.

| Ticket | Connected outcome | Blocked by | Spec | Owner |
| --- | --- | --- | --- | --- |
| [H00](tickets/00-restore-the-existing-saved-generation-retrieval-path.md) | Completed prerequisite `fa3b590c`: existing saved-generation retrieval | — | S3 | M4 + integration |
| [H24](tickets/24-keep-memory-worker-ownership-until-extraction-settles.md) | Completed local foundation: retain memory-worker ownership through actual settlement | — | S2/S3 | M5 + F0/integration |
| [H01](tickets/01-run-a-persistent-headless-opencode-conversation.md) | Completed local foundation: persistent headless OpenCode host | — | S1 | F0 + integration |
| [H02](tickets/02-answer-with-an-eligible-library-passage.md) | Planned next: answer with an eligible Library passage | H01 satisfied | S1/S2 | M2 + M1/F0 |
| [H03](tickets/03-use-the-selected-subscription-for-tools-and-images.md) | Use the selected subscription for tools and images | H01, H02 | S1 | F0 |
| [H04](tickets/04-adjust-roles-and-configuration-with-visible-activation.md) | Adjust roles and configuration with visible activation | H01, H03 | S1 | F0 + integration |
| [H05](tickets/05-complete-a-learning-turn-whose-memory-stays-corrected.md) | Complete a learning turn whose memory stays corrected | H02, H04, H24 | S2 | M5 + M1 + integration |
| [H06](tickets/06-continue-saved-and-temporary-chats-through-one-owner.md) | Migrate and delete one saved conversation through a single owner | H02, H05 | S2/S3 | M1/M3 coordinated + F0/integration |
| [H07](tickets/07-delegate-a-bounded-evidence-review-and-stop-its-children.md) | Delegate a bounded evidence review and stop its children | H02, H04, H05 | S1/S3 | F0 + M1/M2 |
| [H08](tickets/08-apply-versioned-instructions-and-skills-to-a-learning-task.md) | Apply versioned instructions and skills to a learning task | H04, H06 | S1/S2 | F0 + M1 |
| [H09](tickets/09-use-and-revoke-an-explicitly-connected-mcp-tool.md) | Use and revoke an explicitly connected MCP tool | H04, H07 | S1 | F0 + integration |
| [H12](tickets/12-publish-one-validated-five-question-saved-test.md) | Adapt five-question saved generation to OpenCode | H02, H04, H05; H00 satisfied | S3 | M4 + integration |
| [H13](tickets/13-resume-10-and-20-question-generation-without-duplicate-work.md) | Preserve existing 10- and 20-question checkpoints through OpenCode | H12 | S3 | M4 + F0/integration |
| [H14](tickets/14-explain-deterministic-reviewed-test-results.md) | Explain deterministic reviewed-test results | H03, H04, H05 | S3 | M4 + M5/F0 |
| [H15](tickets/15-generate-daily-suggestions-from-eligible-learning.md) | Route existing daily suggestions and Quick practice through the harness | H05, H12 | S3 | M6/M1 + M4/M5 |
| [H16](tickets/16-produce-a-dated-updates-digest-without-altering-source-review.md) | Produce a dated Updates digest without altering source review | H02, H04 | S3 | M7 + M2/F0 |
| [H17](tickets/17-run-one-bounded-opt-in-nightly-practice-occurrence.md) | Adapt the existing nightly occurrence to OpenCode execution | H13 | S3 | M4/M6 + integration |
| [H21](tickets/21-run-temporary-conversations-and-save-across-runtime-stores.md) | Run temporary conversations and save them across runtime stores | H06, H07 | S1/S2/S3 | M1/M3 + F0/integration |
| [H10](tickets/10-continue-an-evidence-aware-128k-or-256k-conversation.md) | Continue an evidence-aware 128K or 256K conversation | H03, H05, H06, H08, H21 | S2 | F0 + M1/M5 |
| [H22](tickets/22-route-explicit-fictional-test-preparation-through-the-harness.md) | Route explicit fictional-test preparation through the harness | H04, H21 | S3 | M4 + M1/M3/F0 |
| [H23](tickets/23-route-imported-test-refinement-through-the-harness.md) | Route imported-test refinement through the harness | H04 | S3 | M4 + M2/F0 |
| [H18](tickets/18-delete-and-restore-a-consistent-migrated-learning-profile.md) | Delete and restore a consistent migrated learning profile | H09, H10, H14, H15, H16, H17, H22, H23 | S2/S3 | Integration + F0 + M1/M2/M5 |
| [H20](tickets/20-cut-over-the-windows-client-with-a-recoverable-release.md) | Cut over the Windows client with a recoverable release | H18 | S1/S2/S3 | Integration + F0 and module owners |
| [H11](tickets/11-recover-older-detail-through-a-derived-history-view.md) | Recover older detail through a derived history view | H10, H18 | S2 | M1/M5 + F0 |
| [H19](tickets/19-validate-an-optional-additional-or-local-provider.md) | Validate an optional additional or local provider | H04, H10 | S1/S2 | F0 future optional lane |

H00 is a satisfied prerequisite; H12 consumes its repaired guard without repeating the work. H24 (actual memory-worker settlement) and H01 (managed host proof) are completed local foundation slices from `c2bd8964`; H02 is the next planned slice. Preserve the repair and landed Design C owners. H01 establishes paired-store contracts; H02 validates and activates the first saved generation before H06 migrates saved history. H21 separately proves temporary execution and Save; H22/H23 explicitly migrate fictionalisation/import producers. H18 consumes all default producers' proofs for paired-store restore, and H20 performs Windows cutover. One M5/integration owner controls shared lineage schema.

H11 (evaluated history tree) and H19 (optional future providers) do not block default cutover. H10 supplies mandatory exact-history retrieval and context accounting; tree activation requires H11's extended H18 retention/restore acceptance. The table is in dependency order even though stable H identifiers reflect discovery order.

## Requirement coverage and proof boundaries

| User requirement | Spec / slices | Required evidence |
| --- | --- | --- |
| Integrate current work without redundancy | All; H00/H01/H02/H06/H12–H18/H20–H24 | Current committed source delta, existing identities/producers, preserved flows and single ownership |
| Correct memory and retrieval | S2; H02/H05/H06/H18/H21/H24 | Current stale-recapture regression, real engine tests, exact source revisions, restore/frontier and support rules |
| Instructions, skills, plugins, MCP | S1; H04/H08/H09 | Explicit manifests, effective activation, no ambient discovery, pending-revocation and nested-call tests |
| Routing, fallbacks and strong backend roles | S1; H03/H04/H12–H17/H22/H23 | Counting transport on every dispatch path, bounded attempts, capability epochs, per-role evaluations |
| Agent loops, subagents and deterministic orchestration | S1/S3; H01/H07/H12/H13/H17 | Real upstream loop/children, current validators/receipts, cancellation/recovery fault injection |
| Reliable adjustment and control | S1; H03/H04/H08/H09 | Requested/effective/failed state, restart activation, explicit busy-run semantics and revocation |
| Later vLLM/Ollama and more providers | S1/S2; H19 | Exact deployment/template/protocol qualification, opt-in; no required model-server installation |
| 128K–256K context and injection | S2; H08/H10 | Final-request budgeting, instruction reinjection, exact account limits; unknown means unavailable |
| Article-inspired memory/context | S2; H10/H11/H18 | Educational summary plus exact history first; tree recall/false-recall/correction/deletion/cost evidence |
| Minimal upstream edits | S1; H01/H07/H09/H10/H18 | Supported composition first; a failing connected test, narrow patch and removal condition if needed |
| End-to-end Windows harness | All; H20 | Matching packaged artifact, native install/auth acceptance and existing varied-domain client flows |

## Accepted foundation test seams

Use the existing public domain/conversation commands plus the small Harness facade as the highest useful test seam. The headless client and desktop use the same operations and receipts. Keep actual SQLite, validators and selected local engines where relevant; substitute only external inference with a counting scripted transport. Use lower-level failure injection for dispatch, plugin readiness, temporary spills and packaging where the public interface cannot express a failure precisely. Record actual account/model/window and native Windows acceptance separately.

The owner's instruction to implement H01/H24 accepts these existing planned seams; no new seam approval or tracker publication is needed. Use one behavioural failing test followed by minimal implementation per cycle. The full source and check ledger is [here](../../research/2026-10-10-opencode-integration/README.md).

