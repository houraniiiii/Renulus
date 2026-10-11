# Explicit managed harness startup

This is an opt-in development entry. The normal launcher, installed application
and private learning profile retain their existing path. H02–H08 acceptance
remains open. Run this entry only in a dedicated Windows Python process against
an explicitly owned profile. Its process-lifetime issuer is acquired before
application/database creation. Do not call it from pytest or the Codex process.

`renulus.server` accepts `--harness-startup <absolute JSON path>` together with
the existing `--profile`, `--port` and `--source-root` arguments. The existing
`RENULUS_SESSION_TOKEN` environment requirement remains. Without the new option,
startup follows the original code path. No runtime installation, account
discovery or deployment is performed by this command.

The JSON document is bounded to262144 UTF-8 bytes, rejects duplicate/unknown
fields and nonfinite numbers, and has this structure:

```json
{
  "version": 1,
  "process": {
    "node_executable": "G:/owned-runtime/node.exe",
    "host_entry": "G:/owned-checkout/packages/harness/src/main.mjs",
    "profile_root": "G:/owned-profile",
    "profile_id": "explicit-profile",
    "store_id": "explicit-runtime-store",
    "domain_store_id": "explicit-domain-store",
    "domain_path": "state/renulus.sqlite3",
    "max_inflight": 1,
    "max_domain_inflight": 1
  },
  "artifact_root": "G:/owned-launch-artifacts",
  "candidate_root": "G:/owned-candidate-profiles",
  "attempt_timeout": 15,
  "initialize_new": false
}
```

The paths above are illustrative; they are not installed artifacts. `process`
accepts the existing HarnessProcessConfig transport/count/byte/start-timeout
settings. Omitted transport bounds use that type's existing defaults. Profile
identity/path must match `--profile` exactly. Candidate profiles and launch
artifacts must be separate from the live profile. Ambient/nonempty boot settings
are rejected; the exact immutable launch artifact supplies native settings.

`initialize_new:true` is allowed only for a new/empty owned scope; reopening
requires the issuer's durable predecessor evidence. `initial_spec`, when supplied,
is a complete strict ConfigurationSpec with a verified launch reference and
previously observed native registry hash. The startup coordinator requires null
pointers for it. Omit it on reopen to preserve the effective version, pending
requested version and revocations. The entry invents no initial connection,
registry hash, capability, limit or tokenizer evidence.

The public Python assembly seam is
`create_managed_app(HarnessStartupOptions, ...)`. The original app's serving
lifespan runs the coordinator before its ordinary startup callbacks on the same
event loop. A closed/no-account/no-policy result refuses this opt-in server
startup with `configuration_not_active`; ordinary producers cannot fall through
to legacy execution. The coordinator's null/closed result remains observable.
Actual lifecycle/owner composition and connected startup verification are
recorded in the H02–H08 handoff.

The entry joins the retained bootstrap drain before closing Services dependencies,
including startup failure before ordinary callbacks run. Cancelling a close
observer does not release the serving loop or its owned finalizers. Services
shutdown also sends the coordinator a synchronous stop signal; it never registers
the coordinator's async close as a recursive dependency callback.

Trusted assembly may pass an async `prepare_startup(app, lease, authority,
launch_store)` callback returning an explicit initial ConfigurationSpec or None.
It runs after issuer-bound creation and before coordinator startup, and cannot
be combined with options.initial_spec. The CLI never injects this callback.
Tests may inject `provider_http_transport` at original application creation;
all connection routes, domain services and shutdown hooks retain the same
ProviderManager. Replacing the provider registry after route creation would
leave stale route owners and is not this contract.

`model_registry_factory` is an explicit Python assembly dependency. It must
provide the existing registry with exact canonical authority, explicit bounds
and independently verified immutable deployment evidence. The CLI currently
supplies none: model callbacks remain denied. No synthetic account/count/limit
fixture is a production deployment credential or evidence source.

App state exposes `harness_bootstrap`, `harness_configuration_authority`,
`harness_bootstrap_runtime` and `harness_bootstrap_result` for trusted assembly
observations. These are not renderer payloads or alternative configuration
authorities. Process/finalizer lifetime and actual native settlement must be
verified before this development entry can establish H04 startup acceptance.

The actual no-factory initial/reopen journey is now recorded in the H02–H08
handoff: one test covers two dedicated Windows child issuers, production Node
main/SDK inspection and activation, canonical admission before ordinary startup
callbacks, persisted configuration and actual normal settlement. Its account
catalogue is synthetic. It establishes the positive public Python serving-loop
assembly path; failure/cancellation recovery, CLI/uvicorn, hidden desktop and
matching account/deployment acceptance remain separately open.
