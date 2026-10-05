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

The backend implementation is ready for scoped regression and the renderer
integration. No successful test, installed original journey, populated recovery
or live image interpretation is claimed by this initial record. These gates
remain open until their actual receipts are reviewed.
