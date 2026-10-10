# OpenCode foundation cohort

2026-10-10. Attribution for the authorized H01 source cohort. Upstream is
[anomalyco/opencode](https://github.com/anomalyco/opencode/tree/4b6fea2875e4f2e3e8a8fee181803e54f7056845)
at commit `4b6fea2875e4f2e3e8a8fee181803e54f7056845`. The twelve selected
`@opencode/*` packages all identify as **2.0.26**, MIT. This is a source cohort;
the separately published SDK with the same version text is not interchangeable.
The parent built all twelve packages successfully. Materialization reads those
outputs without rebuilding them. See the
[cohort evidence](../../docs/research/2026-10-10-opencode-foundation-cohort.md).

| Pinned input | SHA-256 |
| --- | --- |
| [Source archive](https://codeload.github.com/anomalyco/opencode/tar.gz/4b6fea2875e4f2e3e8a8fee181803e54f7056845), **79,614,886 bytes** | `b50f959e4a072e10b81f73b144c3017e83e5c8fafcdefc381d627063c8c67761` |
| [Node 26.4.0 Windows x64 ZIP](https://nodejs.org/dist/v26.4.0/node-v26.4.0-win-x64.zip) | `5f87d038c6ec442aa46b9126f8ca170acbd2f3b9b9152ca798cf54596a31e214` |
| [Bun 1.4.2 Windows x64 standard ZIP](https://github.com/oven-sh/bun/releases/download/bun-v1.4.2/bun-windows-x64.zip) | `ce4c17497b2f29712a99d3d53f028de28cd42e3bacb8589599e7f000e49b6405` |
| Source `package.json` | `09ab22d46509f617157a1573a59d9a5868aa6d8f5556d758ee5415d8c5679abd` |
| Source `bun.lock` | `3232687da07c15408130bc7b2eefd37364eb1e3ac9e61d2b779a3a6880b38d1c` |
| Source and scoped [LICENSE](LICENSE) | `625f0f619133f89bbbb2abe37369613dfa1885eba1e50d02170deb62bb42cb6b` |

The source archive pin comes from the parent's verified acquisition. The
materialization lane independently rehashed both local tool ZIPs, the Node
executable, root manifest, lock, license and [patch inputs](PATCHES.md). Bun is the
developer build tool. Node 26.4.0 is the selected Windows host runtime, replacing
the earlier Node 24 proposal because the closure includes a Node >=26.4.0 engine
declaration. Archive hashes above are not executable-file hashes.
The Node executable SHA-256 is
`3193d7f751b8a07bd4acc70e81946ae9c6efdee83e07ad1c8d0e4089df7c5cef`.
The initial local receipt explicitly records `source_archive_verified: false`:
the materializer was given the built source tree, not the parent's archive path.
Passing `--source-archive` verifies the archive hash again during reproduction.

Use the public Effect entrypoint, `@opencode/sdk/effect`, with
`OpenCode.create(options, embed)` inside an Effect scope. At this commit the
public Promise wrapper at `@opencode/sdk` forwards only `options` and cannot
supply the embedding overrides; `@opencode/sdk/promise` is not exported.

The parent-owned preparation sequence is: acquire and verify the pinned source
and tool archives; extract the source to `C:/Renulus/scratch/ocf/src`; perform
the frozen filtered Bun install; apply the build bootstrap below; build the
twelve packages in verifier order; materialize the already resolved graph.
Bind `$sourceArchive`, `$mimeTypesArchive`, `$bun`, `$node` and `$python` to the
parent's acquired archives and managed executables first.
Use `C:/Renulus/dev/python/Scripts/python.exe` for `$python`. Extract only into a
fresh, short owned source directory and compare both tool ZIPs to the pins above.
The script's `recipe` command prints the pinned URLs and exact build/install argv;
it never downloads, installs or rebuilds on behalf of the caller. These are
reproduction commands; do not rerun the build while another owner is using it.
**Fresh-checkout acquisition and bootstrap are not automated or replayed end to
end by this lane.** The parent needed the following steps; the materializer is
verified against the resulting built tree, not an untouched extraction.

The filtered install includes `@opencode/script` as well as the twelve output
workspaces, theme, httpapi-codegen and http-recorder. Root `.bin` and TypeScript
were missing after filtering. The parent created these developer-only junctions,
which were subsequently verified read-only:

| Source-root junction | Source-root target |
| --- | --- |
| `node_modules/.bin` | `packages/ai/node_modules/.bin` |
| `node_modules/typescript` | `packages/ai/node_modules/typescript` — **5.8.2** |

The parent also acquired [@types/mime-types 3.0.1](https://registry.npmjs.org/@types/mime-types/-/mime-types-3.0.1.tgz)
separately into root `node_modules/@types/mime-types` for source compilation.
It is MIT and source-build-only. Its exact frozen `bun.lock` integrity is
`sha512-xRMsfuQbnRq1Ef+C+RKaENOxXX87Ygl38W1vDfPHRku02TgQr+Qd8iivLtAMcR0KF5/29xlnFihkTlbqFrGOVQ==`.
The parent's earlier tar SHA-256 receipt was not available in this lane; it is
explicitly unset in `build_bootstrap`, not guessed. The installed four files,
including `LICENSE`, were independently SHA-256 hashed and are listed in
`build_bootstrap` in the recipe and repository manifest. The archive can be
verified against the frozen SHA-512 below without downloading another copy:

```powershell
$repo = 'C:/Users/karol/.codex/worktrees/opencode-foundations/repo'
$sourceRoot = 'C:/Renulus/scratch/ocf/src'
if ((Get-Item -LiteralPath $sourceArchive).Length -ne 79614886 -or
    (Get-FileHash -Algorithm SHA256 -LiteralPath $sourceArchive).Hash -ne
    'b50f959e4a072e10b81f73b144c3017e83e5c8fafcdefc381d627063c8c67761') {
    throw 'Pinned source archive mismatch'
}
$buildOrder = @('schema', 'codemode', 'ai', 'util', 'protocol', 'client',
    'plugin', 'plugin-browser', 'core', 'simulation', 'server', 'sdk')
$buildWorkspaces = $buildOrder + @('theme', 'httpapi-codegen', 'http-recorder', 'script')
$filters = foreach ($name in $buildWorkspaces) { '--filter'; "@opencode/$name" }
$previousPath = $env:PATH
Push-Location $sourceRoot
try {
    $env:PATH = "$(Split-Path -Parent $bun);$(Split-Path -Parent $node);$sourceRoot/node_modules/.bin;$previousPath"
    & $bun install --frozen-lockfile --ignore-scripts @filters
    if ($LASTEXITCODE -ne 0) { throw 'Filtered frozen install failed' }
    # Bootstrap a fresh filtered installation; do not replace existing paths.
    $bootstrapLinks = @{
        'node_modules/.bin' = 'packages/ai/node_modules/.bin'
        'node_modules/typescript' = 'packages/ai/node_modules/typescript'
    }
    foreach ($entry in $bootstrapLinks.GetEnumerator()) {
        $link = [IO.Path]::GetFullPath("$sourceRoot/$($entry.Key)")
        $target = [IO.Path]::GetFullPath("$sourceRoot/$($entry.Value)")
        if (Test-Path -LiteralPath $link) {
            throw "Bootstrap path already exists; inspect its target before reuse: $link"
        }
        if (-not (Test-Path -LiteralPath $target)) { throw "Missing filtered target: $target" }
        New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    }
    $compiler = Get-Content -LiteralPath "$sourceRoot/node_modules/typescript/package.json" -Raw | ConvertFrom-Json
    if ($compiler.version -ne '5.8.2') { throw 'Expected frozen TypeScript 5.8.2' }
    $sha512 = [Security.Cryptography.SHA512]::Create()
    try {
        $mimeIntegrity = 'sha512-' + [Convert]::ToBase64String($sha512.ComputeHash([IO.File]::ReadAllBytes($mimeTypesArchive)))
    } finally { $sha512.Dispose() }
    if ($mimeIntegrity -ne 'sha512-xRMsfuQbnRq1Ef+C+RKaENOxXX87Ygl38W1vDfPHRku02TgQr+Qd8iivLtAMcR0KF5/29xlnFihkTlbqFrGOVQ==') {
        throw 'Pinned @types/mime-types archive mismatch'
    }
    $mimeRoot = "$sourceRoot/node_modules/@types/mime-types"
    if (Test-Path -LiteralPath $mimeRoot) { throw 'Inspect existing mime-types before reuse' }
    New-Item -ItemType Directory -Path $mimeRoot -Force | Out-Null
    & tar.exe -xzf $mimeTypesArchive -C $mimeRoot --strip-components=1
    if ($LASTEXITCODE -ne 0) { throw 'mime-types extraction failed' }
    $mimePackage = Get-Content -LiteralPath "$mimeRoot/package.json" -Raw | ConvertFrom-Json
    if ($mimePackage.version -ne '3.0.1') { throw 'Expected exact @types/mime-types 3.0.1' }
    foreach ($name in $buildOrder) {
        & $bun run --cwd "packages/$name" build
        if ($LASTEXITCODE -ne 0) { throw "Build failed: $name" }
    }
} finally {
    $env:PATH = $previousPath
    Pop-Location
}
& $python "$repo/scripts/prepare_opencode_cohort.py" materialize `
    --source $sourceRoot --output 'C:/Renulus/scratch/ocf/cohort' `
    --node $node --source-archive $sourceArchive
if ($LASTEXITCODE -ne 0) { throw 'Cohort materialization failed' }
```

Keep the pinned root catalog, overrides, lock and dependency patches. The
filtered build needs all four additional named workspaces, the explicit root
compiler/bin junction bootstrap, and the exact mime-types type artifact. These
are developer build inputs, not extra installed runtime cohort roots. No full/global installation,
new npm dependency graph, latest-tool fallback or registry SDK substitution is
part of this sequence. Do not run the complete upstream package verifier: its
fresh consumer installation and Workerd tail are outside this procedure.

The materializer physically copies the actual resolved Bun dependency graph,
including applicable patched bytes, native/WASM assets and notices. It preserves
dependency-specific resolution; a flat name-only lookup can select the wrong
version. All junction targets stay inside the fixed output
`C:/Renulus/scratch/ocf/cohort`; none may point back to source or a shared cache.
The output root exposes the twelve packages above plus `effect@4.0.1`,
`typescript@5.8.2` and `@types/node@24.12.2`. The latter two are build-only tools,
not doctor setup requirements. Theme's optional peer does not expand the
mandatory headless cohort to thirteen built packages. Its installed optional
peer resolution is retained as `auxiliary-workspace-source`; it is not a built
TUI deliverable. The root manifest declares the thirteen runtime roots under
`dependencies` and compiler/type roots under `devDependencies`. No development
dependency set is promoted wholesale.
The inventory's per-package roles describe graph reachability: TypeScript also
appears through the installed `bun-ffi-structs` peer, and Node types through
`bun-types`/`@types/ws`. Those bytes remain in the closed graph; they are not
commands exposed on the delivered host PATH.

Package manifest rewrites occur only in local staged copies: source exports
become emitted JavaScript/declaration paths using the upstream verifier's path
mapping, with core declarations under `dist/types/`. Export maps put `types`
before `import`; import conditions retain upstream insertion order. Sorting the
condition keys would put `default` before `node` and select Bun's `bun:ffi`
fallback. This ordering is runtime behavior, not cosmetic formatting.

Core's emitted NodeSocket chunk imports `@effect/platform-node/NodeSocket`,
although upstream declares the package under `devDependencies`. The staged core
manifest explicitly promotes that one installed `4.0.1` resolution to runtime.
Its sixteen-package reachable closure already belongs to the copied graph; no
new package resolution or acquisition is needed. Inspection of emitted files
found no other undeclared Node runtime dependency: the client/plugin references
to Effect and Solid are already covered by their existing peer dependencies.
The declarations are preserved byte for byte. The parent successfully checked
its consumer with TypeScript's Bundler resolution; NodeNext encounters upstream
extensionless declaration imports and is not claimed as passing.

The completed local output is `C:/Renulus/scratch/ocf/cohort`, containing **520
physical packages, 37,845 inventoried files and 1,235 internal junctions**. There
is exactly one physical Effect `4.0.1` package. The repository [cohort.json](cohort.json)
records every package's frozen artifact integrity, source-manifest hash, payload
tree hash, dependency edges, roles, license declarations and notice-file hashes.
`C:/Renulus/scratch/ocf/cohort/inventory.json` retains the complete per-file
size/SHA-256 list; its digest is recorded in `cohort.json` and `READY.json`.
The copied provenance directory retains the root manifest, frozen lock, upstream
license, all sixteen declared patch inputs and Node's license/third-party notices.

`materialize` requires a fresh output and fails on missing required dependencies,
source/Node pin mismatches or duplicate Effect instances. Both write commands
reject manifest destinations that overlap source, runtime inputs or the cohort,
including junction aliases and existing hard links. A completed copy first
has `MATERIALIZED.json` and remains `INCOMPLETE`. `record` adds provenance to that
copy without recopying packages; only successful sealing publishes `READY.json`
and removes `INCOMPLETE`. A missing license or patch cannot leave a ready cohort.
`verify` requires sealed provenance and rechecks the recorded payload bytes and
dependency junctions without consulting the source. The full audit passed for
the final 37,845-file, 1,235-junction inventory:

```powershell
& $python "$repo/scripts/prepare_opencode_cohort.py" verify `
    --output 'C:/Renulus/scratch/ocf/cohort'
```

All four SDK entrypoints in upstream's import check (`@opencode/sdk`, its
`/effect`, `/workerd` and `/workerd/effect` exports) import under pinned Node
26.4.0 with an isolated synthetic profile and runtime-only PATH; each exposes
its `create` function. This check does not construct a Workerd host. Ten synthetic
behavioral checks cover dependency-specific resolution after the source becomes
unavailable, source pin rejection, shared Effect, copied-byte tampering,
lock/patch/license receipts, conditional Node imports, the platform dependency
promotion, build-only root declarations, and failure to publish readiness when
provenance is incomplete, and unsafe manifest destinations. All 520 source manifests and the pinned source root
inputs still match their copy-time hashes. The test driver lives in the owned
scratch lane, `C:/Renulus/scratch/oc-foundations/cohort/test_materialize.py`; only
the five assigned cohort files belong to this repository change.

The parent additionally reports that the equivalent temporary `cohort/STAGING`
graph passed one scripted learning turn, real durable SQLite persistence,
close/reopen transcript equality and model-call count remaining one, plus
consumer typechecking. That is parent-reported host evidence; this lane's direct
runtime check is module import. STAGING stays available until the parent has
finished switching its harness junction. STAGING is a separate temporary copy
and is not included in the final inventory's payload or file count.

The scoped LICENSE is an exact copy of upstream's MIT text, including
`Copyright (c) 2025 opencode`. External packages and native assets retain their
own licenses and notices. Node includes third-party terms; Bun's complete
binary includes additional terms, including JavaScriptCore/WebKit LGPL notices,
and must not be described as MIT-only. Preserve the matching tool notices if
those artifacts are distributed.
Twenty-nine installed packages contain no notice file recognized by the inventory;
their declared license and manifest hash are retained and the absence is explicit.
This includes the optional theme workspace, whose source is covered by the copied
upstream MIT license. Completing missing third-party notices belongs to H20;
the cohort is not a redistribution-clearance claim.

Internal Windows junctions tie this development cohort to its current location.
Relocation, release packaging, complete redistribution attribution and H20
Windows acceptance remain pending. Green builds do not establish SDK execution,
provider behavior, installed delivery or acceptance of those remaining gates.
