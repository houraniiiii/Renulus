# Native saved-answer extraction preparation — 2026-10-11

This bounded fixture proves native saved-answer resolution and the existing real
Mem0/Qdrant/FastEmbed lifecycle with synthetic inference. It does not close H05
or the H04/gateway integration gate. The parent owns production composition.

## Scope and prerequisites

Only `tests/runtime/test_harness_learning_extraction.py`,
`packages/harness/test/fixtures/learning-extraction-host.mjs` and this note change.
No production runtime, host, IPC, Services, Memory/Learn, schema or shared fixture
is changed. No descendants were created.

The worker baseline is `b7928e0f92e477c6869476f1fdf0d51bf14dd558`; it does not
contain the parent's LearningOwner composition. The verified source root was
`C:/Users/karol/.codex/worktrees/opencode-foundations/repo`, HEAD
`d6d4a2be151ea44f1ac44f3f2586cc5914f73a10`, including the then-uncommitted
LearningOwner, native context and terminal composition. Eighteen selected source
files were hashed before and after the final run, with no changes during that
run. The complete identities are in these receipts:

- `C:/Renulus/scratch/oc-h02-h08/learning-extraction/receipts/source-before01.json`
- `C:/Renulus/scratch/oc-h02-h08/learning-extraction/receipts/source-after01.json`

These prerequisites must be present in the consuming checkout. Running against
the worker's older runtime intentionally does not substitute another owner: the
initial prerequisite receipt fails with missing `renulus.runtime.harness_learning`.
For verification before publication, `RENULUS_LEARNING_SOURCE_ROOT` explicitly
selects the owned parent's source. Use that checkout's pytest configuration too.
The test carries this explicit root in fixture-only boot settings because the
managed subprocess correctly strips inherited environment variables.

The selected actual packages were Mem0 2.2.1, qdrant-client 1.19.1, FastEmbed
0.8.1, ONNX Runtime 1.30.0 and tokenizers 0.23.2, on Python 3.14.4 and Node
26.4.0. The existing helper validator checks the explicitly selected public
`C:/Renulus/dev/helper-assets` embedding group: BAAI/bge-small-en-v1.5, 384
dimensions, two CPU threads and local files only. The helper manifest SHA256 is
`7d5375bf81d4c4dc3c5a9b6a1304d99286f465998a4e23ecc4da5a8103dcfa7d`.

## Connected seam and observed results

Each profile uses its existing `create_app`/MemoryService and
`HarnessLearningOwner.install()`. Public conversation `begin`/`events` publishes
the native completed-answer reference through the actual owner's canonical
publication hook. The fixture never synthesizes evidence or publishes lineage.

Both IPC peers have one data slot and one domain callback slot. The native
scripted model produces one accepted saved answer, and the parent records its
actual user input and assistant message identities. The exact consumed pin is
the original manual memory revision, classified `saved`/`general_learning`; the
resolved input manifest includes that same revision in the dependency closure.
The runtime profile/store/cohort, answer digest and publication digest are
checked. A foreign store reference is refused by the public resolver.

The fixture holds an actual native observation without replacing its returned
bytes. While it occupies the sole data slot, `Database.quiesce_writes()` and a
real `BEGIN IMMEDIATE` transaction succeed, and a reserved `host.status` control
reply reports the held read. Resolving returns the exact known native answer
bytes and pinned manifest.

Explicit `memory.enqueue`/`process_pending` then runs the unchanged real Mem0
extractor, local Qdrant and offline FastEmbed. Only external inference is
synthetic: a real `ProviderManager` receives an injected transport and synthetic
catalogue. Its completed request is the original capture job, purpose
`memory-extraction`, selected `opencode-go`/`mimo-v2.6-pro`, one dispatch. Input
contains the selected native answer and excludes the user's prompt. The native
model count remains one. Native automatic answer capture stays disabled.

The first tracer recalls the generated fact, edits it to revision 2, observes
corrected recall, deletes it, and reopens both owners over the same synthetic
profile. Original native messages remain readable through the public history
interface. Suppression makes the answer resolver ineligible for extraction;
explicit enqueue and retry cannot recreate the fact, and reopen performs zero
inference. Historical readability is distinct from extraction eligibility.

The meaningful failure case changes the original support revision while the
actual Mem0 CPU worker waits on synthetic inference. The job is cancelled with
`memory_dependency_revoked`. Close times out and recovery reports `recovery_busy`
until the controlled inference/finalizer is released. Native IPC control remains
live throughout. After real worker/engine settlement, reopen and retry admit no
stale fact and no inference. Each teardown separately checks actual process/pipe
settlement and zero active domain owners.

## Verification and reproduction

Receipts under `C:/Renulus/scratch/oc-h02-h08/learning-extraction/receipts`:

- `tracer05.xml`: connected lifecycle, 1 passed in 21.50 seconds.
- `revocation01.xml`: held-worker revocation, 1 passed in 19.91 seconds.
- `final01.xml` / `final01.txt`: both cases, 2 passed in 34.39 seconds; no skipped
  cases. One existing Qdrant warning states that payload indexes have no effect
  in local mode; the fixture uses the selected local engine.
- Node `--check`, Python compilation and `git diff --check` passed.

Earlier `tracer-red01`/`tracer01` receipts establish missing production
prerequisites/fixture startup, not a repaired production defect. `tracer02` and
`tracer03` corrected test expectations to include the existing typed
classification and dependency closure. `tracer04` corrected the mistaken
expectation that a suppressed answer remains eligible for extraction on reopen.
No production red-to-green repair is claimed by this test-only commit.

From the parent checkout, before picking this fixture into it:

```powershell
$env:RENULUS_LEARNING_SOURCE_ROOT = 'C:/Users/karol/.codex/worktrees/opencode-foundations/repo'
$env:RENULUS_HARNESS_NODE = 'C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe'
$env:RENULUS_MEMORY_HELPERS = 'C:/Renulus/dev/helper-assets'
& 'C:/Renulus/dev/python/Scripts/python.exe' -m pytest -c 'C:/Users/karol/.codex/worktrees/opencode-foundations/repo/pyproject.toml' 'C:/Users/karol/.codex/worktrees/oc-domain-ipc/repo/tests/runtime/test_harness_learning_extraction.py' -q --basetemp='C:/Renulus/scratch/oc-h02-h08/learning-extraction/reproduce' --junitxml='C:/Renulus/scratch/oc-h02-h08/learning-extraction/receipts/reproduce.xml'
```

After composition, run the picked test in the parent's normal checkout. The
source-root override is then unnecessary. Tests do not acquire models, use
accounts or open remote sockets. Each run owns synthetic state/indexes and uses
the explicitly selected public helpers.

## Remaining shared seam and IPC error proposal

`memory/providers.py:ApprovedLLM.generate_response` still calls the existing
ProviderManager stream. This fixture does not prove extraction inference via
native SDK prompt/continuation or gateway dispatch accounting. The missing
composition must admit the existing capture job/purpose with its current
revision/cancellation authority, route its one inference through the parent's
gateway, and preserve the existing CPU/reply-loop settlement. A second runtime,
canonical writer, schema or per-child memory worker is not proposed.

The parent reported an internal-error propagation P2. Source inspection agrees:
LearningOwner `_current` catches every `ApiError` and returns false; the parent
owns that predicate repair. Independently, `harness_domain.py:publication_wire`
and duplicate-result admission catch every exception and translate it into
`domain_cancelled`. The initial handler runner already sanitizes `ApiError`, but
the pipe-publication check can overwrite that error. Transport remains unchanged.

Proposed bounded public red at existing ManagedHarnessProcess/DomainGrant seams:

1. A trusted `check_current` raises
   `ApiError('memory_support_budget', 'SYNTHETIC_PRIVATE_ERROR_CANARY', 409, False)`
   before work. Expect the peer's domain result and `domain_result` to retain
   exactly `{code:'memory_support_budget',status:409,retryable:false}`, no handler
   effect/result, no private message or traceback, and a live control channel.
2. Use the existing owned subprocess's paused-read/pipe-backpressure fixture.
   Let the handler settle once, then change only the trusted predicate to raise
   that error while its result waits for pipe capacity. The peer must receive
   the same sanitized internal error and no payload. An exact duplicate callback
   must retain it without re-executing the handler.

The bounded transport proposal is to distinguish actual DomainCancelled/Stop
from `ApiError` and unexpected internal failures at publication and replay,
reuse the existing bounded error representation, and retain handler ownership
through settlement. Keep false-current/explicit cancellation as cancellation;
preserve internal errors instead of granting authority or reporting a stop. No
new outcome/schema or transport edit is included here.

The full four-case H05 lineage matrix, native extraction gateway, H04/account
activation, other consumed source/tool/summary closures and packaged Windows
acceptance remain parent-owned and open.
