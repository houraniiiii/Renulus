# H01 source cohort and Windows SDK proof

2026-10-10. Research sidecar for the authorized foundation implementation.
Renulus baseline: `c2bd896420fb88f76d63ca576414dbbba182f4c2`.
Only this document belongs to this lane. Parent owns acquisition, dependency
installation, source builds, host code and acceptance.

**Use the twelve-package source cohort and the public Effect SDK entrypoint.**
The public Promise wrapper does **not** forward embedding overrides at this
commit. This corrects the inference in W1/W2 from the internal Promise module.
A source-built import and a completed scripted turn/reopen are the first proofs;
neither has been executed by this research lane.

## Immediate build facts and traps

1. Build/pack in the upstream verifier's order:
   `schema → codemode → ai → util → protocol → client → plugin →
   plugin-browser → core → simulation → server → sdk`.
   All twelve are `@opencode/*@2.0.26`, MIT, from the selected SHA.
   The required workspace dependency closure is these twelve. Build/dev
   workspace dependencies add `theme`, `httpapi-codegen` and
   `http-recorder`. Theme is also an **optional** plugin peer; it is not a
   thirteenth mandatory headless runtime package.
   [Verifier](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/script/verify-package.ts),
   [plugin manifest](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin/package.json).

2. Bun **1.4.2** is the declared build tool. The root catalog pins TypeScript
   **5.8.2**, Effect and its platform packages **4.0.1**, and optional
   `tsgo` typechecking tooling
   `@typescript/native-preview@7.0.0-dev.20251207.1`.
   Builds run `tsc`, not `tsgo`.
   A filtered installation can omit the compiler shim visible to child
   builds: `codemode`, for example, calls `bun tsc` without its own
   TypeScript dependency. Supply the existing pinned compiler bin directory
   to the build child PATH; do not let a missing command trigger a latest
   package acquisition. Parent reported schema built, then this exact
   codemode failure. During subsequent read-only inspection root
   `node_modules/.bin/tsc.exe` and `tsc.bunx` were present.
   [Root catalog](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/package.json),
   [codemode build](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/codemode/script/build.ts).

3. Preserve the source root catalog, lock, patches and package configuration.
   Bun supports repeated `install --filter` selectors. A bounded install
   candidate selects the fifteen build workspaces above with
   `--frozen-lockfile --ignore-scripts`; this lane did not execute it.
   Parent reports its filtered frozen installation of **561 packages passed**.
   The entire upstream lock contains 3,890 package entries across 43
   workspace entries, not a minimal delivery inventory.
   [Bun workspace filtering](https://bun.sh/docs/pm/workspaces),
   [Bun installation](https://bun.sh/docs/pm/cli/install),
   [pinned lock](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/bun.lock).

4. Build output alone is insufficient: source manifests export `./src/*.ts`.
   The verifier translates `exports` and conditional `imports` to
   `dist/*.js` and declarations, using `dist/types/` for core declarations.
   It rewrites workspace dependencies to the already packed local archives,
   packs with scripts disabled, then restores each source manifest.
   Preserve the core Node conditions for SQLite, PTY, FFF and WASM resolvers.
   [Verifier](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/script/verify-package.ts),
   [core imports](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/package.json).

5. A fresh npm consumer installation does **not** carry the original Bun
   transitive lock or root `patchedDependencies`. Upstream's verifier
   deliberately uses `--package-lock=false` and is an import test, not a
   sealed reproducibility recipe. Parent should keep the resolved lock and
   applicable patched dependency bytes in the packaged cohort, or explicitly
   reproduce and verify them in the consumer. Record local archive hashes,
   external package integrity and applied patch hashes. For example, the
   source locks FFF's ranged `ffi-rs` dependency to **1.3.7**.
   Photon, MCP client, pacote, npm agent and provider dependencies have
   relevant root patches; do not assume packing an OpenCode package embeds
   these external changes.
   [Verifier](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/script/verify-package.ts),
   [patch map](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/package.json), [lock](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/bun.lock).

6. Keep `simulation: false` (or absent) for the scripted SDK proof.
   `simulation: true` applies its own replacements **after** caller
   overrides and can replace the intended test seam.
   The server declares simulation as a dependency even when disabled, so
   removing that package is a separately proved packaging change.
   [Composition](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/server/src/routes.ts#L113-L158).

7. The full verifier installs Wrangler **4.110.0**, tests Workerd, and deletes
   its temporary archives on exit. For H01's Node proof, adapt its pack
   sequence into a parent-owned staging script and retain artifacts;
   the Workerd tail is outside the required Windows proof.
   SDK/core/client/server emit external-package Node ESM; other packages
   also use TypeScript emission or Bun transpilation. A successful Bun
   source import is not a successful packed Node import.
   [SDK build](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/script/build.ts),
   [simulation build](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/simulation/script/build.ts).

## Identity, available tools and artifact provenance

| Item | Exact finding |
| --- | --- |
| Source | `4b6fea2875e4f2e3e8a8fee181803e54f7056845`; package version text remains 2.0.26 |
| Parent acquisition | [Source archive](https://codeload.github.com/anomalyco/opencode/tar.gz/4b6fea2875e4f2e3e8a8fee181803e54f7056845); parent reports 79,614,886 bytes and SHA-256 `b50f959e4a072e10b81f73b144c3017e83e5c8fafcdefc381d627063c8c67761`; archive bytes were not rehashed by this lane |
| Parent source tree | `C:/Renulus/scratch/ocf/src`, inspected read-only |
| Root manifest SHA-256 | `09ab22d46509f617157a1573a59d9a5868aa6d8f5556d758ee5415d8c5679abd`; local and raw source match |
| Lock SHA-256 | `3232687da07c15408130bc7b2eefd37364eb1e3ac9e61d2b779a3a6880b38d1c`; local and raw source match |
| Upstream MIT LICENSE SHA-256 | `625f0f619133f89bbbb2abe37369613dfa1885eba1e50d02170deb62bb42cb6b`; retain copyright and license in adoption |
| Distinct published SDK | [@opencode/sdk 2.0.26](https://registry.npmjs.org/@opencode%2fsdk/2.0.26) belongs to the older cohort with Effect `4.0.0-rc.112`; do not mix companions |
| Developer Node initially on PATH | `C:/Program Files/nodejs/node.exe`, observed `v24.15.0` |
| Bundled developer Node | `C:/Users/karol/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`, observed `v24.19.0` |
| Initial Bun/Python | Bun absent from PATH; `C:/Renulus/dev/python/Scripts/python.exe` reports Python 3.14.4 |
| Other initial commands | npm from `C:/Program Files/nodejs/npm.ps1`; pnpm shim under `C:/Users/karol/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm.cmd`; neither was used to install |
| Parent's new managed tools | Parent reports Bun 1.4.2 and Node 24.21.0 acquired under `C:/Renulus/scratch/ocf/tools` |

The inspected a11f `.local/research/opencode-v2-current-76cfdff` cache is a
**Renulus** source snapshot, not the pinned upstream OpenCode tree. It cannot
supply the SDK build. No private profile or credentials were inspected.

**Node compatibility qualification:** core's Node SQLite adapter needs
`DatabaseSync`, `setReadBigInts` and `setReturnArrays`.
The prior proposed Node 24.21.0 archive is
[node-v24.21.0-win-x64.zip](https://nodejs.org/dist/v24.21.0/node-v24.21.0-win-x64.zip),
with published SHA-256
`158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541`.
However, **@opentui/core 0.5.17**, pulled by simulation, declares
`node >=26.4.0` and `bun >=1.3.0`.
Therefore Node 24.x does not meet every declared engine requirement of the
complete package closure. An observed headless import/turn on 24.x must retain
that qualification; evaluate Node 26.4.0+ if requiring all Node engine
declarations to be satisfied. Bun-only conditional packages remain separately
qualified. This is not a proposal to change the parent's runtime silently.
[SQLite adapter](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/database/sqlite.node.ts),
[Node checksums](https://nodejs.org/dist/v24.21.0/SHASUMS256.txt),
[OpenTUI metadata](https://registry.npmjs.org/@opentui%2fcore/0.5.17).

The delegated runtime check executed an in-memory SQLite probe on both installed
Nodes: 24.15.0 (SQLite 3.51.3) and 24.19.0 (SQLite 3.53.3). Both passed
`DatabaseSync`, integer/array settings, exact `9007199254740993n` round-trip,
parameterized reads, blob/null handling, timeout and foreign-key checks.
Neither probe was an OpenCode import or host test. The pnpm shim reports
11.25.0 and explicitly launches the bundled Node 24.19.0, so invoking pnpm
does not necessarily use the Node selected on PATH.

Additional official artifacts, queried without downloading binaries:

| Artifact | Published SHA-256 |
| --- | --- |
| [Node 26.4.0 Windows x64](https://nodejs.org/dist/v26.4.0/node-v26.4.0-win-x64.zip) | `5f87d038c6ec442aa46b9126f8ca170acbd2f3b9b9152ca798cf54596a31e214` |
| [Bun 1.4.2 Windows x64](https://github.com/oven-sh/bun/releases/download/bun-v1.4.2/bun-windows-x64.zip) | `ce4c17497b2f29712a99d3d53f028de28cd42e3bacb8589599e7f000e49b6405` |
| [Bun 1.4.2 Windows x64 baseline](https://github.com/oven-sh/bun/releases/download/bun-v1.4.2/bun-windows-x64-baseline.zip) | `78c221c2376f79731ccf4e4af0b3bb46d81fefa3296c5abee09ad8a1b21e68c6` |

The URLs returned HTTP 200 to HEAD. These are publisher hashes, not independent
binary hashes. Sources: [Node 26 checksums](https://nodejs.org/dist/v26.4.0/SHASUMS256.txt),
[Bun checksums](https://github.com/oven-sh/bun/releases/download/bun-v1.4.2/SHASUMS256.txt).
Node's license includes MIT and bundled third-party terms. Bun's own code is
MIT, but its versioned notice also identifies LGPL JavaScriptCore/WebKit and
other linked libraries; do not label its complete binary MIT-only. Bun is a
developer build dependency in the Node delivery design.
[Node license](https://raw.githubusercontent.com/nodejs/node/v24.21.0/LICENSE),
[Bun license](https://raw.githubusercontent.com/oven-sh/bun/bun-v1.4.2/LICENSE.md).

## Verified imports and construction seam

The **public** imports with embedding support are:

```ts
import { OpenCode, AbsolutePath, Location } from "@opencode/sdk/effect";
import { LanguageModel, LLMClient } from "@opencode/ai";
import { OpenAIChat } from "@opencode/ai/protocols";
import { TestLLM } from "@opencode/ai/testing";
import { llmClient } from "@opencode/core/effect/app-node-platform";
import { SessionRunnerModel } from "@opencode/core/session/runner/model";
import { SessionRestart } from "@opencode/core/session/execution/restart";
import { Config } from "@opencode/core/config";
import { InstructionDiscovery } from "@opencode/core/instruction-discovery";
import { Global } from "@opencode/util/global";
import { Context, Effect, Latch, Layer } from "effect";
```

`@opencode/core` has wildcard subpath exports; use the concrete subpaths above.
`@opencode/sdk/promise` is not exported. The internal
`PromiseSdk.create(options, embed)` is not equivalent to public
`OpenCode.create` from `@opencode/sdk`, whose wrapper forwards only one
argument. The public Effect entrypoint forwards both arguments and releases
the host through its Effect scope; `OpenCode.layer(options)` itself does not
accept the second argument.
[Promise wrapper](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/opencode.ts),
[Effect wrapper](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/effect/opencode.ts),
[SDK exports](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/package.json).

This source-derived construction example belongs inside `Effect.gen`,
executed within `Effect.scoped`. It is **not an executed receipt**. The parent
must supply the owned absolute directories and the recovery replacement
described below, after establishing process ownership and neutral child
environment:

```ts
const llm = yield* TestLLM.Test.pipe(Effect.provide(TestLLM.testLayer()));
yield* llm.push(TestLLM.text("Synthetic renal learning answer.", "answer"));
const model = SessionRunnerModel.resolved(
  LanguageModel.make({
    id: "h01-scripted", provider: "renulus-test", route: OpenAIChat.route,
  }),
  {
    capabilities: { tools: true, input: ["text"], output: ["text"] },
    cost: [], limit: { context: 128_000, output: 4_096 },
  },
);
const opencode = yield* OpenCode.create(
  {
    database: { path: ownedDatabasePath },
    config: { directory: ownedConfigPath, project: false, content: "{}" },
    models: { fetch: false },
    events: { persist: false },
    fs: { filewatcher: false, fff: false },
  },
  {
    overrides: [
      Global.node.replace(Global.layerWith(ownedGlobalPaths)),
      Config.node.replace(Config.configured({
        project: false, global: false, content: "{}",
      })),
      InstructionDiscovery.node.replace(InstructionDiscovery.configured({
        project: false, global: false,
      })),
      llmClient.replace(Layer.succeed(LLMClient.Service, llm)),
      SessionRunnerModel.node.replace(Layer.succeed(
        SessionRunnerModel.Service, { resolve: () => Effect.succeed(model) },
      )),
      recoveryReplacement,
    ],
  },
);
const session = yield* opencode.sessions.create({
  title: "H01 synthetic conversation",
  location: Location.Ref.make({
    directory: AbsolutePath.make(ownedWorkspacePath),
  }),
  model: model.ref,
  metadata: { operation: "h01-synthetic" },
});
yield* opencode.sessions.prompt({
  sessionID: session.id, text: "Return the synthetic learning answer.",
});
yield* opencode.sessions.wait({ sessionID: session.id });
const transcript = (yield* opencode.message.list({
  sessionID: session.id, order: "asc",
})).data;
const requests = yield* llm.requests();
```

The fixed title avoids automatic title generation; do not give TestLLM a
fallback in the one-turn count test. Unexpected calls then fail. Check exactly
one request, and an assistant message with
`type === "assistant"` and a `content` item
`{ type: "text", text: "Synthetic renal learning answer." }`.
These are synthetic model identities, never alternative product model choices.
[Upstream recovery fixture](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/test/instances-effect.test.ts),
[TestLLM](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/ai/src/testing.ts),
[model seam](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/runner/model.ts),
[title trigger](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/runner/llm.ts#L174-L179),
[message schema](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/schema/src/session-message.ts).

Next, save the session identity, let the first Effect scope close completely,
then construct a second host against the same owned database. Use
`sessions.get({ sessionID })` and `message.list({ sessionID, order: "asc" })`
to compare identity and transcript. Do not prompt on reopen. Use a fresh
counting TestLLM with no queued responses and assert **zero** calls. Reopening
a completed conversation should not require a recovery replay. Read the
transcript through the SDK, not direct SQL. Separately test active interruption
using `TestLLM.hangAfter()` and explicit recovery-gate release.
[Read/reopen prior art](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/test/instances.test.ts#L223-L292),
[interrupted recovery prior art](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/test/instances-effect.test.ts#L28-L143).

Observe live notifications using the Effect stream
`opencode.events.subscribe()`; the Promise API uses an AsyncIterable.
`sessions.log` historical replay depends on retained events. Keep
`events.persist:false` for the product-aligned proof and use canonical
message projections for durable transcript assertions. A separately named
synthetic event-replay test may enable retention; do not conflate these.
[Bus implementation](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/bus.ts),
[Promise stream tests](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/test/promise.test.ts).

## Recovery gating and isolation hazards

A dependency-preserving replacement can acquire the original recovery service
immediately and delay **invocation**, with an interruptible latch:

```ts
const ready = yield* Latch.make(); // closed initially
const recoveryReplacement = SessionRestart.node.replace(
  SessionRestart.node.mapLayer(raw => Layer.flatMap(raw, services => {
    const original = Context.get(services, SessionRestart.Service);
    return Layer.succeed(SessionRestart.Service, {
      resumeSuspendedSessions: ready.await.pipe(
        Effect.andThen(original.resumeSuspendedSessions),
      ),
    });
  })),
);
```

This pattern is source-derived, not typechecked or run in this lane. Readiness
must validate actual policy and domain availability. Do not wait during layer
acquisition: host creation acquires its context **before** plugin registration
and before returning. That creates a construction deadlock. Plugin registration
is not successful activation; failed/reloaded policy must close admission.
[Host order](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/host.ts),
[graph contract](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/util/src/effect/layer-node.ts),
[W2 evidence](2026-10-10-opencode-integration/w2-02-dispatch-recovery.md).

The sweep assumes previous owners are dead and performs at-least-once recovery.
`maxAttempts:0` increments the attempt counter and terminalizes claims; it
does not pause. A downstream model denial can also settle a claim as failed.
Keep the whole sweep gated until uncertain-dispatch decisions are resolved.
If fresh work has been admitted while recovery waits, closing admission and
settling child ownership must precede gate opening: child-claim cleanup can
otherwise clear a fresh foreground child's claim. Selective per-session
deferral is still unproved.
[Restart](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution/restart.ts),
[claim cleanup](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/store.ts#L194-L250),
[W3 adversarial finding](2026-10-10-opencode-integration/w3-04-host-proof-adversary.md).

Set owned XDG data/config/cache/state roots, `OPENCODE_TEST_HOME` and the child
process's temporary directory **before importing OpenCode**. Use a sanitized
child environment without provider credentials. Supply all nine Global paths
(`home,data,cache,config,state,tmp,bin,log,repos`) through `Global.layerWith`.
The global module sets lock state on import; `app.name` does not isolate it.
SDK options omit the internal `config.global` switch, hence the explicit
Config and InstructionDiscovery replacements above. Explicit file-backed
settings, well-known config and use-triggered instructions are separate
surfaces; retain empty synthetic configuration and a network-denied proof.
[Globals](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/util/src/global.ts),
[roots](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/util/src/global-roots.ts),
[neutral composition](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/instance.ts).

A second writer must be rejected by Renulus before constructing a host.
SQLite migration locks do not establish exclusive process ownership.
Scope closure cancels host-owned work but has no outer supervision timeout.
Record a shutdown timeout as blocked/uncertain ownership, not successful
handoff. These remain parent H01 acceptance tests.
[Database](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/database/database.ts),
[owned fetch cleanup](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/fetch.ts),
[H01 ticket](../planning/opencode-v2/tickets/01-run-a-persistent-headless-opencode-conversation.md).

## Native files, WASM and licenses

Keep platform artifacts and their notices when materializing the actual
consumer. Disabled behavior is not evidence that its dependency can be
deleted. No native module was loaded by this lane.

| Surface | Pinned source requirement and public artifact |
| --- | --- |
| Ordinary Node PTY | `@lydell/node-pty@1.2.0-beta.12` plus [Windows x64 artifact](https://registry.npmjs.org/@lydell/node-pty-win32-x64/-/node-pty-win32-x64-1.2.0-beta.12.tgz); preserve `conpty.node`, `conpty_console_list.node`, `conpty.dll`, `OpenConsole.exe` layout and included notices |
| Persistent PTY | `@opencode-ai/pty@0.2.0`; Node adapter marks Windows unavailable. No persistent-terminal claim |
| File watcher | `@parcel/watcher@2.5.1` and [win32-x64 package metadata](https://registry.npmjs.org/@parcel%2fwatcher-win32-x64/2.5.1) |
| FFF | `@ff-labs/fff-node@0.10.5`, [fff-bin-win32-x64](https://registry.npmjs.org/@ff-labs%2ffff-bin-win32-x64/0.10.5), `ffi-rs@1.3.7`, [ffi Windows x64](https://registry.npmjs.org/@yuuang%2fffi-rs-win32-x64-msvc/1.3.7); `fff-bun@0.10.5` belongs to the Bun path |
| Photon | `@silvia-odwyer/photon-node@0.3.4`, Apache-2.0, `photon_rs_bg.wasm`; preserve upstream patch and asset |
| Parser | MIT packages `web-tree-sitter@0.25.10`, `tree-sitter-bash@0.25.0`, `tree-sitter-powershell@0.25.10`; preserve `tree-sitter.wasm`, `tree-sitter-bash.wasm`, `tree-sitter-powershell.wasm` |

Source:
[Node PTY](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/pty/pty.node.ts),
[persistent PTY](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/persistent-pty/binary.node.ts),
[Photon resolver](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/image/photon-wasm.node.ts),
[parser resolver](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/shell/parser-wasm.node.ts).

The full lock also contains a top-level Windows ffi native package at 1.3.2,
and a nested `ffi-rs/@yuuang/ffi-rs-win32-x64-msvc` entry at 1.3.7. Resolve by
the actual package dependency path when sealing the FFF closure; a flat
name-only lookup can select the wrong binary. Both registry versions declare
MIT. [Lock](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/bun.lock).

The four path overrides are `OPENCODE_PHOTON_WASM_PATH`,
`OPENCODE_TREE_SITTER_WASM_PATH`,
`OPENCODE_TREE_SITTER_BASH_WASM_PATH` and
`OPENCODE_TREE_SITTER_POWERSHELL_WASM_PATH`.
The normal resolvers use `createRequire(import.meta.url).resolve(...)`, so a
JS-only bundle is insufficient. Upstream's PTY postinstall only repairs Unix
spawn-helper permissions and does nothing on Windows.
[PTY fix script](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/script/fix-node-pty.ts).

## Exact direct external dependency register

These are **all 61 distinct direct runtime dependencies** across the twelve
source package manifests after expanding `catalog:`. Each link is the
tarball URL returned by that exact version's public npm metadata; every
metadata response also supplied `dist.integrity`. Licenses below are
registry declarations, not a completed transitive notice audit or a claim
that the tarballs were downloaded. The pinned Bun lock governs transitive
versions; the entire actual installed closure still needs parent inventory
and license-file preservation. Apache-2.0, ISC, BSD-3-Clause and BlueOak
dependencies must not be relabeled MIT.

| Public artifact | Version | Declared license |
| --- | --- | --- |
| [@ai-sdk/cohere](https://registry.npmjs.org/@ai-sdk/cohere/-/cohere-3.0.27.tgz) | 3.0.27 | Apache-2.0 |
| [@ai-sdk/perplexity](https://registry.npmjs.org/@ai-sdk/perplexity/-/perplexity-3.0.26.tgz) | 3.0.26 | Apache-2.0 |
| [@ai-sdk/provider](https://registry.npmjs.org/@ai-sdk/provider/-/provider-3.0.8.tgz) | 3.0.8 | Apache-2.0 |
| [@ai-sdk/provider-utils](https://registry.npmjs.org/@ai-sdk/provider-utils/-/provider-utils-4.0.23.tgz) | 4.0.23 | Apache-2.0 |
| [@ai-sdk/vercel](https://registry.npmjs.org/@ai-sdk/vercel/-/vercel-2.0.39.tgz) | 2.0.39 | Apache-2.0 |
| [@aws-sdk/credential-providers](https://registry.npmjs.org/@aws-sdk/credential-providers/-/credential-providers-3.1057.0.tgz) | 3.1057.0 | Apache-2.0 |
| [@effect/opentelemetry](https://registry.npmjs.org/@effect/opentelemetry/-/opentelemetry-4.0.1.tgz) | 4.0.1 | MIT |
| [@effect/platform-node](https://registry.npmjs.org/@effect/platform-node/-/platform-node-4.0.1.tgz) | 4.0.1 | MIT |
| [@effect/platform-node-shared](https://registry.npmjs.org/@effect/platform-node-shared/-/platform-node-shared-4.0.1.tgz) | 4.0.1 | MIT |
| [@ff-labs/fff-bun](https://registry.npmjs.org/@ff-labs/fff-bun/-/fff-bun-0.10.5.tgz) | 0.10.5 | MIT |
| [@ff-labs/fff-node](https://registry.npmjs.org/@ff-labs/fff-node/-/fff-node-0.10.5.tgz) | 0.10.5 | MIT |
| [@lydell/node-pty](https://registry.npmjs.org/@lydell/node-pty/-/node-pty-1.2.0-beta.12.tgz) | 1.2.0-beta.12 | MIT |
| [@modelcontextprotocol/client](https://registry.npmjs.org/@modelcontextprotocol/client/-/client-2.0.0.tgz) | 2.0.0 | MIT |
| [@modelcontextprotocol/core](https://registry.npmjs.org/@modelcontextprotocol/core/-/core-2.0.0.tgz) | 2.0.0 | MIT |
| [@npmcli/arborist](https://registry.npmjs.org/@npmcli/arborist/-/arborist-9.4.0.tgz) | 9.4.0 | ISC |
| [@npmcli/config](https://registry.npmjs.org/@npmcli/config/-/config-10.8.1.tgz) | 10.8.1 | ISC |
| [@opencode-ai/pty](https://registry.npmjs.org/@opencode-ai/pty/-/pty-0.2.0.tgz) | 0.2.0 | MIT |
| [@opentelemetry/api](https://registry.npmjs.org/@opentelemetry/api/-/api-1.9.0.tgz) | 1.9.0 | Apache-2.0 |
| [@opentelemetry/api-logs](https://registry.npmjs.org/@opentelemetry/api-logs/-/api-logs-0.219.0.tgz) | 0.219.0 | Apache-2.0 |
| [@opentelemetry/context-async-hooks](https://registry.npmjs.org/@opentelemetry/context-async-hooks/-/context-async-hooks-2.8.0.tgz) | 2.8.0 | Apache-2.0 |
| [@opentelemetry/exporter-trace-otlp-http](https://registry.npmjs.org/@opentelemetry/exporter-trace-otlp-http/-/exporter-trace-otlp-http-0.219.0.tgz) | 0.219.0 | Apache-2.0 |
| [@opentelemetry/resources](https://registry.npmjs.org/@opentelemetry/resources/-/resources-2.8.0.tgz) | 2.8.0 | Apache-2.0 |
| [@opentelemetry/sdk-logs](https://registry.npmjs.org/@opentelemetry/sdk-logs/-/sdk-logs-0.219.0.tgz) | 0.219.0 | Apache-2.0 |
| [@opentelemetry/sdk-metrics](https://registry.npmjs.org/@opentelemetry/sdk-metrics/-/sdk-metrics-2.8.0.tgz) | 2.8.0 | Apache-2.0 |
| [@opentelemetry/sdk-trace-base](https://registry.npmjs.org/@opentelemetry/sdk-trace-base/-/sdk-trace-base-2.8.0.tgz) | 2.8.0 | Apache-2.0 |
| [@opentelemetry/sdk-trace-node](https://registry.npmjs.org/@opentelemetry/sdk-trace-node/-/sdk-trace-node-2.8.0.tgz) | 2.8.0 | Apache-2.0 |
| [@opentui/core](https://registry.npmjs.org/@opentui/core/-/core-0.5.17.tgz) | 0.5.17 | MIT |
| [@parcel/watcher](https://registry.npmjs.org/@parcel/watcher/-/watcher-2.5.1.tgz) | 2.5.1 | MIT |
| [@silvia-odwyer/photon-node](https://registry.npmjs.org/@silvia-odwyer/photon-node/-/photon-node-0.3.4.tgz) | 0.3.4 | Apache-2.0 |
| [@smithy/eventstream-codec](https://registry.npmjs.org/@smithy/eventstream-codec/-/eventstream-codec-4.2.14.tgz) | 4.2.14 | Apache-2.0 |
| [@smithy/util-utf8](https://registry.npmjs.org/@smithy/util-utf8/-/util-utf8-4.2.2.tgz) | 4.2.2 | Apache-2.0 |
| [@standard-schema/spec](https://registry.npmjs.org/@standard-schema/spec/-/spec-1.1.0.tgz) | 1.1.0 | MIT |
| [acorn](https://registry.npmjs.org/acorn/-/acorn-8.15.0.tgz) | 8.15.0 | MIT |
| [aws4fetch](https://registry.npmjs.org/aws4fetch/-/aws4fetch-1.0.20.tgz) | 1.0.20 | MIT |
| [bun-pty](https://registry.npmjs.org/bun-pty/-/bun-pty-0.4.9.tgz) | 0.4.9 | MIT |
| [cross-spawn](https://registry.npmjs.org/cross-spawn/-/cross-spawn-7.0.6.tgz) | 7.0.6 | MIT |
| [diff](https://registry.npmjs.org/diff/-/diff-8.0.4.tgz) | 8.0.4 | BSD-3-Clause |
| [drizzle-orm](https://registry.npmjs.org/drizzle-orm/-/drizzle-orm-1.0.0-rc.5-169397b.tgz) | 1.0.0-rc.5-169397b | Apache-2.0 |
| [effect](https://registry.npmjs.org/effect/-/effect-4.0.1.tgz) | 4.0.1 | MIT |
| [fuzzysort](https://registry.npmjs.org/fuzzysort/-/fuzzysort-3.1.0.tgz) | 3.1.0 | MIT |
| [gitlab-ai-provider](https://registry.npmjs.org/gitlab-ai-provider/-/gitlab-ai-provider-6.19.0.tgz) | 6.19.0 | MIT |
| [glob](https://registry.npmjs.org/glob/-/glob-13.0.5.tgz) | 13.0.5 | BlueOak-1.0.0 |
| [google-auth-library](https://registry.npmjs.org/google-auth-library/-/google-auth-library-10.5.0.tgz) | 10.5.0 | Apache-2.0 |
| [gray-matter](https://registry.npmjs.org/gray-matter/-/gray-matter-4.0.3.tgz) | 4.0.3 | MIT |
| [htmlparser2](https://registry.npmjs.org/htmlparser2/-/htmlparser2-8.0.2.tgz) | 8.0.2 | MIT |
| [http-proxy-agent](https://registry.npmjs.org/http-proxy-agent/-/http-proxy-agent-7.0.2.tgz) | 7.0.2 | MIT |
| [https-proxy-agent](https://registry.npmjs.org/https-proxy-agent/-/https-proxy-agent-7.0.6.tgz) | 7.0.6 | MIT |
| [immer](https://registry.npmjs.org/immer/-/immer-11.1.4.tgz) | 11.1.4 | MIT |
| [jose](https://registry.npmjs.org/jose/-/jose-6.0.11.tgz) | 6.0.11 | MIT |
| [jsonc-parser](https://registry.npmjs.org/jsonc-parser/-/jsonc-parser-3.3.1.tgz) | 3.3.1 | MIT |
| [mime-types](https://registry.npmjs.org/mime-types/-/mime-types-3.0.2.tgz) | 3.0.2 | MIT |
| [minimatch](https://registry.npmjs.org/minimatch/-/minimatch-10.2.5.tgz) | 10.2.5 | BlueOak-1.0.0 |
| [npm-package-arg](https://registry.npmjs.org/npm-package-arg/-/npm-package-arg-13.0.2.tgz) | 13.0.2 | ISC |
| [open](https://registry.npmjs.org/open/-/open-11.0.4.tgz) | 11.0.4 | MIT |
| [pacote](https://registry.npmjs.org/pacote/-/pacote-21.5.1.tgz) | 21.5.1 | ISC |
| [tree-sitter-bash](https://registry.npmjs.org/tree-sitter-bash/-/tree-sitter-bash-0.25.0.tgz) | 0.25.0 | MIT |
| [tree-sitter-powershell](https://registry.npmjs.org/tree-sitter-powershell/-/tree-sitter-powershell-0.25.10.tgz) | 0.25.10 | MIT |
| [web-tree-sitter](https://registry.npmjs.org/web-tree-sitter/-/web-tree-sitter-0.25.10.tgz) | 0.25.10 | MIT |
| [which](https://registry.npmjs.org/which/-/which-6.0.1.tgz) | 6.0.1 | ISC |
| [ws](https://registry.npmjs.org/ws/-/ws-8.21.0.tgz) | 8.21.0 | MIT |
| [zod](https://registry.npmjs.org/zod/-/zod-4.1.8.tgz) | 4.1.8 | MIT |

## Evidence boundary and parent's next checks

This lane read H01/S1 and W1/W2/W3 findings, inspected the authorized public
cache and selected source tree, compared manifest/lock hashes, enumerated
workspace/direct dependency closure, and queried exact public registry
metadata. It did not install dependencies, run OpenCode, execute a provider,
edit manifests or implement a host.

Parent-reported acquisition/build progress is explicitly attributed above.
To close the remaining proof, retain build and package hashes plus licenses;
check the public Effect imports from the isolated consumer; construct with
developer tools absent from the **host** PATH; complete one counted scripted
turn and a no-generation reopen; then exercise failed/delayed policy,
interrupted recovery, competing ownership and bounded shutdown. Do not mark
those acceptance gates passed from this document. The later executed runtime
proofs are recorded separately in the [H01 implementation evidence](../implementation/opencode-foundations-h01.md)
and [actual SDK IPC evidence](../implementation/opencode-foundations-ipc.md).
