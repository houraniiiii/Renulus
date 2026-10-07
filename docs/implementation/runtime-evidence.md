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

The selected helper stack installed and imported; all packages except the
pure Python ANTLR parser have compatible official binary/universal wheels.
Torch reports no CUDA; ONNX Runtime exposes CPUExecutionProvider. Actual native
LanceDB vector/full-text retrieval and delete, plus embedded Qdrant round trip
and deletion, passed with synthetic vectors. This does not establish Mem0 capture
or educational accuracy. Actual embedding/OCR evidence is recorded below. Two dependency deprecation warnings
remain: shared Starlette TestClient/httpx and legacy LanceDB create_fts_index in
the package smoke test. They do not affect the test outcome.

## Compatible pins and offline helper contract

[requirements-f0.txt](../../packaging/runtime/requirements-f0.txt) proposes
runtime pins; [requirements-helpers.txt](../../packaging/runtime/requirements-helpers.txt)
proposes the selected stack. The root manifests/global lock remain integrator-owned.
[windows-cp314-wheels.json](../../packaging/runtime/windows-cp314-wheels.json)
records official PyPI filenames/hashes for the 139-package combined Windows x64
CPython 3.14 stack, with an explicit developer wheel exception for ANTLR 4.9.3.
The earlier binary-only resolver selected OmegaConf 2.0.6: it imported but failed
RapidOCR's Path assignment. The actual engine proof instead requires OmegaConf
2.3.1 with ANTLR 4.9.3. The official ANTLR sdist was built into a universal wheel
in the developer environment; doctors need no compiler or setup. The inventory
records both source and built wheel hashes and does not claim that every package
has an official wheel. Actual installed relevant versions are Docling 2.133.0, Docling-core
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
ignored verification state, not source. Their exact public file hashes and
immutable revisions are in [helper-assets.json](../../packaging/runtime/helper-assets.json).
Temporary-case Docling remains disabled until its no-write path is proven.

The ready public profile for integration is
`C:/Users/karol/Documents/t3-workspaces/Renulus-wt-runtime/packaging/runtime/.verification/.local/runtime/cpu-helpers`.
Copy only its complete `helpers` subtree, including manifest.json, into the
explicit integration profile; validate through both HelperAssets methods before
inference. No user state, credentials or private material is in this acquisition.

## Actual offline CPU proof

[prove_offline_helpers.py](../../packaging/runtime/prove_offline_helpers.py) uses
the real selected engines with hash-validated local assets, an explicit profile,
offline Hugging Face configuration and an external socket guard. Windows asyncio
and embedded LanceDB may use loopback sockets; those remain allowed. Fixtures
are synthetic and span CKD, dialysis, transplantation, glomerular disease and
electrolytes. This development-only script writes its synthetic PDFs/index into
its profile; it is not the temporary-case extraction path.

[offline-helper-proof.json](../../packaging/runtime/offline-helper-proof.json)
records actual FastEmbed CPU inference producing two 384-dimensional vectors;
native PDF and scanned PDF OCR extraction; Docling HybridChunker using the local
tokenizer with a page locator; and a real embedding-to-LanceDB retrieval round
trip. External connection attempts were zero. The proof records elapsed time
and sampled peak process RSS. These results establish the bounded local engine
pipeline, not standalone image interpretation, full document fidelity, native
installer acceptance or educational efficacy.

The helper validator additionally requires the exact layout/table, three OCR
files and tokenizer/model files to appear in the hash manifest. RapidOCR receives
an explicit `Global.model_root_dir` inside `helpers/ocr`. Three focused
helper-validation tests passed after this tightening.

[helper-notices.md](../../packaging/runtime/helper-notices.md) records original
model card licence tags and the developer-built ANTLR provenance. Complete
package/model notices, including OCR artifact terms, remain a distribution step.

## Primary evidence and remaining integration

### Controlled context, image input and helper startup follow-up

The additive implementation keeps the exact shared Provider.stream signature,
including scope, run_id, model, system and purpose. Typed message content accepts
ordinary text or parts of the following form; image bytes stay in memory:

~~~json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "Explain this synthetic teaching image."},
    {"type": "image", "media_type": "image/png", "data": "<base64>", "detail": "auto"}
  ]
}
~~~

Pillow 12.3.0 verifies inline PNG/JPEG/WebP without file or URL loading: single
frame, user role only, four images maximum, 8 MiB each, 16 MiB total and 16 million
pixels per image. Hermes converts those parts to actual Codex input_image or Go
image_url requests. The runtime does not fetch remote images or save bytes.
The dependency proposal adds Pillow, already present in the selected helper
stack; no root manifest/lock was edited.

Every model reports text_input and image_input as unknown, supported or
account_unsupported with evidence. A catalogue listing supplies account
availability only. A completed request records accepted input, while
image_interpretation_verified remains false: semantic image interpretation still
needs explicit real account evidence. Machine-code image/model rejection blocks
replay without selecting another model/subscription. Quota failures do not
establish input incompatibility. Authentication failure invalidates stale
catalogue state. Refresh/new connection clears the observations. Codex accepts
the documented models[].slug/visibility:list catalogue and legacy data[].id.

services.registry['context'] is a HermesContextAdapter. It reuses the actual
ContextCompressor, rough estimator, protected head/tail, media handling and
assembly. A fresh compressor serves each operation. The conservative application
budget is 32,768 tokens with a 4,096-token output reservation and 24,000-token
trigger; this is not a claim about verified model context windows. The summary
hook uses the same ProviderManager.stream with purpose='compaction', the exact
selected model and original scope. Native auxiliary resolution, retry, fallback,
tool execution and persistent Hermes sessions are disabled. Failed, empty,
oversized or ineffective summaries preserve the caller input and fail clearly.
Automatic compaction emits ordered progress events; parent cancellation closes
the summary child. Explicit provider.compact and
POST /api/v1/runtime/context/compact return volatile messages, estimates,
provider/model/scope, engine and persisted:false.

The stricter filesystem guard exposed two upstream side effects, now recorded
with original/patched SHA-256 values in hermes-source.json:

- R002 relocates nine unchanged recovery markers to conversation_markers.py.
  The general conversation loop re-exports them; compressor classification no
  longer imports general-agent Windows file logging. AST comparison against the
  acquired baseline established identical literal values, including a recorded
  canonical marker digest.
- R003 adds a context-local opt-out for optional heap trimming before the
  Hermes config/home loader runs. Controlled Renulus calls disable it; upstream
  defaults and other contexts remain unchanged. This removes the native state
  directory creation discovered by the strengthened compaction test.

Helper readiness now compares the writable profile manifest with the reviewed
source contract at services.paths.source_root/packaging/runtime/helper-assets.json
before checking file hashes. Desktop must bundle that trusted JSON read-only in
the source root alongside the public 19-file helper inventory. Rewriting both
profile assets and their self-declared hashes cannot pass readiness.

HelperAssets.startup is a HelperStartup object, registered on Services.on_startup.
Its status() returns configured, imports with per-group readiness/fingerprint or
error code, cpu_threads:2, downloads:false, model_instances_created:false and
temporary_extraction_verified:false. The startup hook configures
cache/import-temp through TMPDIR/TEMP/TMP and tempfile.tempdir, profile-owned
Hugging Face/Torch/FastEmbed caches, offline/telemetry flags, bytecode suppression
and two-thread helper environment settings before dependency warm imports. It
warms selected modules only when reviewed assets validate and does not construct
models, converters, indexes or perform conversion. Missing assets skip imports;
import failures report helper_import_failed without dependency details. Settings
remain controlled until provider/module shutdown completes, then are restored.
One owned backend/profile per process is the production lifecycle.

The real cold huggingface_hub.file_download/filelock import creates its symlink
probe only under cache/import-temp. A fresh-interpreter audit proved every
startup write stayed there, then prohibited writes during repeated imports.
This resolves the observed cold import probe, not all Docling conversion
side effects. Temporary extraction stays disabled until the library lane proves
its actual DocumentStream(BytesIO) conversion/chunking under a complete no-write
guard. No new heavy Docling proof was run in this follow-up.

RapidOCR 3.9.2 docling_config now supplies cpu_threads:2 and the dotted parameters
EngineConfig.onnxruntime.intra_op_num_threads=2 and inter_op_num_threads=2. Its
actual installed ParseParams.update_batch accepted them with the app-owned OCR
root; no OCR session or model inference was constructed in that check.

Final focused Windows x64 CPython 3.14.4 check:

~~~powershell
packaging/runtime/.verification/.venv/Scripts/python.exe -m pytest tests/runtime/test_provider.py tests/runtime/test_codex_stream.py tests/runtime/test_auth_api.py tests/runtime/test_protected_helpers.py tests/runtime/test_images_context.py tests/runtime/test_helper_startup.py tests/runtime/test_hermes_provenance.py tests/integration/test_foundation.py -q --basetemp packaging/runtime/.verification/f0-context-image-startup-final
~~~

**54 tests passed in 12.77 seconds**, with one shared Starlette TestClient/httpx
deprecation warning. The suite uses synthetic inputs and actual Hermes/SDK
transports against synthetic HTTP, verifies all five image mappings, explicit
rejections, same-subscription compaction, API scope retention, one terminal
event/cancellation, original input preservation and trusted helper provenance.
Cold Hermes compression with an injected synthetic test summary produced zero
filesystem mutations, including OS mkdir/link/open/rename/remove, and did not
load the general conversation loop or Hermes file logging. This is runtime seam
evidence, not live model or installer proof.

Official source inspected on October 4:

- https://github.com/NousResearch/hermes-agent at the recorded immutable pin.
- https://developers.openai.com/siwc/token-sharing-open-source/sign-in
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions
- https://auth.openai.com/.well-known/openid-configuration (issuer/endpoints/RS256).
- Official PyPI version JSON, exact installed library source, and the helper
  acquisition manifest's pinned Hugging Face/Modelscope artifacts.

Required remaining proof: real user-entered app-owned account login/catalogue/
model response, semantic image capability, combined native packaging/installer,
release notices, actual no-write temporary Docling conversion and M5 Mem0
capture/deletion integration. Desktop native launch evidence is tracked by its
own lane; no native installer was verified by F0. The present source/transport
slice does not claim the full S0 acceptance gate or a complete installed product.
No paid-provider inference, copied credential, patient input or main mutation
was performed. Tracking: houraniiiii/Renulus issue #2, parent #1.

Integration follow-up on October 4: the current official open-source
token-sharing sign-in and models/inference pages were fetched again. They retain
the selected dynamic-registration, S256 PKCE, loopback callback and public
Responses/model-catalogue direction. Renulus keeps the owner's exact allowlist
and intersects it with actual account availability.

The actual running local API then started a deliberate Codex login with
`select:false` and cancelled it through its public route. Both responses were
HTTP 200; the attempt changed from pending to cancelled. Authorization origin
was auth.openai.com, S256 was present, the resource was the public v1 API and
the requested scopes included `chatgpt.tokens.use.direct`. The authorization
URL/state/nonce were not published or opened, and no account exchange or
generative request occurred. Both providers remained disconnected and the
selected provider stayed null. This proves the live app-owned initiation and
cancellation seam, not completed login, available account models or inference.

Later selected-engine and cross-module evidence is tracked in the Library,
Cases, Memory, recovery and desktop records beside this file; the original F0
remaining-proof list above describes that earlier isolated slice.

The integrated Connections UI subsequently passed an actual browser start/cancel
journey against the owned development backend. It displayed the pending sign-in
and its cancellation control, then the cancelled notice. A fresh public status
request confirmed both providers disconnected and no subscription selected.
The browser did not open the authorization link; no URL/state/nonce, token
exchange or learning prompt was published or sent. This extends the earlier API
seam proof to the updated renderer, with the live account gate unchanged.
