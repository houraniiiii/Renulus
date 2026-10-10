**Wave 1/03 — OpenCode artifact and embedded-host verification**

2026-10-10. Research only; no product implementation. The owner's current selection is OpenCode v2 embedded, superseding the older undecided side-chat status. Current subscription defaults remain selected; future opt-in vLLM/Ollama/additional providers remain possible. This lane inspected public artifacts and repository source only.

**Recommendation.** Use source `4b6fea2875e4f2e3e8a8fee181803e54f7056845` for the first proof, building its complete SDK dependency cohort together. Retain published 2.0.26 as a comparison artifact, not an equivalent build. The published SDK demonstrably forks recovery before registering supplied host plugins. The newer source fixes registration ordering, but registration alone does not establish successful policy activation or permission to resume generation.

**Artifact identity and integrity — observed.**

| Candidate | Exact identity and finding |
| --- | --- |
| Selected source | `4b6fea2875e4f2e3e8a8fee181803e54f7056845`; root still declares 2.0.26, build tool Bun 1.4.2, Effect 4.0.1. Version text alone cannot identify this build. [Root manifest][root] |
| Release-tag source | Supplied SHA `9b4ec5714d481559990db0a816d5dec19541a814`. Raw `v2.0.26` host and Promise files were byte-identical to these SHA-pinned files. This verifies those files, not every package's provenance. [Tag host][tag-host], [tag Promise][tag-promise] |
| Published SDK | `@opencode/sdk@2.0.26`: Effect 4.0.0-rc.112; exact 2.0.26 core/util/client/plugin/schema/server dependencies; no `gitHead` or `engines` declaration. [Registry][sdk-reg] |
| CLI | Exact `opencode-ai/2.0.26` registry request returned 404. This does not negate SDK publication or supply an embedded artifact. [Exact query][cli-reg] |

Downloaded tarballs into memory, compared actual SHA-512 against registry `dist.integrity`, and inspected members without installing or importing them. All five passed. Independently calculated SHA-256:

| Artifact | SHA-256 |
| --- | --- |
| SDK 2.0.26 | `5b62dc637174778a48c024bcea31b177bb28991c62407afa26bbe5917ceb53db` |
| Core 2.0.26 | `9750090be01bc0f8fba3c018e9f5445e66edcf4e1e937431cfb07acaffe26a2c` |
| Util 2.0.26 | `b6f32ea505c2567d02a4245d573f4de29884dff2a7119147555da396d54c34b5` |
| Server 2.0.26 | `2526356b87d3e034c38892f1e4d4c7e195e1088a5fd694bd04d481c5ad7ab96a` |
| @lydell/node-pty-win32-x64 1.2.0-beta.12 | `88fb6655b0493e5e7abaeca53bec0078b99e76a94398562fbcf1c2bb4ddb887c` |

Sources: [SDK][sdk-reg], [core][core-reg], [util][util-reg], [server][server-reg], [Windows PTY][pty-reg]. SDK's expected SRI is `sha512-+Klt3Xtpb/1AkPbDASZXrko/+ISxxFndGVKocorRp9f1I7wMpIX9NujOIoDMNVjS4fTTJuhSg02T8YTyiftEyA==`. Registry signatures were present but not verified; matching integrity does not prove source-to-binary reproducibility. The full dependency closure was not downloaded.

**Startup ordering and recovery — static findings.**

In the published SDK, `dist/chunks/logging-d9bx5h6j.js` acquires the host services and calls `runtime.runFork(...resumeSuspendedSessions)`. Its Promise entry, `logging-y51agw8v.js`, awaits that host and only subsequently loops over supplied plugins. This matches the tagged source. It establishes an ordering hazard, not an observed provider escape. [Inspected tarball][sdk-tar], [tag host][tag-host], [tag Promise][tag-promise]

At the selected source, Promise plugins are adapted before host creation; the host registers them before forking recovery. However, `SdkPlugins.register` stores definitions and publishes an update: it does not await every location's plugin setup. Session-selected instances have stronger checks: they await activation and reject failed configured plugins, including ID collisions with host plugins. Do not generalize that protection to every host-wide or locationless request. [Current Promise][promise], [host][host], [registration][registration], [instance checks][instances]

Recovery is explicitly at least once, includes background-job reconciliation, assumes previous owners are dead, and defaults to ten resume attempts. The SDK invokes it automatically; its public host options have no recovery switch. A recovered child completion can wake a parent. Gating only new UI prompts therefore misses work already in storage. [Recovery implementation][restart], [options][options]

Proposed gate choices:

- Prefer an `embed.overrides` replacement for `SessionRestart.node` that waits on an application-owned readiness decision, then delegates to the original recovery layer with its dependencies. Keep admission and provider/domain dispatch independently denied until policy is ready. This uses existing composition machinery; feasibility and deadlock behavior remain unexecuted. [Replacement routing][routes]
- A small upstream `recovery: manual|automatic` option is a fallback if the replacement cannot preserve lifecycle semantics. It must defer the entire sweep, including background notifications.
- Setting `maxAttempts: 0` is not a pause: the sweep increments attempts and terminalizes claims. A permanently empty replacement also loses reconciliation. Neither is an adequate resumable recovery design. [Attempt handling][restart]

**Native Windows and configuration entry points — observed code, not runtime acceptance.**

The SDK/core build scripts emit Node ESM with external packages. Bun is a build tool here; it is not inherently the delivered host runtime. Core has explicit Node/Bun import conditions. Node SQLite uses `node:sqlite`, including `setReadBigInts`, `setReturnArrays` and `DatabaseSync`; absence of a package engine constraint is not compatibility proof. [SDK build][sdk-build], [core manifest][core-manifest], [SQLite adapter][sqlite]

Concrete distribution requirements:

| Surface | Evidence and implication |
| --- | --- |
| Ordinary PTY | `#pty` is lazy-loaded; its Node implementation requires @lydell/node-pty. The inspected Windows package contains `conpty.node`, `conpty_console_list.node`, `conpty.dll` and `OpenConsole.exe`. Preserve their layout if PTY capability is shipped; this does not prove they load successfully. [Lazy import][pty], [Node adapter][pty-node], [artifact][pty-reg] |
| Persistent PTY | Node adapter explicitly marks Windows unavailable because opencode-pty has no Windows binaries. Ordinary PTY availability must not become a persistent-terminal claim. [Adapter][persistent-pty] |
| Watch/search | Core declares @parcel/watcher 2.5.1 and @ff-labs/fff-node 0.10.5; both have Windows artifacts. FFF's ranged ffi-rs dependency resolves to 1.3.7 in the selected lock. `fs.filewatcher:false` and `fs.fff:false` are behavior controls, not evidence that every dependency can be removed. [Manifest][core-manifest], [lock][lock], [options][options] |
| WASM | Node resolvers expect photon, web-tree-sitter, Bash and PowerShell WASM files, with explicit path overrides. A JS-only bundle can miss these assets. [Image resolver][photon], [parser resolver][parser] |

`OpenCode.create(options, embed)` exposes persistent `database.path`, `config.directory/project/file/content`, `models.fetch/snapshot`, `events.persist`, filesystem flags, logging, host plugins and session-selected `instances.key/configure`. Desktop `config.content` is a string. Default storage is in memory; use an absolute owned database path. [Promise API][promise], [options][options], [database][database]

There is useful existing neutral-profile machinery: internal `Instance.layer(..., {discovery:false})` disables project/global config and boot-time instruction discovery through service replacements. The SDK's instance options do not expose that flag, and server options omit core `config.global`. Reuse those two replacements for Config and InstructionDiscovery, preserving explicit supplied content, rather than rebuilding discovery. Explicit file-backed configuration, well-known configuration and use-triggered nested instructions remain separate surfaces. [Instance implementation][instance], [instance selector][instances], [options][options]

`app.name` does not isolate storage: Global uses the literal `opencode`, and XDG roots are calculated at module import. For a proof child process, supply isolated environment roots before import and override all Global paths, including home/tmp; changing only `config.directory` is insufficient. No private roots were read here. [Global][global], [roots][roots], [route configuration][routes]

**Host lifecycle and minimal change ledger — proposals.**

Keep one process owner per harness database and confirm predecessor death before recovery. Database migration locks shown in source are process-local maps, not a cross-process ownership guarantee. `close()` stops admitting requests, aborts tracked requests, awaits settlement and disposes the runtime; it has no outer timeout. Preserve this cleanup with bounded supervision. Renulus already has hidden owned-child startup and teardown patterns to reuse. [Database][database], [owned fetch][fetch], [existing backend][renulus-backend]

| Ledger item | Minimal intervention and disposition |
| --- | --- |
| AH-01 artifact cohort | Build all twelve packages named by upstream SDK package verification from the selected SHA, preserving catalog pins/patches; rewrite local package references consistently. No mixing source Effect 4.0.1 with published rc.112 companions. Packaging work only. [Upstream verifier][verify] |
| AH-02 recovery gate | Prefer the service replacement above. Add a small host option only if necessary. Do not replace runner, durable storage or child coordination. |
| AH-03 neutral roots/discovery | Integration configuration and existing service overrides first. Optional SDK flag forwarding is the only presently justified discovery API patch. |
| AH-04 required-plugin readiness | Test failure before proposing changes. If host-wide policy can fail open, add a narrowly scoped activation/dispatch gate; current registration ordering alone does not close this gap. |

No ledger item was implemented.

**Exact proof candidate and next-wave gaps.**

Proposed tuple: selected source SHA; its `bun.lock` SHA-256 `3232687da07c15408130bc7b2eefd37364eb1e3ac9e61d2b779a3a6880b38d1c`; Bun 1.4.2 build tool; Effect 4.0.1 cohort; separate managed Node 24.21.0 Windows x64 host. Official Node checksum lists `node-v24.21.0-win-x64.zip` as `158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541`. The binary was not downloaded or run; its documented SQLite API includes the required methods. [Lock][lock], [root][root], [Node checksums][node-sums], [Node SQLite][node-sqlite]

Next wave should seal compiler/runtime/native/WASM hashes and licences, then prove: packed Node startup with developer tools absent; synthetic persistent reopen; delayed/failed policy activation before recovering parent/child claims; no dispatch while gated; duplicate-owner rejection; close during streaming and cleanup failure. Test without providers. Full Windows dependency closure, signatures, reproducible build, resource costs and all lifecycle behavior remain unproved. ARM64 and Electron embedding are separate candidates.

**Checks actually run.** Read required project/side-chat documents and relevant Renulus lifecycle code; fetched pinned raw source and exact registry metadata; inspected five tarballs in memory; verified five SRI digests and calculated their SHA-256; hashed the source lock; compared two raw tag files with supplied commit files. Eleven static assertions passed covering ordering, tag-file identity, Effect mismatch, tar integrity and missing public configuration controls. GitHub API attempts returned rate-limit 403; continued using raw files. No OpenCode host, build, install, service, inspected native binary or provider was executed. Parent context/image tests were not duplicated.

[root]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/package.json
[lock]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/bun.lock
[tag-host]: https://github.com/anomalyco/opencode/blob/9b4ec5714d481559990db0a816d5dec19541a814/packages/sdk/src/internal/host.ts
[tag-promise]: https://github.com/anomalyco/opencode/blob/9b4ec5714d481559990db0a816d5dec19541a814/packages/sdk/src/promise.ts
[sdk-reg]: https://registry.npmjs.org/@opencode%2Fsdk/2.0.26
[core-reg]: https://registry.npmjs.org/@opencode%2Fcore/2.0.26
[util-reg]: https://registry.npmjs.org/@opencode%2Futil/2.0.26
[server-reg]: https://registry.npmjs.org/@opencode%2Fserver/2.0.26
[pty-reg]: https://registry.npmjs.org/@lydell%2Fnode-pty-win32-x64/1.2.0-beta.12
[cli-reg]: https://registry.npmjs.org/opencode-ai/2.0.26
[sdk-tar]: https://registry.npmjs.org/@opencode/sdk/-/sdk-2.0.26.tgz
[promise]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/promise.ts
[host]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/host.ts
[registration]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin/sdk.ts
[instances]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/instances.ts
[restart]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution/restart.ts
[options]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/server/src/options.ts
[routes]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/server/src/routes.ts
[sdk-build]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/script/build.ts
[core-manifest]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/package.json
[sqlite]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/database/sqlite.node.ts
[pty]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/pty.ts
[pty-node]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/pty/pty.node.ts
[persistent-pty]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/persistent-pty/binary.node.ts
[photon]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/image/photon-wasm.node.ts
[parser]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/shell/parser-wasm.node.ts
[database]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/database/database.ts
[instance]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/instance.ts
[global]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/util/src/global.ts
[roots]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/util/src/global-roots.ts
[fetch]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/fetch.ts
[renulus-backend]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/apps/desktop/electron/backend.ts
[verify]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/script/verify-package.ts
[node-sums]: https://nodejs.org/dist/v24.21.0/SHASUMS256.txt
[node-sqlite]: https://nodejs.org/download/release/v24.21.0/docs/api/sqlite.html
