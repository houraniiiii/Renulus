# BF01 native capability lifecycle

`createPluginLifecycle(options)` coordinates reviewed local native OpenCode
plugins. Its object API is `status`, `stage`, `add`, `edit`, `disable`, `remove`,
`activate`, `recover`, and `close`. Stage/add/edit/disable/remove inspect the
complete proposed graph; `activate` is the separate explicit activation command.
No package installer, provider, account, MCP server or model is invoked.

## Artifacts and validation

Install reviewed self-contained `server.js` bundles at
`<root>/artifacts/<plugin_id>/<version>-<artifact_sha256>/server.js`, with
`LICENSE` and all listed notice files in the same directory. Installation does
not mean runtime npm/pip resolution. Renulus's manifest records configuration;
OpenCode's native Plugin/Effect scopes own registration and execution.

Staging checks the exact manifest shape/cohort/schema, semantic versions and
closed dependency graph, duplicate native/tool identities, integrator-known
migration checksums, licences/notices, plain-file integrity, and final native
input/output schema hashes and tool byte bounds. Dependencies load first in a
deterministic order. Unknown migrations are rejected by default; normal hosts
must not set the synthetic-only `allowUnknownMigrations` option. Prompt, skill
and endpoint declarations refuse staging pending their later-wave observation
and authority work.

Candidate inspection executes a private copy of the reviewed bytes in a
disposable profile. It binds the native loaded identity/source/hash and final
transformed registry. Original and copied bytes are checked after inspection.
An undeclared tool remains observable and fails validation. A native setup
failure, including SDK restoration of an earlier healthy activation, fails the
candidate; the requested artifact is never called healthy because old tools work.

## State and activation

The lifecycle owns only `state/plugin-lifecycle/`:

- `selection.json` records the requested, inspected generation and failures.
- `effective.json` atomically selects a complete inspected graph **after**
  quiescence and an additional byte check.
- `active.json` records the last generation whose restarted native inventory
  and registry matched its candidate receipt.

Status separately exposes `requested_operation_id`, `requested`,
`selected_operation_id`, `selected`, `active_operation_id`, `active`,
`failed_operation_id`, `failed_requested`, `failed_error`, and `reobserved`.
`state` is `empty`, `staged`, `ready` or `held`. Active metadata is historical
evidence while held; it does not assert that an old host is still serving.

Disable/remove narrow affected native grants before candidate inspection.
Activation requires settled operations, permissions, workers and external
effects. Timeout stays held, and late settlement cannot continue activation.
Activation replaces the native host, never simulates unregister. Saved data,
canonical migrations and installed artifact originals are preserved.

On reopen, the effective selection starts held and must be reobserved through
`recover`. Recovery validates the effective selection, not a merely staged edit.
A recorded returned failure requires fresh explicit staging; it is not retried
as if it were a crash. Revoked grants are not restored by recovery or restaging.

## Protected native factory mapping

`packages/harness/src/capability-plugins.ts` exports:

- `closedHarnessEnvironment(state, config)` for shared Global, Config,
  InstructionDiscovery and package-acquisition overrides.
- `verifyCapabilityArtifacts(artifacts)` for pre/post native byte validation.
- `createCapabilityPluginHarness({ root, openHost, authority })` for disposable
  inspection and fresh selected-host composition.

An injected `openHost` requires explicit app `authority`:

```ts
const host = createCapabilityPluginHarness({
  root: lifecycleArtifactRoot,
  authority: {
    narrow: request => app.revokeNativePlugins(request.disabled_native_ids),
    quiesce: request => app.settlePluginChange(request),
  },
  openHost: async configuration => {
    // Disposable roots need their own prepared paired profile. The selected
    // root binds the existing selected profile/store and its writer lease.
    const profile = await app.preparedProfileFor(configuration.root, configuration.isolation);
    const native = await openHarness({
      ...profile,
      capabilityArtifacts: configuration.artifacts,
      capabilityPermissions: app.currentNativePermissions(),
      // Supply the existing Library/model/domain adapters where appropriate.
    });
    return {
      inspect: () => native.inspectCapabilities(configuration.isolation),
      close: () => native.close(),
    };
  },
});
const lifecycle = createPluginLifecycle({
  root: lifecycleArtifactRoot, host, cohortSource: CAPABILITY_COHORT,
  knownMigrations: integratorMigrationChecksums,
});
```

Here `app` denotes the owning backend, not an implementation supplied by this
module. `narrow` must commit current grant revocation before returning.
`quiesce` closes admission, settles the entire affected graph and returns the
`PluginQuiescence` counts, including uncertain effects. The backend must close
its pre-existing target native host before the adapter opens a replacement on
the same store. It keeps admission/recovery closed until lifecycle observation
and its current authority/configuration checks both pass. A failed candidate
does not authorize reopening admission. Existing current grants remain the
authority; declarations cannot mint them.

The callback owns protected store selection: `openHarness` uses its paired
profile's `state/harness/opencode.sqlite`, not `configuration.databasePath`.
The latter configures the standalone synthetic inspector only. The standalone
default has no admitted effect surface and uses a separate lifecycle native
database; it is not a replacement for production grants or worker settlement.

The protected `inspectCapabilities` seam must expose every final transformed
tool even if its execution grant is currently denied. Explicit empty capability
lists must preserve the stock tool boundary after removing the final plugin.
The existing `harness/1` inspect response retains its independent wire shape.

## Focused verification

Run Node 26.4.0 in strip-only mode (the default):

```text
packages/backend: node --test --test-concurrency=1 test/plugins*.test.mjs
packages/harness: node --test --test-concurrency=1 test/capability-plugins.test.mjs
both packages: node node_modules/typescript/bin/tsc --noEmit
```

The protected-factory test uses Python `prepare_harness_profile` on owned
synthetic roots, then real native add/edit/disable/remove and reopen on the same
selected native store. It admits no providers, accounts, workers or real user
permissions. `RENULUS_TEST_PYTHON` may select the prepared contributor Python;
the default is `C:/Renulus/dev/python/Scripts/python.exe`.

These proofs do not establish production HTTP/dispatch grant wiring, app worker
draining, provider availability, BF03 skills/MCP, or packaged Windows acceptance.
