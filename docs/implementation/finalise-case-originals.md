# Explicitly saved case originals — October 5, 2026

The connected-flow review found that the `f3160c59` installer retained reviewed
attachment text and discussion but omitted original PDF/image bytes. This is
an implementation gap against the confirmed explicit-Save retention decision,
not an external access blocker. Preserve that installer and its receipts as a
checkpoint; a changed application must be manufactured and accepted again.

The downstream change retains accepted originals in volatile case state until
Save. Applying reviewed text, explicitly keeping an image, or explicitly
sending it for discussion does not write a durable case. Save commits the case,
original metadata and bounded base64 parts in one canonical SQLite transaction.
After commitment, raw in-memory copies are released. The additive
`cases-002-originals` migration preserves the previously applied schema checksum.

An original has a filename, media type, byte count and SHA256. Authenticated
explicit viewing verifies ordered parts, byte count and hash and returns a
no-store response. Ordinary session responses contain metadata only. Removing
an attachment is a temporary change until Save changes; closing unsaved edits
returns to the last saved snapshot. Deleting a case cascades through originals
and uses the existing deletion ledger, secure deletion and checkpoint.

The existing full segmented backup transports canonical parts and reconciles
their case/attachment references against newer deletion markers. No additional
original-copy tree or index is introduced. Records-only exports skip raw parts
before their JSON size check and explicitly describe the omission. Such a
restore can show attachment metadata while the original remains unavailable.
Originals retain the bounds of the input routes; a case has at most 16 originals
totalling 32 MiB. Original source files are preserved.
Keeping an original image uses the existing bounded in-memory image validator
and needs no subscription, OCR or provider call. Image discussion retains its
existing approved-model/account eligibility checks.

## Scoped validation and manufacture acceptance

The Flow controls are integrated from `1ae9a5c9` and `49c0fdf7`: explicitly add
originals, inspect saved/temporary metadata, view an authenticated original and
stage removal until Save. The disconnected original-image choice performs no
model call. The entire renderer source/manifests match the reviewed lane. Its
45 affected renderer checks and TypeScript check passed with synthetic API
fixtures; this is not installed viewer or live model proof.

The guarded application run at `1e383913` completed 113 identities: 112 passed
and one records-only restore identity failed. Its valid JUnit SHA256 is
`b42d25e9c553c6bcf1922ffcbbbe4a7bcc5081260a6d5f504fb6a1d1845cf599`.
The run remains failed/nonaccepted. Earlier `d3bc31f1` collection failure ran
no identities. A one-ID retry at `e9f8364c` reached successful restoration but
failed its error-response no-store assertion; that failure is also preserved.

Parent fixes `381933fd` and `499d6d00` admit the declared case-original omission
and make product/validation errors no-store. The exact one-ID retry at
`37dc53842ad928cbc47488189576729e4082e9cd` passed, exit 0, complete/source
unchanged/accepted true, with no guards or unexpected modules. JUnit SHA256:
`d3f0b2d6a195958db798d1166965261a9c7452bb296afbbcc5950f7d08bbf879`.
It ended October 5 at 19:52:46 UTC and released the application slot.
Receipts are under `C:/rn-finalise-20261005/case-originals-37dc5384-01`, with the
prior 112 individual passes under `case-originals-1e383913-01`. No successful
identity was repeated and no new green 113-ID aggregate is asserted.

Integrated product and affected test paths are byte-identical to the clean
tested `37dc5384` source. The 112 earlier assertions retain relevance: the
remaining production delta is the new omission allowlist and additive error
headers, and the formerly failing identity covers those paths. Temporary
absence, explicit Save/restart bytes, failed Save rollback, staged removal/close,
capacity bounds, canonical recovery, conflict and deletion tests are local
proof. The newly extended two actual-engine consumer tests are preparation
only; they were not run in this application slot.

The integrator accepts this reviewed slice for a new exact manufacture freeze.
Matching installed original viewing, populated recovery and successful live
interpretation still require performed receipts. The f316 installer remains
a truthful pre-fix checkpoint.
