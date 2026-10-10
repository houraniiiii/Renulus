# Renulus managed harness foundation

This is the H01 saved-profile execution boundary for the pinned OpenCode source
cohort. Python retains canonical domain records. OpenCode owns its native
session, inbox, transcript and execution lifecycle in a separate SQLite store.
The existing desktop still uses its current execution path; H02 connects the
first cited learning flow and H03 supplies the selected subscription adapters.

The production entry is `src/main.mjs`, launched by Python's
`ManagedHarnessProcess`. It starts observable and policy-blocked. There is no
ambient provider, credential, plugin or project-configuration discovery path
that authorizes inference. The counted model in `test/fixtures/scripted-host.mjs`
is an external test adapter, never a product provider fallback.

## Prepare and check the source cohort

Follow [the pinned inputs and preparation recipe](../../upstream/opencode/UPSTREAM.md).
Use one built cohort and the hash-verified Node 26.4.0 executable. Do not run
`npm install` here or substitute the registry SDK's matching version label.
Create this package's ignored `node_modules` junction to the prepared cohort's
`node_modules`. Runtime child PATH contains only the managed Node directory;
Bun and TypeScript are build tools.

With the managed Node executable, run:

```text
node node_modules/typescript/bin/tsc --noEmit
node --test --test-concurrency=1 --test-timeout=45000 test/*.test.mjs
```

The real Python/Node integration tests are in
`tests/runtime/test_harness_sdk.py`; use their explicit artifact configuration.
The Python profile preparer writes `state/harness/manifest.json` before the
Node host opens a database. It remains **prepared**, with validation pending.
This slice does not activate a migrated domain store or implement paired backup.

## Lifetime and recovery

`openHarness` requires explicit profile, runtime-store and domain-store
identities plus the prepared manifest. Its facade exposes activation, native
session creation/input, observation, cancellation, deliberate recovery and
bounded close. The SDK's public Effect entry supports the required service
overrides; its Promise wrapper does not forward them at the pinned commit.

Input receipts contain the caller's operation/attempt IDs, the native session
ID, and the durable native `inputId`. OpenCode returns an inbox/message anchor;
this is not an invented upstream execution ID. Observation and reconstruction
do not submit another prompt. A native `wait` observes active execution; a
recovery acknowledgement schedules work and is not a terminal result.

Reopening holds interrupted work. Activating an admitted model configuration
does not resume it. Deliberate recovery must name the complete held set and
matching configuration, after admitted writes and all native executions are
quiescent. Fresh admission is sealed while the original upstream recovery sweep
runs. This conservative gate does not offer selective recovery of only some
uncertain sessions; that capability remains deferred.

Close seals new writes, drains admitted writes and disposes the real SDK. A
bounded observer can return blocked while the same drain continues. Only actual
settlement releases the store lease. Cancel likewise acknowledges settlement
after native finalizers. A dead previous PID can be reclaimed under the atomic
ownership guard; an ambiguous/stuck guard fails closed, requiring explicit
recovery. Time elapsed never proves ownership ended.

Detailed source references, observed failures and acceptance limits belong in
[the H01 implementation evidence](../../docs/implementation/opencode-foundations-h01.md)
and [the IPC evidence](../../docs/implementation/opencode-foundations-ipc.md).
