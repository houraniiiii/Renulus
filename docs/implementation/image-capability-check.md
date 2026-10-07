# Explicit image-input capability check

Evidence recorded October 5, 2026, 01:43 UTC. Renderer base:
8f6de976e75c211022c3e4ca82f5f68464efff53. API producer checks were repeated against
integration 63c68ad7e8e658da9c10ba09bf83515f12ee87de, whose runtime guard is
45defa9da3f37ff6dc03f3756b4f0b46631820c5.

Connections offers **Check image input** beside each available approved model of
the selected, connected Codex account. The visible explanation identifies an
original synthetic Renulus test image and subscription usage. The clicked row
chooses the exact model. Go, unselected Codex, disconnected accounts and
unknown/unavailable catalogue models cannot initiate this check. A previously
rejected image route remains disabled until a deliberate model-list refresh
clears its observed rejection.

The helper sends one POST to /api/v1/runtime/runs with purpose
capability-image-check, the clicked model, a UUIDv4 run ID, and scope
{kind: temporary-case}. Its input is fixed original test text plus an inline PNG.
It reads no upload, case, clipboard, local file or credential. Initial render,
account checks and model listing do not initiate it. Runtime/API code remains
parent-owned and is not part of this patch.

The existing ordered run-events helper handles terminal results. Only completion
produces an acceptance notice and refreshes public Connections status. Generated
text is not displayed or saved. Interpretation quality remains explicitly
unverified. Authentication, quota, image rejection, connection change, model
refusal and incomplete streams remain visible failures; no route is substituted
and no retry occurs automatically. Other model/account actions are disabled
during the run. Stop and unmount abort body consumption and send DELETE to the
existing run cancellation path once per attempt. Late completion cannot write
UI state. Failed stop confirmation remains visible.

## Original PNG provenance

Renulus-authored MIT fixture: 16×16 RGB white image with a teal 8×8 square,
generated with Pillow and stored as a base64 constant in imageCapability.ts.
No third-party image, clinical finding or user input is present.

- Image bytes: 100.
- SHA-256: 004300443c19b2ac42179cb4a9859445ea610cbfa5d52512e9aa5edf0bbef76d.
- Wire detail: low; media type: image/png.

## Meaningful checks

**68 renderer checks passed** across ConnectionsImage, the existing subscription
auth/Go journeys and the shared run-event consumer. Coverage includes all three
exact Codex model requests, UUIDv4 and the complete fixed body, no request on
render, provider/account/catalogue guards, visible synthetic/usage explanation,
completion refresh, public failure transitions, ignored deltas/incomplete
streams, stop before headers, cancellation during body consumption, unmount,
late responses and failed server cancellation. TypeScript and git diff --check
also passed.

~~~text
node node_modules/vitest/vitest.mjs run src/platform/ConnectionsImage.test.tsx src/platform/ConnectionsPage.test.tsx src/platform/runs.test.ts --config ../../.local/vitest-image.config.mts
node node_modules/typescript/bin/tsc --noEmit --project tsconfig.json
~~~

The ignored test configuration is equivalent to the repository Vitest
configuration with its cache placed in this worktree's .local. The final
renderer run completed in 8.10 seconds using installed Vitest4.1.11.

**Three producer/API checks passed** using JSON emitted by compiling the actual
TypeScript helper with esbuild. Each exact model request exercised the real app
factory, authenticated runtime route, ProviderManager, pinned Hermes conversion
and OpenAI SDK through HTTPX MockTransport. The wire carried the exact 100-byte
PNG, exact model, store:false and no tools. Ordered started/delta/completed
events updated only that model's observed image support from unknown to
supported, with completed-request evidence and interpretation verification
false. Selection remained Codex, active runs emptied, and all profile file
hashes were identical before and after the three temporary requests. External
sockets were blocked, permitting only Windows asyncio loopback. These probes
also passed against the integrated strict Cases guard.

Machine-only probe artifacts are under owned .local: imageCapability.cjs,
emit-image-requests.cjs, image-requests.json and image-api-proof.py. Their
synthetic profile is .local/runtime/image-cap-api/profile.

~~~text
node node_modules/esbuild/bin/esbuild src/platform/imageCapability.ts --bundle --platform=node --format=cjs --outfile=../../.local/imageCapability.cjs
node .local/emit-image-requests.cjs
# CPython3.14.4, PYTHONDONTWRITEBYTECODE=1, HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1,
# MEM0_TELEMETRY=false; PYTHONPATH points to tested integration/runtime.
python .local/image-api-proof.py
~~~

The existing Flow tokens, typography and controls were inspected in an isolated
browser preview with public synthetic connection responses. Model-row controls
and the usage explanation fit the desktop layout. This is renderer inspection,
not a native Electron account journey.

## Integration and limits

Apply the scoped renderer commit alongside the parent's strict Cases image guard
and refresh the frozen renderer/package capture. Observed image support is now
obtainable through an explicit public app flow. Live account acceptance and
image interpretation quality remain unproved: development used synthetic keys
and controlled HTTP, with no real sign-in, paid inference or provider usage.
The parent owns combined regression, native packaging and ticket closure.
