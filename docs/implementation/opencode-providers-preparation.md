# H03 provider adapter preparation

2026-10-11. Providers lane, codex/oc-h03-providers, based on
74e3424b5c03ac4616834911c13faef1c064d09c. This is independent preparation,
not H03 acceptance. The parent reports actual-store activation prerequisite
96a29d11861f901bded2ea46c81cb20f948a194b; it is not included in this lane.
H02, connected final admission/budget enforcement, actual account/tool/image
acceptance and packaged acceptance remain downstream gates.
The parent subsequently reported configuration authority a85e1ee0 and native
Library/input/recovery prerequisites through def4b12b. Those parent changes are
not copied into this lane; the parent assembles them with this provider seam.

## Public gateway and selector interfaces

SubscriptionRoute in runtime/renulus/runtime/provider_adapter.py is frozen:
provider_id, catalog_model_id, wire_model_id, endpoint, protocol, credential_ref,
credential_epoch and advisory catalogue_listed. Its descriptor() contains no
credential or input. Reconstruct a trusted IPC descriptor using
SubscriptionRoute(**descriptor). References are opaque and process-local;
reopening creates new references so old descriptors cannot revive.

ProviderManager exposes these public methods:

    await prepare_harness_route(model: str | None = None) -> SubscriptionRoute
    require_harness_route(route: SubscriptionRoute) -> None
    harness_capabilities(route: SubscriptionRoute) -> dict
    await credential_for_harness(route: SubscriptionRoute) -> str
    observe_harness_result(route, *, code: str, images=False, tools=False) -> None
    observe_harness_error(route, error: Exception, *, images=False) -> ApiError
    observe_harness_stream_error(route, code: str | None, *, images=False) -> ApiError

Preparation preserves the selected provider, explicit/saved model and existing
Automatic ordering. Pass the already-resolved model from the parent's single
selector. There is no new role ranking, fallback, catalogue or inference probe.
An expiring existing OAuth token can refresh during preparation.

require_harness_route is synchronous, performs no IO and grants no admission.
Use it immediately before IO and after response/settlement, alongside the
parent's configuration/purpose/scope revocation checks. credential_for_harness
revalidates before and after protected lookup; token rotation invalidates an
old route instead of silently replacing it. The returned token is for trusted
Python dispatch only; never serialize it to Node, session/configuration or UI.
H04 durable permits, role binding and configuration revocations remain parent
authority. Credential-route validity alone is insufficient admission.

The capability report contains the route, model ID, availability, current
catalogue visibility, documented support, effective text/image/tool input,
evidence labels, epoch and image_interpretation_verified=False. Existing Codex
documented text/image support stays separate. Go and tool documentation remain
unknown. Catalogue membership proves neither modality nor tools. Observations
belong to a credential epoch. Transient catalogue failure can retain same-epoch
observations with unknown availability; 401 clears observations and advances
the epoch. Old completions/errors cannot affect a fresh epoch. A 401 blocks
dispatch until explicit refresh/reconnect, preserving the selected subscription.

Only the trusted parent observes completion after native terminal settlement.
tools=True means a completed tool-call/result continuation; images=True means
required images were actually sent. A 200 handshake is not completion. Error
APIs return existing redacted ApiError forms and record only known machine
codes. Do not log exception bodies or input payloads.

The native module packages/harness/src/provider-adapter.ts exports:

    createSubscriptionAdapter({ route, sessionId, dispatch, validateImages? })
    // -> { providerId, modelId, model, client: LLMClientShape, configuration, close }
    dispatch: (route, HttpClientRequest) => Effect<HttpClientResponse, AIError>
    validateImages?: (readonly InlineImage[]) => Effect<void, AIError>

It fits the existing ModelAdapter shape, using actual pinned LLMClient.layer,
public RequestExecutor.Service and native Chat/Responses protocols with
Auth.none. There is no default executor or credential discovery. dispatch
receives the actual serialized POST after identity/input validation. It must
use parent-owned reverse IPC, final serialized input/output/window bounds,
durable permits at dispatch commitment, Python credential injection, no
redirects, bounded raw SSE bytes, and current revocation checks. No automatic
retry/fallback, WebSocket, middleware override or native compaction is enabled.

validateImages is mandatory when the final body contains images, and runs before
dispatch. Missing/failed validation causes zero dispatch. Invoke public Python
validate_harness_images(images), reusing existing validate_inputs and managed
Pillow in memory. InlineImage has type=image, media_type=image/png|image/jpeg|
image/webp, and base64 data. Physical validation checks format, file validity,
one frame, 16,000,000 pixels, four images, 8 MiB each and 16 MiB combined. Node
also checks inline MIME/magic/base64, user role, 200 messages and one million
input characters. The parent's token/output/window gate remains mandatory.
The configured 32,768 context / 4,096 output values are bounded preparation
settings, not measured account/model context claims.

| Provider | Exact catalogue = wire IDs | Protocol | Endpoint |
| --- | --- | --- | --- |
| codex | gpt-6.1-sol, gpt-6-astra, gpt-6-luna | openai-responses | https://api.openai.com/v1/responses |
| opencode-go | mimo-v2.6-pro, deepseek-v4.1-flash | openai-chat | https://opencode.ai/zen/go/v1/chat/completions |

Only local function tools with complete, unique, correctly named call/result
pairs are admitted. Hosted/native tools, provider-executed results, body/query
overlays, credential headers, retention, truncation and opaque compaction/replay
controls are refused. Recognized upstream session headers are reconstructed;
project paths and caller header values are discarded. Raw errors, provider
metadata and finish diagnostics do not enter transcript-facing output.
Normalized usage and native tool content remain. Encrypted reasoning metadata
and native replay are not adopted by this narrow preparation module.

## Ownership, evidence and limitations

Owned changes: runtime provider manager and new provider_adapter.py; native
provider-adapter.ts; tests/runtime/test_provider_acceptance.py and new
test_provider_adapter.py; native provider-adapter.test.mjs and dedicated
fixtures/provider-environment.mjs; this note. Standards/spec review is local,
without subagents. No shared contracts, database/migrations, Services assembly,
host, production entry, harness process/profile, locks or tickets/status changed.

All receipts/profiles are under C:/Renulus/scratch/oc-h02-h08/providers.
Red/green receipts in receipts/: c01-c15 cover inherited discrepancies and
route/input/transport boundaries; c17 refresh-401; c18 route-bound observations;
c19 mandatory final image decoding; c20 physical image limits; c21 public
gateway errors/revalidation; c22 hosted/retention/compaction/truncation denial;
c24 metadata canaries. Intermediate fixture/syntax failures are retained.
c14-green-02.xml is the successful diagnostic-redaction receipt.

c16-harness-06.xml proves saved synthetic Harness text turns for all five IDs
through the pinned SDK, SQLite and actual native LLMClient. Native roundtrip
receipts c23-native-roundtrip-02.xml and c24-continuation.xml prove emitted tool
calls, results and text continuation on both protocols, with the managed Python
decoder and two counted HTTP requests per round trip. c24-green.xml retains an
intermediate decoder timing failure during concurrent runtime checks; the
successful continuation and final suite determine the final result. Synthetic
canary values are not printed into red failure receipts.

The cohort/provenance is unchanged from upstream/opencode/UPSTREAM.md: source
4b6fea2875e4f2e3e8a8fee181803e54f7056845, source-built 2.0.26 packages. The
ignored packages/harness/node_modules junction targets
C:/Renulus/scratch/ocf/cohort/node_modules. Managed Node is
C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe, SHA-256
3193d7f751b8a07bd4acc70e81946ae9c6efdee83e07ad1c8d0e4089df7c5cef.
Managed Python is C:/Renulus/dev/python/Scripts/python.exe. No acquisition,
cohort replacement, private profile, account, provider charge or push was used.

At this lane's baseline, the H01 saved facade exposes text-only submit and no
eligible domain tool-registration seam. The parent's newer native Library/input
prerequisites must be connected to this adapter and the gateway above in H02.
Native adapter/client proofs do not establish connected saved domain tool/image
execution, account access, image interpretation or packaged Windows delivery.
H03 remains unaccepted until those gates land.

## Final validation commands and receipts

From the assigned checkout, managed Python ran:

    RENULUS_HARNESS_NODE=C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe
    C:/Renulus/dev/python/Scripts/python.exe -m pytest tests/runtime
      --basetemp=C:/Renulus/scratch/oc-h02-h08/providers/final-runtime
      --junitxml=C:/Renulus/scratch/oc-h02-h08/providers/receipts/final-runtime.xml
      --tb=line -q

Result: 232 passed, one failure in the protected parent-owned
test_concurrent_start_cannot_launch_two_children_for_one_transport. Both starts
missed its 0.5-second readiness deadline during the sweep. Its isolated rerun
passed (final-start-rerun.xml), using the same test, no edits, and basetemp
final-start-rerun. This is not a claim that the broad sweep was entirely green.
All four inherited provider discrepancies and the seven new Python adapter
cases passed in the sweep; c21-green.xml separately records the seven new cases.

From packages/harness, the pinned Node executable ran:

    node --import ./test/fixtures/provider-environment.mjs --test
      --test-concurrency=1 --test-timeout=45000 --test-reporter=junit
      test/*.test.mjs
    node node_modules/typescript/bin/tsc --noEmit

Result: 28 native tests passed, including 15 dedicated adapter tests, with no
skips (final-harness-02.xml; final-harness.xml also passed). Typechecking returned exit code 0
(final-typecheck.log). Preloading the owned environment keeps baseline native
test temp roots in this lane. The tool/image decoder proof has an explicit
90-second test deadline and 30-second managed child deadline, avoiding the
earlier ten-second child deadline under concurrent import load. No product
timeouts or provider retries were changed.

## Exact retained four-case red/green ledger

four-baseline-red.xml contains four failures from original test and manager
snapshots at 74e3424b5c03ac4616834911c13faef1c064d09c. Only public tracked
source snapshots were materialized in the lane scratch directory; no checkout,
working files or private profile were changed. prepare_baseline_receipt.py in
the scratch root records the reproducible snapshot loader. Dependencies and
AppPaths source root remain this assigned checkout.

four-current-green.xml contains four passing cases from this lane's current
source, using the same filter. Exact cases and changes:

| Test node ID | Baseline red | Current green |
| --- | --- | --- |
| tests/runtime/test_provider_acceptance.py::test_sdk_stream_machine_failure_is_redacted_actionable_and_has_no_retry[invalid_api_key-authentication_required-error] | Account availability incorrectly available after 401 | Account availability unknown; selected subscription unchanged |
| tests/runtime/test_provider_acceptance.py::test_sdk_stream_machine_failure_is_redacted_actionable_and_has_no_retry[invalid_api_key-authentication_required-response.failed] | Same discrepancy for response.failed frame | Same corrected invalidation for response.failed |
| tests/runtime/test_images_context.py::test_inference_auth_failure_invalidates_catalogue_without_image_claim | Effective inputs remained supported after access invalidation | Effective inputs unknown; no image capability claim from failed access |
| tests/runtime/test_provider_acceptance.py::test_transient_refresh_failure_preserves_rotating_token_and_is_retryable | Stale assertions demanded unknown documented support and unavailable unlisted model after recovered refresh | Assertions now preserve documented support and distinguish advisory catalogue visibility from account access |

The fourth case intentionally corrects an inherited expectation rather than
erasing documented modality on a successful recovered refresh. Its stronger
evidence assertions, plus c18's transient failure/epoch observation test, retain
the distinction between access, documentation and observed capability.

Exact current command (the baseline command substitutes the two scratch snapshot
test files and uses -c pyproject.toml):

    C:/Renulus/dev/python/Scripts/python.exe -m pytest
      tests/runtime/test_provider_acceptance.py tests/runtime/test_images_context.py
      -k 'invalid_api_key or transient_refresh_failure or inference_auth_failure'
      --basetemp=C:/Renulus/scratch/oc-h02-h08/providers/four-current-profiles
      --junitxml=C:/Renulus/scratch/oc-h02-h08/providers/receipts/four-current-green.xml
      --tb=line -q
