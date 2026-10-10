# W4-03 — Current conversations, retention and OpenCode adaptation

2026-10-10. Research only; no product changes. Research checkout baseline: `528025ff0b22477c12ee1512e0e7d15297a6e888`. Executed source: **`76cfdff23e259700bec820e174c200540c7c1e1b`**, using the frozen public-source snapshot identified in the [current source map](current-source-map.md). Fifteen inspected source/test files matched `git show` at that commit after LF normalization. Below, `76cfdff:path` denotes that commit's repository path. Required project documents, the [side-chat findings](../2026-10-10-pi-opencode-v2-side-chat-findings.md), [W3-04](w3-04-host-proof-adversary.md) and [W3-01](w3-01-migration-retention.md) were read.

**Result:** the existing conversation facade is the correct integration boundary. **25 selected cases passed**, while an additional isolated reproduction confirmed deleted draft payloads remain in command receipts and new exports. The older generic deletion-cascade finding is fixed for the exercised typed relations. OpenCode itself was not executed.

**Runtime evidence.** Tests use fresh synthetic profiles, in-process FastAPI clients and scripted `ConversationProvider`/`PausedProvider` implementations. Dispatching cases disable retrieval/memory as specified in their fixtures. No private profile, credential, live provider, install, service or deployment was used. Memory-capture and generation/nightly suites were excluded. Sources: `76cfdff:tests/integration/test_design_c_conversations.py` ([map 23](current-source-map.md#source-23)) and `tests/integration/test_design_c_migration.py` ([map 24](current-source-map.md#source-24)), both at the current commit.

| Executed coverage | Cases | Observed result |
| --- | ---: | --- |
| Saved defaults/drafts, failed/successful sends, replay | 5 | Both kinds retain original owner identities; failed drafts survive; successful replay after restart makes no provider request; active Test blocks command replay. |
| Temporary multi-turn, subscription close, attachment deletion | 5 | Both kinds retain follow-up context without profile/export sentinels; disconnect cancels; temporary case attachment bytes/upload receipts are discarded. |
| Explicit Save and attachment rollback | 3 | Both kinds preserve identity/history exactly once; failed case attachment promotion retains the volatile original and retry commits. |
| Saved disconnect/Stop and restart | 3 | Saved producers finish after subscription close; Stop preserves completed state; orphan receipt becomes interrupted with draft retained and no dispatch. |
| Context/policy epochs | 3 | Context change rejects late assistant publication for both kinds; an old policy revision remains invalid after Test submission. |
| Typed restore, migration and cleanup | 6 | Shared document/revision survives project deletion; removed membership stays removed; schema-one conversion is explicit/repeatable; restore dirties indexes/increments context; deferred attachment cleanup drains on restart. |

The “segmented” relation case invokes its pruning helper, not a complete ZIP restore. Temporary file scans prove absence of their tested markers, not universal memory/crash-dump erasure. Restore capture barriers were inspected statically; capture execution was deliberately excluded. Existing `Recovery.mutation` and `invalidate_restored_context` must be extended, not recreated. Sources: `76cfdff:runtime/renulus/storage/{relations.py,recovery.py,invalidation.py,compatibility.py}`, [map 14–19](current-source-map.md#source-14).

**Exact test invocation and output.** From the frozen snapshot, PowerShell piped an ephemeral runner to `& 'C:/Renulus/dev/python/Scripts/python.exe' -B -`. It set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, inserted `cwd/runtime`, rejected socket connects except inside Windows' internal `socketpair`, and replaced real `ProviderManager.stream/compact` with refusal functions. Its exact pytest call was:

```python
selection = 'saved_default_chat or saved_wrapper_send or temporary_multi_turn or context_change_during_reply or explicit_save_promotes or saved_producer_outlives or restart_reconciles or temporary_subscription_close or saved_command_replay or (chat_attachment_save_rollback and case) or (temporary_chat_delete and case) or owned_attachment_cleanup_pending or policy_revision_blocks or project_link_deletion or schema_one_populated_json or restore_invalidates_derived or unlinked_membership_tombstone'
pytest.main(['-q', '-x', '-p', 'no:cacheprovider', '-p', 'pytest_asyncio.plugin',
    '--basetemp', 'C:/Users/karol/AppData/Local/Temp/renulus-w4-03-pppo1v2b/cases',
    'tests/integration/test_design_c_conversations.py',
    'tests/integration/test_design_c_migration.py', '-k', selection])
```

```text
25 passed, 25 deselected, 1 warning in 121.40s (0:02:01)
BOUNDARY_COUNTS {'blocked_network': 0, 'blocked_provider': 0}
```

The warning was Starlette's installed `httpx` TestClient deprecation; nothing was installed. An initial overbroad socket guard produced failures and was interrupted before a summary. A standalone `asyncio.new_event_loop()` reproduction established that it blocked Windows' internal pair; those failures are harness evidence, not product failures. The corrected run above completed with exit 0.

**Executed remaining defect.** A second `python.exe -B -` runner created only `C:/Users/karol/AppData/Local/Temp/renulus-w4-03-residue-espdu0g9/synthetic-profile`, without app lifespan/workers. For each kind it called `create(NewConversation(...))`, `save_draft(..., old_marker, old_key)`, `save_draft(..., replacement_text, new_key)`, then `delete(..., latest_revision, delete_key)`. It queried the owner, sidecar, deletion ledger and `conversation_commands`, then called `export_records`. Only synthetic rows/export text were inspected; network connects were blocked after allocating asyncio's internal pair.

Both `learning` and `case` produced this asserted result:

```text
owner_rows=0; sidecar_rows=0; tombstoned=True; receipts=3;
marker_receipts=1; marker_in_export=True; payload_hash_retained=True
```

Markers were `SYNTHETIC_W4_03_DELETED_DRAFT_LEARNING` and `SYNTHETIC_W4_03_DELETED_DRAFT_CASE`. `command()` serializes draft results; deletion removes owners but does not retire prior receipts; `COMMON_TABLES` explicitly exports the ledger. This confirms W3-01's static defect at current code. It does not establish physical SQLite/WAL or full ZIP erasure. Sources: `76cfdff:runtime/renulus/learn/conversation_repository.py` ([map 09](current-source-map.md#source-09)) and `runtime/renulus/storage/backup.py:23` ([map 13](current-source-map.md#source-13)).

**Minimal adaptation — proposed.** Extend [H06](../../planning/opencode-v2/tickets/06-continue-saved-and-temporary-chats-through-one-owner.md) in the existing DC04 owner:

1. Keep conversation IDs, kind/retention/lifecycle, drafts, project membership, pagination and attachment ownership. Add an execution-owner/store/session mapping to existing sidecars. Adapt `ConversationStreams.begin/events/status/cancel/close` to upstream execution; receipts become references/projections rather than another execution log. Freeze legacy transcript writers and Hermes compaction at handover; preserve readable historical IDs/citation pins. No dual writable transcripts or second conversation subsystem. Source: `76cfdff:runtime/renulus/learn/conversation_stream.py` ([map 10](current-source-map.md#source-10)).
2. Carry existing policy revision/context epoch into admission, tool execution and publication; reject stale work after project move, Test transition, deletion or restore. Keep neutral run status and explicit Stop accessible. Migrate legacy running receipts as interrupted, never silently resubmit them. `76cfdff:runtime/renulus/{learn/conversation_stream.py,study/project_repository.py,storage/assessment_policy.py}` supplies these existing guards ([map 10](current-source-map.md#source-10), [12](current-source-map.md#source-12), [22](current-source-map.md#source-22)).
3. Retire payload-bearing receipts transactionally with deletion: remove result text and payload digests, preserve opaque operation identities, return terminal-unavailable on replay. Resolve live results by canonical reference. Include creation receipts whose current `target_id` is `new`, using their actual resulting owner identity; filtering only by target ID would miss their titles. Reuse the existing ledger and typed restore contracts.
4. Place the entire temporary parent/child family in a separate volatile runtime graph. Instance keys inherit host replacements and do not select separate storage. Replace disk-spilling tool output and attachments with volatile services. Explicit Save must settle children, stage the retained family/originals, commit one mapping, and retain the volatile source on failed promotion. Current single-store Save tests do not prove that cross-store transfer. [Instances](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/instances.ts), [tool-output spill](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/tool-output.ts).

**Next-wave gates.** OpenCode source remains **`4b6fea2875e4f2e3e8a8fee181803e54f7056845`**; [SDK 2.0.26 metadata](https://registry.npmjs.org/@opencode%2Fsdk/2.0.26) declares Effect `4.0.0-rc.112` and belongs to the distinct `9b4ec5714d481559990db0a816d5dec19541a814` tag. Public metadata was fetched; no package was installed.

At the selected source, [host construction](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/host.ts) registers plugins before forking recovery. Revalidate W3-04 with an actual embedded scripted host: recovery's [child list](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution/restart.ts) omits live foreground children from the exceptions supplied to [claim cleanup](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/store.ts). Require quiescence or proven eligibility filtering before opening delayed recovery. This is independently rechecked source evidence, not an executed OpenCode race.

H06 must prove the receipt fix, saved/temporary child disconnect and atomic Save under injected failure. [H18](../../planning/opencode-v2/tickets/18-delete-and-restore-a-consistent-migrated-learning-profile.md) must extend the existing recovery barrier to both stores, apply current tombstones before activation, and scan events, summaries, child sessions, spills, WAL and new JSON/ZIP exports. Upstream [recursive session removal](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session.ts) is reusable but does not prove this complete boundary. Current selected defaults remain; future opt-in vLLM/Ollama/providers must obey the same retention and epoch rules without required setup.
