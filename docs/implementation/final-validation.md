# Final integration validation

October 5, 2026 UTC. The application source is frozen at
`ebb2db2e5080f4d42eaf31c2eb63711797704df0`. Later test-harness, confined proof-tool
and evidence changes do not change the frozen renderer, managed backend or native
entry used for packaging. Native matching source and installer checks remain a
separate acceptance gate until their observed results are recorded.

The integrated producer/image/error check passed **44 tests** in 162.73 seconds.
It strictly checks the non-retryable Go restriction through Cases, Learn and
generated practice, actual controlled SDK image traffic and the Runtime guard
before credential access for unverified case images. There is no expected failure.

The first full renderer run passed 399 checks, but two API-backed suites failed
their ten-second readiness window and Windows temporary-directory cleanup. The
same two suites also failed independently. Their shared test-only harness now
selects the pinned project Python, allows a finite 60-second cold start with
bounded health requests, stops the exact spawned Windows process tree, and
retries cleanup of only its fresh synthetic temporary directory. Both real-API
suites then passed **all eight tests** in 70.41 seconds, with no skipped test or
cleanup failure. The subsequent full run exposed one-second UI waits that were
too short for six real-backend operations. Those two suites now allow a bounded
five-second asynchronous UI wait and thirty-second test budget, restoring their
configuration on teardown. No application code changed for either repair.

The final renderer run passed **407 of 407 tests across all 33 files** with no
skip, in 82.48 seconds. TypeScript checking, the Vite production renderer build
and Electron entry build then passed. Ignored local logs are
`E:/rn-renderer-accepted-20261005.log` and
`E:/rn-build-accepted-20261005.log`. The earlier failed attempts remain distinct
from this observed all-passing result. The test harness is not bundled into the
frozen Windows application.

Frozen staging checks passed **seven Python checks and three Node checks**,
including an actual Windows junction refusal. The Windows PowerShell 5.1 child
proof confirmed E TEMP/TMP without changing the parent's environment. These
guards do not establish actual installer or native Save-dialog execution.

The final full backend regression began with 901 collected tests on runtime
source `45defa9d`, which is unchanged in the frozen application. Its later
result and optional skips will be recorded separately. Test scratch, final
generated build output and native proof profiles are on the authorised local
E drive. The managed larger local data-only snapshot is still rebuilding;
successful recovery, excluded-state audit and cross-domain retrieval remain
separate from scan counts or queued ingestion.

Live account authorization/catalogue/generation, interpretation quality,
live automatic learning-point extraction, signing and a clean-machine release
remain unproved. No host credentials, paid provider calls or patient records
were used for these checks.
