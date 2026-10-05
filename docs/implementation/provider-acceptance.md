# Subscription adapter and recovery acceptance

Audit date: **2026-10-05**. Isolated branch `build/provider-acceptance`, based
on `fdc2356dbd17757101927ba9b07bafc00847622f`. Scope: app-owned runtime
connections/auth/provider modules, focused runtime tests, this evidence.
Issues [#2](https://github.com/houraniiiii/Renulus/issues/2) and
[#5](https://github.com/houraniiiii/Renulus/issues/5), their evidence and S0/S1
acceptance were reviewed. Existing runtime and Learn baseline: 67 checks passed.

No real account sign-in, authorization URL opening, token exchange, model
catalogue request, generation or revocation occurred. HTTPX MockTransport owns
every subscription request in the new checks; a socket guard permits only
loopback. RSA-signed synthetic identities, actual SDK/Hermes wire conversion,
Windows DPAPI, SQLite and local ASGI/loopback routes provide offline evidence.
No other app credentials or private profiles were read.

## Official contracts

The exact allowlist remains unchanged:

| Connection | Model IDs | Fixed endpoint |
| --- | --- | --- |
| Codex / ChatGPT plan token | `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6-luna` | `https://api.openai.com/v1` |
| OpenCode Go / explicitly entered subscription key | `mimo-v2.6-pro`, `deepseek-v4.1-flash` | `https://opencode.ai/zen/go/v1` |

Official model pages document the three OpenAI IDs:
[Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[Astra](https://developers.openai.com/api/docs/models/gpt-6-astra),
[Luna](https://developers.openai.com/api/docs/models/gpt-6-luna).
Their existence does not establish plan/account availability. The official
[models/inference contract](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
requires the account catalogue and sharing eligibility. Renulus intersects the
catalogue with its five selected IDs; hidden/extra models cannot become routes.

The official [sign-in contract](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
specifies S256 PKCE, state/nonce, dynamic registration, v1 resource, plan usage
and `resource.invoke` scopes. It accepts UUIDv4 URNs, JWK-thumbprint URNs or
`did:key` for `ext_agent_host_id`; the previous default hex ID was invalid.
[Accounts/sessions](https://developers.openai.com/siwc/token-sharing-open-source/accounts-and-sessions)
requires stable app/account/host registration across sign-out/reconnect and
preserving refresh state after transient failures.
[Errors/recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)
distinguishes auth, plan budget, unavailable models and transient service errors.
[Responses streaming events](https://developers.openai.com/api/reference/resources/responses/streaming-events)
includes direct `error` and nested `response.failed` errors.

Official [OpenCode Go documentation](https://opencode.ai/docs/go/) lists both
selected models and compatible chat-completions routes. The final fresh page
describes coding-agent traffic and asks for an app-specific User-Agent plus a
stable `x-opencode-session` header per conversation; it does not explicitly ban
non-coding use. It identifies newer Hermes builds containing a session-header
fix as validated clients. **Renulus learning-use eligibility is unresolved.**
The controlled Renulus Go adapter still needs its own identity/session-header
integration after that eligibility review; the upstream validation cannot be
claimed for this adapter. No client identity was fabricated and no alternative
provider/model was introduced. Transport/schema tests do not prove Go
subscription acceptance for this product. The earlier coding-policy summary
was relayed to parent and this narrower final reading corrects it:
[#1](https://github.com/houraniiiii/Renulus/issues/1#issuecomment-5985964094).

## Fixes and offline evidence

| Reproduced problem | Implemented behavior / meaningful check |
| --- | --- |
| Disconnecting an unused connection cancelled another subscription's active run. | Cancel only runs belonging to the disconnected provider; a pending Codex stream completes after Go disconnect. |
| Old catalogue success/failure overwrote a disconnected/reconnected account. | Volatile connection revisions guard commit of async results; controlled old 200/401 replies cannot alter current status, catalogue or protected credentials. |
| Login cancellation left token/JWKS/catalogue requests running; expiry ignored exchange. | Own and cancel the exchange task; close listener and clear PKCE state. Token, JWKS and catalogue cancellation plus exchange expiry stop without saving credentials. A new login can supersede an exchange safely. |
| Stop did not interrupt generation waiting for a token refresh. | Token access is part of the cancellable run; stopping it produces one cancelled terminal, closes the request and does not invoke generation. |
| Codex SSE auth/quota/model errors lost their machine code. | Whitelisted direct/nested codes produce redacted actionable errors; auth invalidates stale catalogue, model rejection blocks replay, quota does not become an image capability claim. No retry or subscription/model fallback. |
| Sign-out lost the account/client mapping. | Drop tokens but retain only issuer/subject/client registration in the existing DPAPI record. Restarted reconnect uses the same host/client; public status never contains registration or tokens. |
| Default host identity did not meet the documented protocol. | New profiles use persistent UUIDv4 URNs. Unregistered legacy profiles upgrade before login; registered invalid identities fail with `host_identity_invalid` and their protected file remains byte-for-byte unchanged. |
| Refresh accepted incomplete grants, blank/non-bearer tokens and non-finite expiry; transient failure was labelled auth. | Reuse initial/refresh token validation, require both plan/resource scopes, preserve original credentials on rejection, rotate valid tokens durably. A 503 remains retryable provider unavailability and its original refresh token survives. |
| Live provider recovery had only a test provider at Learn level. | Actual SDK + local ASGI + SQLite tests inject 401, 429 and offline failures. Each retains its study input and failed run, survives app restart and completes an explicit retry in the same thread with the same selected model. These are controlled responses. |

The protected-record version remains 1; `codex_registration` is additive. No
SQL migration, shared API, root dependency, renderer or upstream source edit is
needed. Source attribution and the immutable Hermes baseline remain intact.

## Validation and remaining acceptance

Focused new acceptance suite: **30 passed**. Combined runtime/auth/provider,
image/context, DPAPI/helper boundaries, Hermes provenance and Learn checks:
**104 passed** on the integration CPython 3.14 environment. `git diff --check`
passed. The existing Starlette/httpx deprecation warning is unrelated to these
changes. No heavy helper model or native installer proof was repeated.

Reproduce from this checkout with `PYTHONDONTWRITEBYTECODE=1`,
`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`:

```text
python -m pytest tests/runtime/test_provider_acceptance.py tests/runtime/test_provider.py tests/runtime/test_auth_api.py tests/runtime/test_codex_stream.py tests/runtime/test_images_context.py tests/runtime/test_protected_helpers.py tests/runtime/test_hermes_provenance.py tests/learn -q --basetemp .local/runtime/provider-acceptance/final --tb=short
```

Achieved: runnable offline disconnected behavior, exact allowlist enforcement,
synthetic signed login/retry/cancel/expiry, protected restart/token rotation,
actionable provider failures, controlled thread retention/retry and existing
temporary-case no-save/context/image boundary checks. Synthetic completion
keeps `live_provider_verified=false`; production contains no canned response.

Unproved: real user-owned registration/consent/refresh/revocation, account model
availability, actual streamed response/cancel for either subscription, live
image interpretation, plan budget behavior, and Go learning-use eligibility
with truthful client/session headers.
Existing registered legacy host identities need deliberate recovery rather than
automatic rebinding. Multiple ChatGPT accounts and published plan-gate recovery
paths have not been fully accepted. **#2/#5 must not be closed as live-provider
complete on this offline evidence.** Parent integration needs this scoped commit
and its focused checks; no additional module wiring is required.
