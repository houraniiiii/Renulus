# Windows shutdown correction — October 5, 2026

Issue #18 is a concrete normal-workload delivery prerequisite. The owner
confirmed that the temporary case was a check and authorised continuing. The
parent invoked End temporary context at **06:27:44 UTC**, verified that its
control disappeared, and returned to ordinary Learn. Case details were not read.

The installed `3ff9b0d6` app then failed the parent's 25-second normal-close
observation while bulk Library ingestion was active. Its backend PID 28580 was
physically absent, while main PID 6488 remained on the controlled stop-error
dialog. The parent preserved the failure and terminated only the
executable-guarded stranded main process at **06:36:22 UTC**. Profile records,
account state, source originals and prior artifacts remain preserved. This is
not a successful normal-shutdown proof.

Later Windows reuse of PID 28580 by a system service was observed. That service
was untouched. Subsequent admission preflight checks the expected installed
executable paths rather than treating a historic PID as permanent ownership.
Ignored public receipts and logs remain under the integration checkout's
`.local/`; no credential or case content is part of this report.

## Correction and provenance

The previous child observer accepted Node exit/signal fields only, waited five
seconds, escalated and waited one more second. Observer lag or an insufficient
loaded-process observation bound is the working explanation; the original
failure does not establish its precise cause.

The parent added an optional Windows physical-existence observation. A specific
`ESRCH` result releases an absent root when Node fields are delayed. A live,
unknown, access-denied or throwing query retains ownership. POSIX still uses
the existing group/exit contract. Production taskkill is bounded at ten seconds
and production observation at fifteen seconds before the existing escalation.
Rejected inner and outer stop promises are cleared for a later attempt rather
than permanently caching the first failure. The helper still refuses to report
an unproved exit.

Owned source changes are `electron/backend.ts`, `electron/main.ts` and the
scoped `electron/upstream/backend-child.ts` patch, plus its meaningful boundary
tests. `THIRD_PARTY_NOTICES.md` preserves the original imported Hermes hashes
and licence while distinguishing this parent patch. No dependency, helper,
runtime-schema, renderer-flow or provider change accompanies it.

## Verification and remaining acceptance

The targeted serial run passed **11 checks in two files, 4.48 seconds**:

```text
npm test -- --maxWorkers=1 --no-file-parallelism electron/backend-child.test.ts electron/backend.test.ts
```

These include one actual Windows Node child: spawn a synthetic idle process,
tree-stop it, deliberately retain stale exposed exit fields, then independently
verify physical absence. No model, provider, private profile or source input is
used. Other checks retain ownership on alive/unknown/access errors, avoid
escalation after physical disappearance, retain POSIX group semantics and cover
existing cold startup/cancellation. TypeScript, Vite production and Electron
compilation passed with `npm run build`. Logs are
`.local/windows-stop-targeted.log` and `.local/windows-stop-build.log`.

These checks do not establish matching installed normal-queue shutdown. The
new exact product must be packaged and installed, then exercised on the
normal learning profile with its ingestion worker active. Verify physical close
and reopen, the retained account selection, original viewing/download and
priority admission before accepting the launcher change. The old failure and
any freeze55 artifacts remain separately dated checkpoints.
