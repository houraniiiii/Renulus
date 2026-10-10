# W5-04 — Independent current-defect verification

2026-10-10. Research/testing only; no product changes. Research/document baseline: `528025ff0b22477c12ee1512e0e7d15297a6e888`. Inspected/executed implementation: **`76cfdff23e259700bec820e174c200540c7c1e1b`**, frozen at `C:/Users/karol/.codex/worktrees/a11f/repo/.local/research/opencode-v2-current-76cfdff`. Documentation came from the research checkout. An independent `git ls-tree -r -z 76cfdff23e259700bec820e174c200540c7c1e1b -- runtime/renulus tests pyproject.toml` comparison, hashing Git blob headers plus file bytes, matched **365/365 blobs**. Current-source links below resolve into that snapshot; the canonical checkout was untouched.

**Independently reproduced guard defect.** AST inspection finds no bases, `guard_run`, or dynamic attribute hooks on `SavedGenerationService`. Its `_batch` passes itself to the shared helper; the helper's first statement calls the absent method. This precedes knowledge access, call-counter increment and provider dispatch. `_produce` catches that `AttributeError` and records `generation_failed`. Sources: [caller/catch/publication](current-source-map.md#source-05), [retrieval helper](current-source-map.md#source-26).

**Exact executed checks.** Both stdin runners used `& 'C:/Renulus/dev/python/Scripts/python.exe' -B -` from the snapshot; Python reported **3.14.4**. The first imported the actual class/helper and executed:

```python
loop.run_until_complete(retrieve(
    object.__new__(SavedGenerationService),
    SimpleNamespace(scope=ContextScope(kind=Scope.GENERATED_PRACTICE),
                    prompt='Synthetic nephrology learning', topic_id=None)))
```

Output: `AttributeError: 'SavedGenerationService' object has no attribute 'guard_run'`; asserted expected exception, exit **0**. No profile or provider object was created; network-attempt counter **0**. This deliberately uninitialised receiver isolates attribute lookup; it is **helper execution, not integration proof**.

The second runner set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, disabled bytecode/cache, denied socket activity except Windows' internal socketpair, and supplied a fresh synthetic temporary profile. Its exact invocation was:

```python
pytest.main(['-q', '-s', '-p', 'no:cacheprovider', '-p', 'pytest_asyncio.plugin',
    '--basetemp', 'C:/Users/karol/AppData/Local/Temp/renulus-w5-04-97wfbnsr/cases',
    'tests/assessment/test_saved_generation.py::test_real_selected_route_batches_publish_once_and_keep_keys_private[5]',
    '--tb=short'], plugins=[Observe()])
```

`Observe` only read the job row/transport counter after the test call:

```text
state=failed; error_code=generation_failed; calls=0; synthetic_transport_calls=0
1 failed, 1 warning in 4.59s
blocked_network=0; internal_socketpair=1; pytest_exit=1
```

The warning concerns Starlette/httpx. An initial attempt instead produced **1 setup error in 4.79s**: the runner mistakenly denied `_fallback_socketpair`. Correcting that allowance changed only the harness. Temporary profiles were removed by their owners. No broad suite was rerun.

**Failure semantics.** The [selected test](current-source-map.md#source-27) uses real migrations/services/SQLite/ProviderManager with `SyntheticTransport` and an artificial token. Six concurrent creates deduplicate, then line 101 fails at `state == published`. Later count, privacy and publication assertions are unexecuted. Thus [W4-02's](w4-02-current-workflows.md) 8 passes/16 failures cannot establish defective publication fencing. `_publish` already calls `_check` within its canonical transaction. Tests waiting for transport startup time out before exercising their intended revocation boundary. “Real selected route” does not mean a real account/model call.

**Memory audit: supported, bounded finding.** I inspected W4-01's retained `probe.py`, four JSON results and test logs, without rerunning them. Its four edit/delete cases use real Learn/Memory admission, worker and commit code, but replace answer generation, recall, extraction and reindexing. They show stale text can acquire a new canonical ID when supplied by those doubles; they do not measure extraction quality or test the assembled conversation facade/OpenCode. The source supports the explanation: [answer publication](current-source-map.md#source-28) omits consumed memory dependencies; [suppression/commit](current-source-map.md#source-11) checks source identities rather than inherited support.

[W4-01's](w4-01-current-memory.md) **80 distinct passing regression cases** combine 56 initial passes, 12 boundary cases and 12 successful short-profile reruns. Keep the initial 12 Qdrant failures visible; path sensitivity is observed, an exact OS limit is unproved. Some [capture tests](current-source-map.md#source-29) execute Mem0/local Qdrant with synthetic inference/embeddings; neither all 80 nor the four defect probes are full-engine acceptance.

**Receipt audit: source corroboration, no independent rerun.** [W4-03](w4-03-current-conversations.md) reports 25 passing synthetic API/service cases and a separate two-kind deletion reproduction. [Command storage/deletion](current-source-map.md#source-09) retains result JSON/request digests; [export](current-source-map.md#source-13) includes that ledger. Deleted-draft residue in new JSON exports is credible. This is not a physical WAL/ZIP erasure test; the segmented relation test invokes pruning, not complete restore. Existing typed relations and restore barriers must remain.

**Proposed gates, not implementation.**

- **H00 prerequisite to H12/H13/H17:** pass an explicit job/execution guard into shared retrieval, checking before/after awaits while preserving the legacy guard. Never supply a no-op. Recheck the five-question flow and affected W4 failures before moving execution ownership.
- **H05 prerequisite to enabling migrated automatic capture:** persist inherited dependency references and reject revoked support before extraction/commit, including historical follow-up. Epoch increments alone allow later scan/requeue. Preserve current global facts and case/temporary exclusions.
- **H06 prerequisite to saved-chat deletion/export acceptance:** transactionally retire receipt payloads/digests, retaining opaque replay tombstones. Include creation receipts targeting `new` through their resulting owner identity. **H18 migration acceptance** then covers both stores, children, events, spills, restore and new exports. These fixes need not block H01's isolated synthetic host proof.

**The absence of runtime OpenCode proof is stated honestly.** W4 states it, the [plan](../../planning/OPENCODE_V2_INTEGRATION_PLAN.md) explicitly separates current-domain tests, and [H01](../../planning/opencode-v2/tickets/01-run-a-persistent-headless-opencode-conversation.md) leaves actual SDK/store/reopen acceptance unchecked. I inspected the pinned [source host `4b6fea2`](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/host.ts), distinct [tag `9b4ec57`](https://github.com/anomalyco/opencode/blob/9b4ec5714d481559990db0a816d5dec19541a814/packages/sdk/src/internal/host.ts), and fetched [SDK 2.0.26 metadata](https://registry.npmjs.org/@opencode%2Fsdk/2.0.26): matching package cohort, Effect `4.0.0-rc.112`. These are static/public-artifact checks only. Future opt-in providers remain compatible with these gates; selected defaults and no required setup remain. No live provider/authentication calls, installs, service changes, deployment or private data were used.
