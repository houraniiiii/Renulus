# Design C hidden Study and timed Test checkpoint

The lead exercised the actual source app with the hidden Renulus controller and
an owned synthetic profile. This is bounded source-app evidence, not matching
installed acceptance or a live provider/physical accessibility claim.

Evidence root: `C:/Renulus/scratch/dcctl/c3/c/s-b2d93aa4/out`.
The readonly final database check and eight screenshot hashes/dimensions are in
`evidence-manifest.json`, SHA-256
`edbe29fb44791af4d79233e02426b9c5c7cd59a92cb0f8f8c238d6bd9de83ae6`.
The renderer remained built at `319ff190`; normal restarts loaded the then-current
canonical backend during integration. This mixed integration checkpoint must be
repeated at the final immutable delivery revision for DC21 parity.

## Actual journeys

- Created a five-question reviewed set covering ANCA-associated disease, CKD and
  AKI from the installed content owner. Study help recorded assistance before
  an explicit correct answer. Paused, closed/reopened normally, resumed and
  finished: one correct out of one committed answer, four not submitted, one
  assisted commitment. The database retains 233 paused seconds.
- Retook the same immutable version as a one-minute Test. Selected an answer and
  marked a question; New chat remained restricted. Restarted normally while the
  timer continued. Reopen finalized at the deadline: **1/5**, four unanswered,
  zero excluded and zero not submitted. Results retain repeat **1/2**, fresh
  **0/3**, assisted **0/0**. The result reason is `deadline`, duration 60 seconds
  and paused seconds zero. Feedback was inspected after final submission.
- Inspected actual result pixels wide, at 1000×720 and 640×540 outer dimensions,
  and at 200% zoom. At the narrow size the rail collapses and the result scrolls;
  the 200% keyboard check showed a visible focus ring on the retake checkbox.

The final readonly SQLite audit found exactly these two attempts, Study `ended`
and Test `submitted`, with the stated denominators and immutable result records.
No private question snapshots were exported into this report.

## Receipts and limits

`receipt.json` records three hidden launches, two normal restarts and the final
normal requested close. All closes have empty `forcedPids` and `remainingPids`;
`fault` is null. Native entry SHA-256 is
`c4b3e337fa58ee3e2754ffbf2d485cc74d0421db6a7d339ed36f3a5cc223d615`.
No owner profile, accounts, credentials, live inference or OS input was used.

Inspected captures are `0001` setup, `0002` assisted Study feedback, `0005` wide
Test results, `0006` narrow results, `0007` minimum-width results and `0008`
200% keyboard focus. Intermediate `0003`/`0004` remain indexed but are not used
as visual pass evidence. Expected policy refusals and operator locator errors
are retained in logs; null controller fault does not mean a zero-error run.

The run exposed a sidebar that retained failed navigation reads after Test expiry.
The lead repaired refresh on assistance release in `d14b0997`; the two actual
shell component tests passed in `integration/navigation-policy-02.xml`. The first
test receipt is retained: its restricted-history locator was incorrectly visible
only and was corrected to account for the intentionally hidden history region.
Final installed timing, sleep/clock cases and the full DC20 matrix remain open.
