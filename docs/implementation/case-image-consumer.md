# Guarded Cases image consumer

October 5, 2026, UTC. Isolated `build/case-image-consumer` worktree begins at
`5d4e92a72ff8cf88a3f64d8547cd40adb160be18`. Only Cases code/tests and Cases
evidence are changed. The parent profile, Memory, App, shared runtime, source
collections and external originals are untouched.

## Application behavior

The daily-case attachment picker keeps local text extraction as its default.
The doctor can instead select image discussion, review a PNG/JPEG in RAM,
choose an image-capable model from the selected subscription and explicitly
press **Send image for discussion**. Upload/review performs no inference.
PDFs continue through the separate local text extraction/review route.

The additive `mode: "image"` uses the existing prepare/upload/preview/cancel
reservation and revision/scope guards. The raw upload is bounded at 8 MiB
before decoding, including streams without Content-Length. Runtime
`validate_inputs` checks the actual bytes, MIME, single-frame format and
16-million-pixel limit. No original-copy path or multipart/disk staging exists.
Image questions are bounded at 11,800 characters to reserve room for the
canonical omission notice within the existing 12,000-character message limit.

`POST /cases/attachments/{preview_id}/discuss-image` requires revision,
request_id, message and the exact model. It resolves only a current ready
image review. Read-only connection checks require the selected provider route,
connected account, allowlisted/available model and observed
`image_input == "supported"`. Unknown, disconnected, unapproved and
account-rejected routes fail closed. No subscription/model fallback is used.
The same gate runs immediately before streaming.

The actual Cases stream calls the existing Provider seam with the selected
model, temporary case scope and `purpose="case-image-discuss"`. Only the
pinned last user input contains the runtime typed image; Hermes maps it to the
actual SDK image input. Session messages contain the question and a notice
that image bytes are omitted from Save. The source preview is invalidated on
acceptance and raw generator context is cleared on termination. Ordinary
follow-up discussion and Learn/practice handoffs receive no image bytes.

The existing cancellation endpoint stops the real run and prevents partial
or late assistant text from becoming a completed session message. Discard,
case revision changes, Save/scope changes, close and delete invalidate the RAM
review. The renderer also clears its image preview when Save changes scope
without changing revision.

Save retains only the existing explicit text snapshot: case text, question,
image-omission notice and completed discussion. Images are omitted even after
Save; reopening requires reselection for another image discussion. Pending
image selection is omitted too. The review screen states this before Send.
No automatic Memory producer/export is introduced.

## Required runtime prerequisite: Planck-owned

At this branch base, ProviderManager permits unknown image support for an
explicit runtime probe. Cases needs a narrower policy in
`runtime/renulus/runtime/manager.py:ProviderManager.events`: after `_route`
and `_model_status`, before credentials, compaction or transport use, reject
image-bearing `purpose="case-image-discuss"` unless the chosen current
account/model has `image_input == "supported"`. Preserve the existing
`account_unsupported` denial and connection-version checks. The proposed
unknown-support denial is `image_capabilities_unverified`, already safely
mapped by Cases.

This closes the account-change window between the Cases precheck and runtime
route selection. The prerequisite was proposed to the parent/Planck and was
not edited under this lease. **Integrate that runtime gate with this consumer
before declaring the guarded image flow freeze-ready.** Verify unknown support
and a changed account both fail before credential/HTTP use; established
support still uses the explicitly selected model.

## Controlled evidence

- `tests/cases/test_images.py` uses generated PNGs, synthetic account tokens,
  actual Hermes/OpenAI SDK and httpx controlled HTTP. A completed synthetic
  SDK image request establishes capability; no fake positive capability flag
  is supplied. Public sockets are denied; Windows asyncio loopback is allowed.
- The real Cases API proof checks exact SDK image data URI, selected model and
  `store=false`; upload produces no model request. It scans every isolated
  profile file and SQL table for image/prompt/result sentinels before Save.
  Save/restart retains only question/answer/omission text. A later text request
  contains no image. Unknown account, changed account, unapproved model,
  revision, discard, malformed PNG and upload limits are rejected.
- The cancellation proof invokes the real Cases route and actual SDK with a
  paused controlled response. The real cancel route stops it before a
  completed assistant message, clears the pinned image and retains no raw
  payload in the isolated profile.
- Cases preserves trusted ProviderManager public error code/message/retryability.
  The actual Runtime Go-denial proof asserts `learning_use_unverified` with
  `retryable=false` in the stream and image preflight/capabilities. Credential
  and HTTP sentries remain unused; no assistant message or profile payload is
  retained. Arbitrary provider-fixture exceptions still use the existing safe
  message mapping and cannot expose echoed payloads.
- `CaseImages.test.tsx` exercises CasesPage, attachment review and useCases
  with the real renderer transport/SSE code. It covers explicit Send, exact
  model, no Save/storage side effect, Stop, unsupported account, changed-account
  error, and invalidation on Save at unchanged revision.
- A browser pass at localhost ports 5291/8981 used a new ignored synthetic
  profile and the actual Cases API/renderer/Hermes/SDK with controlled HTTP.
  After image discussion, SQLite held **zero saved cases**. Explicit Save
  produced **one** saved snapshot. Image/base64 were absent from that profile.
  The generated original PNG remained unchanged, SHA-256
  `d99bb410cdf0d6284a4fcf480088bc87c3c4a9009656c2fdb80d1292e729b8ec`.
  Screenshots and the synthetic harness remain in ignored
  `.local/runtime/case-images/`; no host credential or parent profile is used.

Focused backend checks: **74 passed** across images, attachments, API and
retention. Cases renderer family: **29 passed**. Full desktop typecheck,
production renderer build, workspace validation and whitespace checks pass.
The existing Starlette TestClient deprecation and local verification config
dynamic-import warning remain non-blocking. No actual Docling/helper rerun,
new data download or paid/live provider request was used.

## Capability limits

Image input/transport completion is application evidence only.
`interpretation_verified` remains false. Live image interpretation, clinical
accuracy and educational efficacy are unproved. Current account support must
be established by an explicitly authorised image probe; a model catalogue or
text success cannot establish it. Go remains subject to the existing runtime
learning-use gate. This adds one PNG/JPEG per deliberate image discussion;
PDF visual interpretation, DICOM, image persistence and automatic case-derived
general learning are not implemented by this lane.

The integration owner added the shared Runtime prerequisite on October 5:
image-bearing `case-image-discuss` requests require observed `supported` image
input after route selection and before credential access or context compaction.
The independent guard check makes credential access fail if reached, then proves
the unverified request is rejected with no active run or live-provider claim.
The integrated Cases, practice and Learn producer check now strictly asserts
the non-retryable Go gate in all three consumers, with no expected failure.
The combined focused image/cross-module/practice/Learn error run passed
**44 checks** in 162.73 seconds. Connections' explicit synthetic image check is
now integrated in frozen product `ebb2db2e`; see
[the explicit image-input check](image-capability-check.md). The full renderer
subsequently passed 407 checks across 33 files. No live account proof is claimed
by the controlled-HTTP run or renderer suite.
