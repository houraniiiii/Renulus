# Response observation preparation

Prepared on 2026-10-06 in `C:/rn-finalise-20261005/lanes/response-observation`,
branch `codex/finalise-response-observation`, source base
`6c76efe058aeb7b2385bd49c018557c5b77b4b41`. Parent acceptance remains frozen at
`035ca7bd07337c65266c17f9b762ca1f97238e11`.

The ignored candidates are under `.local/finalise-response-observation/recipes/`.
Only this report is committed. The preserved originals at
`C:/rn-finalise-20261005/preserved-lanes/live-acceptance/recipes/` were read and
hashed without modification. Their two entry scripts, two PowerShell wrappers,
physical-close helper and three root preparation JSON files were copied.
Wrappers/helper and historical JSON remain byte-identical. The unchanged helper
pin is `5e163a494a755708712bf5f2d023b37eedd137203b92cb144a34f9432d7950ff`.

The original validators joined `waitForResponse` with an action, then obtained its
body through Chromium's inspector cache. The candidate arms one exact method and
literal/regex route on the actual renderer fetch. It calls the original fetch
once with unchanged arguments, starts a clone reader when the response arrives,
and returns the original Response immediately. Product SSE flows before clone
observation completes. Cleanup cancels only the clone; cancellation is not
awaited because a tee branch can wait for the product branch. ID matching drops
late callbacks. Fixed transport error codes avoid exception-message leakage;
the observer reads no request body, auth headers or URL query, emits no console
output, and transports only the armed body and four allowed response headers.

| Candidate source | Exact delta |
| --- | --- |
| `recipes/response-observation.mjs` | New shared module; one armed same-origin observation, asynchronous clone JSON/text/binary capture, original Response returned untouched, absolute deadlines, bounded SSE/binary accumulation and clone cleanup. |
| `recipes/connected-acceptance/connected-acceptance.mjs` | Import/install observer; replace `ui()` inspector JSON and `viewOriginal()` inspector binary access. Retain 180-second bounds and exact canonical bytes/hash checks. Record custom SHA header presence/value without a propagation claim. |
| `recipes/live-acceptance/live-acceptance.mjs` | Import/install observer; replace `uiResponse()` inspector JSON/SSE access within 120 seconds and 256 KiB. Replace separate Study-resume inspector JSON within its existing 30-second wait. Add the shared module to `recipeHashes` so strict Probe equality also covers it. |

Live SSE line/event parsing, terminal-error/cancelled/completed checks, result
shape, routing and synthetic-output handling are unchanged. Connected original
viewer checks, PDF screenshot classification and PNG dimensions remain.
Failure receipt/close bodies are unchanged; blocker latches and Probe provenance
guards retain their existing conditions. Original capture cannot exceed
`original.bytes`; final exact count and SHA256 checks still apply. JSON receives
no new byte allowance. Requests, provider/account/model/authorization selection
and deadlines are not widened or replayed; no mocked response is introduced.

The parent's later finding reported native05's eleven passed gates followed by
failure on a proxied backup format header. Reading the current main
`apps/desktop/electron/frontend.ts` confirmed that its streaming proxy sends
Content-Type/Cache-Control and sets nosniff, but does not forward
`X-Renulus-Backup-Format` or `X-Renulus-SHA256`. The read-only source at
`C:/Renulus-native-delivery/desktop-20261005/repo/apps/desktop/electron/frontend.ts`
has SHA256 `0eb5c7c8e0af502d5c47826d481862f72eefc0d1403cab73e2ce5422f6a24da7`.

View-original still mandates no-store, nosniff, media type, exact
`data.length === original.bytes` and `sha(data) === original.sha256`, against
canonical attachment metadata already returned by the apply/keep/reopen flow.
A custom SHA header, if present, must equal that canonical hash. Evidence adds
canonical bytes/hash, `sha256Proof: 'exact-raw-bytes-vs-canonical-attachment-metadata'`,
and `proxySha256Header`. With the current absent header it records
`{ present: false, value: null, propagationProofClaimed: false }`. This preparation
does not claim an executed View-original observation or propagated-header proof.
There is no extra metadata request. Connected `bytes()` and `archiveCase()` already
validate the actual ZIP format-2 manifest, segment sizes/hashes, metadata and raw
attachment parts independently of custom headers; both are unchanged. Parent
owns continuation after backup, preservation of the failed eleven-gate receipt
and avoiding Library replay; product/manufacture source is untouched here.

The native05 reference was read-only:
`C:/Renulus-native-delivery/desktop-20261005/repo/apps/desktop/.local/installed-journey-resume-035ca7bd/source.patch`,
SHA256 `9924ab45b14f31730e83e30fb34646c1a30885cbdf1e37bfd9aeb475213d4cd6`.
Its actual-clone approach informed the candidate; no native receipt was opened.

Syntax passed for all three modules. Imports invoked only helper exports and
original/candidate `plan()` functions. Both default and explicit-revision CLI plans
passed and match the originals exactly. Source comparison verified unchanged
SSE parsing, ZIP inspection, viewer code apart from declared header/evidence
changes, and failure/close bodies. Neither candidate retains inspector-body
response waits. `preparation.json` lists exact command arguments and SHA256 values
for all originals/candidates. Commands executed from this lane before the report
commit were:

```powershell
$renulusNode = 'C:/Users/karol/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
$renulusPreparationRoot = 'C:/rn-finalise-20261005/lanes/response-observation/.local/finalise-response-observation'
$renulusFreeze = '035ca7bd07337c65266c17f9b762ca1f97238e11'
& $renulusNode "$renulusPreparationRoot/prepare.mjs"
# The preparation invokes these syntax and CLI-plan commands:
& $renulusNode --check "$renulusPreparationRoot/recipes/response-observation.mjs"
& $renulusNode --check "$renulusPreparationRoot/recipes/connected-acceptance/connected-acceptance.mjs"
& $renulusNode --check "$renulusPreparationRoot/recipes/live-acceptance/live-acceptance.mjs"
& $renulusNode "$renulusPreparationRoot/recipes/connected-acceptance/connected-acceptance.mjs" --plan
& $renulusNode "$renulusPreparationRoot/recipes/connected-acceptance/connected-acceptance.mjs" --plan --expected-revision $renulusFreeze
& $renulusNode "$renulusPreparationRoot/recipes/live-acceptance/live-acceptance.mjs" --plan
& $renulusNode "$renulusPreparationRoot/recipes/live-acceptance/live-acceptance.mjs" --plan --expected-revision $renulusFreeze
```

`prepare.mjs` checks the assigned branch/base and safe plan imports, compares source
sections, and produces two scoped `git diff --no-index` hunks plus the new shared
module hunk. Patch paths are relative to a directory containing `recipes/`.
`SHA256SUMS` additionally pins `preparation.json` itself. Copied historical JSON
describes the original recipes, not the current candidate.

| Artifact under `.local/finalise-response-observation/` | SHA256 |
| --- | --- |
| `source.patch` | `bda790049cfc034334944a472485b75d69100be8e004ce1be1f32cbeb02935b1` |
| `preparation.json` | `554b9dcabf60fd94d37672a8b2b1dd83dd8fa0a5f13f2d6829341f972be43ebd` |
| `recipes/response-observation.mjs` | `1d43b348b137634169e6b86d7ac9fe6dbb1a363d4bfe18cf287be33125134f96` |
| `recipes/connected-acceptance/connected-acceptance.mjs` | `5f3ac575a2ea191c3b350cff0184b64782298285ee8d802cfa55347ff29f14fd` |
| `recipes/live-acceptance/live-acceptance.mjs` | `5a6c210dfd88fd04dcbde0856cca3aa11d5c0368f852fda8cef5ad4d7c73fcea` |

This is preparation, not installed/live transport acceptance. There were zero
run-mode invocations, app/native/helper/engine/live executions, provider/network
requests, tests, profile/credential/account reads or native receipt reads.
Main/product/test sources and tracker state were not edited.

Parent owns integration and execution. Preserve the entire ignored
`.local/finalise-response-observation/` folder, both sibling recipe directories and
shared module before retirement. Integrate within the authorized receipt/latch
lifecycle: relocating a candidate ROOT must not clear a failed-attempt guard or
authorize a repeat. The new recipe hash inventory keeps strict Probe provenance;
it does not accept old source hashes as this candidate's passed Probe evidence.
