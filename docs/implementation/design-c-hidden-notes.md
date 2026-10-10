# Design C Notes: hidden connected checkpoint

October 10, 2026. The actual assembled source app created and revised a personal
study note, placed its original revision in a saved chat draft, and reopened both
after a normal process restart. The editor opened revision 2 while the chat's
typed source continued to render revision 1. Nothing was sent to a provider.

The final restart used the exact `d14b0997` renderer build. The initial build was
labelled `f1228182` with the then-uncommitted Notes slice subsequently committed
as `a4439597`; this is an integration checkpoint, not matching installed evidence.
Notes backend/retention prerequisites are `7116e427` and `820d1906`.

The app-scoped controller exclusively owned
`C:/Renulus/scratch/dcctl/n1/c/s-7a282185/p`. Its `out/evidence-manifest.json`
SHA-256 is `a5c9230741c666dcf74c87ab6b6cf5ad688a726ee09fc54ff1a7ed10c6fc2517`.
The manifest indexes all seven capture hashes/dimensions and the final receipt.
Captures 0001, 0003, 0004, 0005 and 0007 were visually inspected; 0002 and 0006
are indexed only. The narrow reader is 984×681; 0004 also uses 200% renderer zoom.
Final wide captures show the retained draft, revision-1 reader and revision-2
editor. Controls remained within the independently scrolling Workspace.

Read-only inspection after normal close verified one saved Learn conversation,
two immutable note revisions and their exact original byte hashes. The canonical
draft contains the revision-1 text and one `note_revision` reference to that exact
revision. There are zero Learn messages, runs, assessment jobs and Memory jobs.
Both controller closes were normal, with no forced or remaining processes and
`fault: null`. No owner profile or credentials were accessed.

Two premature operator locators before Notes finished mounting and the expected
offline Home 409 remain in the logs. They are not described as a zero-error run.
The actual loopback editor test separately covers lost Save acknowledgement,
revision conflict comparison/rebase, immutable history and deletion in
`C:/Renulus/scratch/design-c/integration/notes-import-ui-03.xml`; six component
checks are recorded in `notes-ui-02.xml`, whose earlier journey timing failure is
retained. Actual backend originals/reopen checks are in `notes-backend-01.xml`.

Project membership/restore and Study help restrictions need their combined
producer checks; this journey does not establish those or installed/native
dialog, live model, physical accessibility or complete DC09/DC21 acceptance.
