# F0 runtime evidence

October 4, 2026. Work is confined to the assigned runtime worktree and F0 write
set. Shared prerequisites fffa82c and 735bd2f were cherry-picked by explicit
orchestrator instruction. Renulus's sole remote remains origin.

## Source adoption

Commit c83b5549 retains the complete NousResearch/hermes-agent source layout,
17,259 files / 205,050,446 bytes, under upstream/hermes. The original MIT licence
and copyright remain. The source pin is
af90026aa09949579bd423d24def3d38f743cde0, committed October 4 at 13:49:41 UTC.
The explicit archive URL, SHA-256, source count and patch hashes are recorded in
[hermes-source.json](../../packaging/runtime/hermes-source.json).

Maintained main was 32172d4622195697e4f077976140d0ed0738318a at inspection,
27 commits ahead. Its intervening file list contained no transport/auth changes,
so the inspected research revision remains the update baseline. No upstream Git
remote was added. The archive is retained in ignored development acquisition
state. Upstream Git attributes retain their original checkout conventions.

Downstream patch R001 adds a context-local opt-out to provider lookup/discovery.
Upstream defaults remain unchanged. Renulus binds an explicit Hermes home and
that opt-out while importing and using actual ResponsesApiTransport and
ChatCompletionsTransport methods. The general AIAgent initializer, stock HTTP
gateway, tools, plugins, external credentials, persistent Hermes sessions,
request dumps, spillover and auxiliary-model resolver are not entered.

The desktop lane was notified and reuses source lifecycle modules under its own
ownership. F0 does not modify apps/desktop.

## Working interface and connection controls

The module exposes create_router(services) and registers one ProviderManager at
services.registry['provider'], with cleanup in services.on_shutdown. It consumes
the shared paths and contracts, and creates no server, database or migrations.
The shared stream interface returns text deltas with keyword scope, run_id,
model, system and purpose; cancel is async. Explain, case, generated practice,
memory extraction and compaction consume this same selected route. The runtime
router wraps it in ordered Event SSE with exactly one terminal event.

Provider/model pairs are exactly Codex gpt-6.1-sol/gpt-6-astra/gpt-6-luna and
OpenCode Go mimo-v2.6-pro/deepseek-v4.1-flash. Automatic choice intersects that
allowlist with the explicitly connected account's catalogue. Model overrides
are restricted to that subscription. No provider fallback, environment-key
discovery, implicit subscription switch, SDK retry or secondary model call occurs.

Connection records are Windows-user-bound DPAPI ciphertext with profile-bound
entropy; secrets are never returned by public routes. No credentials are read
from another app. Startup performs no connection discovery or inference and
reports disconnected honestly. A reloaded record is configured, with unknown
capabilities, until the user requests a refresh. Text input is supported; image
interpretation remains unverified and is not advertised as working.

Codex uses Renulus-owned dynamic registration, an opaque stable host ID, PKCE,
state/nonce validation, an ephemeral 127.0.0.1 /auth/callback listener, issued
client ID binding, signed RS256 OIDC validation and granted plan-use scopes.
The public Responses endpoint receives store:false and stream:true. Returning
sign-in reuses the issued client ID; the optional ID token hint is omitted to
avoid exposing it to the UI. Token refresh remains within this connection;
disconnect drops local credentials and attempts renewable-session revocation.
Go accepts only a deliberately entered subscription key and checks its catalogue.

Public routes under /api/v1:

- GET /connections; POST /connections/select with provider.
- POST /connections/opencode-go with api_key and optional explicit select.
- POST /connections/codex/login with optional explicit select; GET/DELETE
  /connections/codex/login/{login_id} for status/cancellation.
- POST /connections/{provider}/refresh; DELETE /connections/{provider}.
- GET /runtime/status; POST /runtime/runs for Event SSE;
  DELETE /runtime/runs/{run_id} for cancellation.

Errors use shared ApiError; provider bodies, tokens and case text are redacted.
Transport diagnostic loggers are disabled because SDK debug logs can contain
request bodies. Temporary/unclassified generation is volatile. F0 never stores
any transcript, prompt, attachment, summary or model response, regardless of scope.

## Verification so far

Native Windows x64 CPython 3.14.4, F0-owned isolated environment:

    python -m pytest tests/runtime tests/integration/test_foundation.py -q

**28 tests passed**. Evidence includes actual Windows DPAPI round trip and
cross-profile rejection; dynamic OAuth with synthetic RSA identity and a real
loopback callback; rejection of wrong state/nonce and missing plan permission;
all five actual Hermes wire conversions; actual OpenAI SDK Codex and Go against
synthetic HTTP SSE; explicit background extraction/compaction using the same
selected route; streaming cleanup, cancellation, error redaction, no fallback,
scope enforcement and sentinel absence in app-owned durable files. These are
synthetic transport/account checks, not live-provider inference proof.

The tests exposed and fixed a Python 3.14 OAuth deadlock: waiting for listener
closure inside its still-active callback prevented the HTTP acknowledgement.
They also exposed and fixed dropped system instructions in the upstream Responses
converter: Renulus now passes them through the instructions field.

The full selected helper stack installed from binary wheels and imported.
Torch reports no CUDA; ONNX Runtime exposes CPUExecutionProvider. Actual native
LanceDB vector/full-text retrieval and delete, plus embedded Qdrant round trip
and deletion, passed with synthetic vectors. This does not establish embeddings,
OCR, Mem0 capture or educational accuracy. Two dependency deprecation warnings
remain: shared Starlette TestClient/httpx and legacy LanceDB create_fts_index in
the package smoke test. They do not affect the test outcome.

## Compatible pins and offline helper contract

[requirements-f0.txt](../../packaging/runtime/requirements-f0.txt) proposes
runtime pins; [requirements-helpers.txt](../../packaging/runtime/requirements-helpers.txt)
proposes the selected stack. The root manifests/global lock remain integrator-owned.
[windows-cp314-wheels.json](../../packaging/runtime/windows-cp314-wheels.json)
records official PyPI filenames/hashes for all 138 packages in the combined
Windows x64 CPython 3.14 resolution; each has a matching Windows/ABI3/universal
wheel. Actual installed relevant versions are Docling 2.133.0, Docling-core
2.99.0, FastEmbed 0.8.1, LanceDB 0.39.0, Mem0ai 2.2.1, Qdrant-client 1.19.1,
ONNX Runtime 1.30.0, tokenizers 0.23.2, PyArrow 25.0.1, Torch 2.14.1,
RapidOCR 3.9.2 and docling-parse 7.22.1. No Python downgrade is indicated by this
wheel/install/import evidence; clean bundled-runtime testing remains separate.

services.registry['helpers'] is a HelperAssets object. embedding_config() and
docling_config() validate manifest version, contained file paths, sizes and all
SHA-256 hashes before returning local paths and a group fingerprint. Missing or
tampered artifacts fail closed. Runtime does not download models.

The embedding engineering baseline is BAAI/bge-small-en-v1.5, 384 dimensions,
512-token truncation, with the exact bundled tokenizer.json. FastEmbed's
installed registry points to Qdrant/bge-small-en-v1.5-onnx-Q and model_optimized.onnx.
Explicit model path, local_files_only=True, CPUExecutionProvider, cuda=False and
two threads avoid implicit downloads/GPU selection. Stable profile paths:

- helpers/fastembed/bge-small-en-v1.5/ for ONNX and tokenizer assets.
- helpers/docling/ for the Docling layout/table artifact folders.
- helpers/ocr/ for explicit English RapidOCR det/rec/cls assets.
- cache/fastembed/ for profile-owned disposable CPU-helper state.

Knowledge's immutable beecc7f developer acquisition script was reviewed and
executed into F0's own explicit development profile. It acquired 67,412,843 bytes
for embedding, 384,434,829 for Docling and 31,749,509 for OCR. These assets stay in
ignored verification state, not source. Offline inference/extraction and asset
notices are the next separate evidence step; acquisition alone is not a pass.
Temporary-case Docling remains disabled until its no-write path is proven.

## Primary evidence and remaining integration

Official source inspected on October 4:

- https://github.com/NousResearch/hermes-agent at the recorded immutable pin.
- https://developers.openai.com/siwc/token-sharing-open-source/sign-in
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions
- https://auth.openai.com/.well-known/openid-configuration (issuer/endpoints/RS256).
- Official PyPI version JSON, exact installed library source, and the helper
  acquisition manifest's pinned Hugging Face/Modelscope artifacts.

Required remaining proof: real user-entered app-owned account login/catalogue/
model response, image capability, native desktop process/installer, offline CPU
asset inference/OCR/resource measurements and notices, controlled Hermes context
management and M5 Mem0 capture/deletion integration. The present source/transport
slice does not claim the full S0 acceptance gate or a complete installed product.
No paid-provider inference, copied credential, patient input or main mutation
was performed. Tracking: houraniiiii/Renulus issue #2, parent #1.
