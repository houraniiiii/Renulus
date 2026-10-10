# Reviewable ticket breakdown

The [three specs and coverage matrix](README.md) and [integration plan](../OPENCODE_V2_INTEGRATION_PLAN.md) provide the supporting decisions. Proposed test seam: existing domain/conversation commands plus the shared Harness facade, real local state/validators, counting synthetic inference; separate native/account/model acceptance. This review is for scope, seams, granularity and blockers, not implementation permission.

The 25 slices below are in dependency order. H00/H24/H01 are independent initial work; H11/H19 are later optional strategies. Stable IDs preserve references from the adaptive reviews.

1. **[H00 — Restore the existing saved-generation retrieval path](tickets/00-restore-the-existing-saved-generation-retrieval-path.md)** — Blocked by: none. Delivers: An existing five-question request reaches its selected synthetic provider, validates its citations and publishes one saved test before execution is migrated.

2. **[H24 — Keep memory-worker ownership until extraction actually settles](tickets/24-keep-memory-worker-ownership-until-extraction-settles.md)** — Blocked by: none. Delivers: Stopping or closing a memory capture either settles the actual extraction worker or visibly blocks store handoff until it does.

3. **[H01 — Run a persistent headless OpenCode conversation](tickets/01-run-a-persistent-headless-opencode-conversation.md)** — Blocked by: none. Delivers: A client submits a synthetic learning request to the pinned, managed OpenCode host, observes its result, closes and reopens it with the same execution identity.

4. **[H02 — Answer with an eligible Library passage](tickets/02-answer-with-an-eligible-library-passage.md)** — Blocked by: H01. Delivers: The same headless and existing desktop learning flow retrieves a real synthetic Library passage through a registered native tool and opens its citation.

5. **[H03 — Use the selected subscription for tools and images](tickets/03-use-the-selected-subscription-for-tools-and-images.md)** — Blocked by: H01, H02. Delivers: A user chooses an existing permitted subscription/model and completes a text/tool or image learning turn through the new harness.

6. **[H04 — Adjust roles and configuration with visible activation](tickets/04-adjust-roles-and-configuration-with-visible-activation.md)** — Blocked by: H01, H03. Delivers: A profile owner changes a purpose model or capability setting, sees the effective revision and can recover a failed change without partial activation.

7. **[H05 — Complete a learning turn whose memory stays corrected](tickets/05-complete-a-learning-turn-whose-memory-stays-corrected.md)** — Blocked by: H02, H04, H24. Delivers: A saved explanation produces eligible learner memory, and a later correction or deletion cannot be undone by queued capture or historical follow-up.

8. **[H06 — Migrate and delete one saved conversation through a single owner](tickets/06-continue-saved-and-temporary-chats-through-one-owner.md)** — Blocked by: H02, H05. Delivers: A user reopens an existing saved chat, continues it through OpenCode, and can delete it without orphaned transcript writers or retained command payloads.

9. **[H07 — Delegate a bounded evidence review and stop its children](tickets/07-delegate-a-bounded-evidence-review-and-stop-its-children.md)** — Blocked by: H02, H04, H05. Delivers: A learning run delegates a narrow evidence review, observes foreground/background progress and stops every owned descendant without widening access.

10. **[H08 — Apply versioned instructions and skills to a learning task](tickets/08-apply-versioned-instructions-and-skills-to-a-learning-task.md)** — Blocked by: H04, H06. Delivers: A user enables a reviewed learning skill or instruction revision and sees it applied consistently after reopen and compaction.

11. **[H09 — Use and revoke an explicitly connected MCP tool](tickets/09-use-and-revoke-an-explicitly-connected-mcp-tool.md)** — Blocked by: H04, H07. Delivers: A user connects a selected MCP server, approves a scoped operation and can disable or revoke it with a defined in-flight outcome.

12. **[H12 — Adapt five-question saved generation to OpenCode](tickets/12-publish-one-validated-five-question-saved-test.md)** — Blocked by: H00, H02, H04, H05. Delivers: The existing chat/Tests producer sends its five-question generation through OpenCode and retains one canonical saved test in both destinations.

13. **[H13 — Preserve existing 10- and 20-question checkpoints through OpenCode](tickets/13-resume-10-and-20-question-generation-without-duplicate-work.md)** — Blocked by: H12. Delivers: The existing generated-test job retains its validated 10/20-question batches through interruption while OpenCode owns execution and explicit retry.

14. **[H14 — Explain deterministic reviewed-test results](tickets/14-explain-deterministic-reviewed-test-results.md)** — Blocked by: H03, H04, H05. Delivers: A doctor receives an authoritative reviewed-test result and an optional model explanation that cannot change the score or learner evidence.

15. **[H15 — Route existing daily suggestions and Quick practice through the harness](tickets/15-generate-daily-suggestions-from-eligible-learning.md)** — Blocked by: H05, H12. Delivers: Existing Home actions request their daily three-by-five bundle through the configured purpose, and Quick practice keeps the existing canonical five-question producer.

16. **[H16 — Produce a dated Updates digest without altering source review](tickets/16-produce-a-dated-updates-digest-without-altering-source-review.md)** — Blocked by: H02, H04. Delivers: A user sees deterministic source-change checks and an optional generated digest tied to the exact observed revisions.

17. **[H17 — Adapt the existing nightly occurrence to OpenCode execution](tickets/17-run-one-bounded-opt-in-nightly-practice-occurrence.md)** — Blocked by: H13. Delivers: Existing NightlyService submits its bounded opted-in occurrence through the harness and keeps its established occurrence and explicit-retry authority.

18. **[H21 — Run temporary conversations and save them across runtime stores](tickets/21-run-temporary-conversations-and-save-across-runtime-stores.md)** — Blocked by: H06, H07. Delivers: A temporary conversation can use tools and bounded children, then either discard on disconnect or explicitly Save its eligible retained family once.

19. **[H10 — Continue an evidence-aware 128K or 256K conversation](tickets/10-continue-an-evidence-aware-128k-or-256k-conversation.md)** — Blocked by: H03, H05, H06, H08, H21. Delivers: A long learning conversation uses its supported context profile, compacts educationally and continues with exact eligible recent exchanges and evidence.

20. **[H22 — Route explicit fictional-test preparation through the harness](tickets/22-route-explicit-fictional-test-preparation-through-the-harness.md)** — Blocked by: H04, H21. Delivers: A user explicitly prepares fictional practice from temporary material, reviews the eligible result and publishes one canonical saved test through the existing flow.

21. **[H23 — Route imported-test refinement through the harness](tickets/23-route-imported-test-refinement-through-the-harness.md)** — Blocked by: H04. Delivers: A user imports a test, receives bounded model refinement through the selected route, edits unresolved material and publishes one eligible saved version.

22. **[H18 — Delete and restore a consistent migrated learning profile](tickets/18-delete-and-restore-a-consistent-migrated-learning-profile.md)** — Blocked by: H09, H10, H14, H15, H16, H17, H22, H23. Delivers: A user deletes scoped data or restores a paired runtime/domain backup covering every migrated default producer, without resurrecting suppressed learning or breaking shared originals.

23. **[H20 — Cut over the Windows client with a recoverable release](tickets/20-cut-over-the-windows-client-with-a-recoverable-release.md)** — Blocked by: H18. Delivers: The selected Windows client runs the new harness with existing learning data and a verified shutdown/reopen, backup and rollback path.

24. **[H11 — Recover older detail through a derived history view](tickets/11-recover-older-detail-through-a-derived-history-view.md)** — Blocked by: H10, H18. Delivers: The assistant can navigate a persisted summary tree or reference search to exact eligible historical detail without creating another transcript.

25. **[H19 — Validate an optional additional or local provider](tickets/19-validate-an-optional-additional-or-local-provider.md)** — Blocked by: H04, H10. Delivers: An advanced user explicitly enables a supported extra provider or vLLM/Ollama endpoint under the same purpose and capability controls.

The requested to-spec skill requires checking the proposed test seams; to-tickets requires approval of granularity and blockers before publication. Pending that review, these remain local GitHub-target drafts. The normal next step is publishing three spec issues and one issue per approved slice, with the ready-for-agent label and blocker references. Publication alone does not start execution.

