# OpenCode cohort patch provenance

2026-10-10; upstream commit
`4b6fea2875e4f2e3e8a8fee181803e54f7056845`. Source manifests remain unchanged.
See [UPSTREAM.md](UPSTREAM.md) for the pinned inputs and procedure.

## Renulus narrow capability injection (2026-10-27)

`packages/backend/src/domain/capabilities/native-patch.mjs` applies only to validated,
owned copies of published 2.0.26 (MIT); never the shared cohort. It substitutes the
Code Mode web extension, MCP transport/credential boundary and browser attachment/tunnel
factories, preserving native execution/protocols. The exact-source test loader applies the
same transformations in memory. Six original-file SHA-256 preconditions:

| Published file | Original SHA-256 |
| --- | --- |
| `core/dist/chunks/agent-82v73sw7.js` | `d80823d0ba4fa9978972aa792684a9c7a082c8ddf3055eb07e197246ac8bfb33` |
| `core/dist/chunks/agent-63648xmm.js` | `a7cccd5a258c37811932306639029f3e56593b599813e2c303385f415a7d59c3` |
| `core/dist/mcp/client.js` | `0d97f9cb1f7540eb75e2be40f21c4c6ed5fce9e58be3711e2dcfe18f684650f5` |
| `core/dist/chunks/agent-4ahpts8n.js` | `fc5b998e53031c185e2391eca6985e9d712224e6ec557f65386c267d2cee31ef` |
| `plugin-browser/dist/connection.js` | `b78bd47fb5321a1248e8b3c1feeee47d0af0995d4d63278a648cc07b591b51e8` |
| `plugin-browser/dist/files.js` | `2403d98ac1f526344fe57b62d2785bcd6b162287f7bd174a23750d704ee08386` |

The `plugin-browser/dist/files.js` change roots browser exports in the owned
`renulus.browser.downloads` directory and refuses an absent root. Remove this
change when upstream accepts an application-owned export directory and the
connected browser export journey proves every exported file stays within it
without this transformation.

The patch also emits `core/dist/renulus-boundary.js`; it has no upstream original.
Remove when upstream exposes equivalent per-attempt web/MCP and browser attachment/tunnel
factories and the native execute journey passes redirect, byte-limit, revocation and
header-denial assertions without the patch. This is not full packaged acceptance.

The source root `package.json` declares the dependency patches below. These are
upstream-authored inputs, not Renulus patches. SHA-256 values were computed
directly from `C:/Renulus/scratch/ocf/src/patches/`. Retain the patch inputs and
the already installed dependency bytes; materialization must not resolve a new
npm graph or discard upstream patches by repacking only the OpenCode packages.

This register includes all sixteen root declarations so unused entries are not
mistaken for missing provenance. Exact matching versions were observed in the
filtered Bun store for **openai-compatible 2.0.41, npmcli/agent 4.0.2,
photon-node 0.3.4, solid-js 1.9.15, pacote 21.5.1, fff-bun 0.10.5 and MCP
client 2.0.0**. Presence alone does not prove patch application or inclusion in
the final runtime closure: the materializer's resolved dependency inventory and
per-file hashes must identify the bytes actually copied. In particular, the
observed `gcp-metadata` version is 8.1.4, so the 8.1.2 patch must not be claimed
as applied to it. Preserve exact versions and conditional dependencies.

Paths below are relative to the pinned source root; `%2F` is literal in patch
filenames. Each row identifies the root patch input, including declarations not
selected by the filtered installation.

| Upstream patch file | SHA-256 |
| --- | --- |
| `patches/@ai-sdk%2Fopenai-compatible@2.0.41.patch` | `b26cf35cfbeb627144c9d03eb1cd3f101022970e8e011071aae5d3e65d353acb` |
| `patches/@dnd-kit%2Fdom@0.5.0.patch` | `d5def8da059568be2116dfbae14c0671a7db12b19cdb8b5462860ec1ea9c4c26` |
| `patches/@npmcli%2Fagent@4.0.2.patch` | `6c3354fde497bc6a310b15e87b3c5675f066b738235ebffa82e0da90e2cfff84` |
| `patches/@silvia-odwyer%2Fphoton-node@0.3.4.patch` | `2f276dcd71b0c6c2c6b77ce56b764e57ee323211e4ccd2c22524b28e8fc4a0f4` |
| `patches/@standard-community%2Fstandard-openapi@0.2.9.patch` | `4c6248f000365bd4af943a672532d6bdeb179f46e6831d05d4f2f1ecc4d6e439` |
| `patches/solid-js@1.9.15.patch` | `8c25ae5b542df14000ecc3b2a5f3571f6153b8ed3ad15ab8c63a1dd6e60d31e4` |
| `patches/@ai-sdk%2Fmistral@3.0.51.patch` | `ecab65795923de8e06f078fb678e933177e2dd9861331601ce8a7ca9d01addec` |
| `patches/gcp-metadata@8.1.2.patch` | `a5801ed5ab632cbdd21cc91628f1bd9cc6b37eaabb840c769e074f46d87bdf4b` |
| `patches/pacote@21.5.1.patch` | `a79e5adfb1d2117ec76b982a49cd39984538753ef979a7db334db1eb3d3966bc` |
| `patches/@ai-sdk%2Fgoogle@3.0.73.patch` | `891e385c92e0bbda8172dc495bba7ca5c7f33a33a117e2c453354fce483dc682` |
| `patches/@pierre%2Ftrees@1.0.0-beta.4.patch` | `9288191ef74b71771dc9299d822c0a3751ca743a88ab92987650e6a4f89d45e4` |
| `patches/@tanstack%2Fvirtual-core@3.17.8.patch` | `2f02fc0b9852a086631ef59466b726330b67c72ca0127c681c53cc0242708fda` |
| `patches/@ff-labs%2Ffff-bun@0.10.5.patch` | `d4650123a98a1c979f992ac562fc9e4115edc90611958f1b5764a40cb0d7edf6` |
| `patches/ghostty-web@0.3.0.patch` | `2359f429bfc29fb87b116febef710147e0fb5f48ebd9f657e72be0973e9cb01b` |
| `patches/vite@8.2.2.patch` | `cca700c4480e08621de8c9ee38dfc003ccdf7229d23a7df222ed40d07e68b9d7` |
| `patches/@modelcontextprotocol%2Fclient@2.0.0.patch` | `fbc462b1c513ba438594f1dd904e54456a0c0ee5181e5bd1dbfdd4d3040a0bc9` |

The Ghostty declaration targets
`ghostty-web@github:anomalyco/ghostty-web#83c0a07`, despite the patch filename's
0.3.0 suffix. Additional source helpers such as `install-korean-ime-fix.sh` are
not root `patchedDependencies` and are not part of this patch register.

The local materialization changes only staged manifests: source export paths
become emitted JavaScript/declaration paths, `types` comes before `import`, and
conditional import order is preserved. Core additionally promotes the existing
frozen `@effect/platform-node@4.0.1` dependency because its emitted NodeSocket
chunk imports it at runtime. No upstream source, emitted JavaScript, declaration,
native binary or dependency patch input is edited.

The completed inventory stores all sixteen copied patch input hashes and the
exact copied-package IDs matching each patch declaration. Packages without a
matching declaration are not labelled patched. Matching alone remains distinct
from independently comparing the patch against an unmodified registry artifact.

This records input provenance, not redistribution clearance or H20 acceptance.
See `cohort.json` and the local full inventory for the materialized byte identities.

## MCP injection evidence and removal condition — October 27, 2026

| Surface / pinned emitted files | Injection and connected evidence | Removal condition |
| --- | --- | --- |
| MCP: core `dist/mcp/client.js`, `dist/chunks/agent-4ahpts8n.js`, `dist/chunks/agent-63648xmm.js` | Existing `CapabilityBoundary.mcp` supplies credential-free fetch / Effect local transport / scoped close; stock OAuth provider and request headers are disabled. `mcpTool` checks application approval before and after native execution. `packages/backend/test/mcp-journey.test.mjs` exercises real native connect through the Python broker against a synthetic authenticated server. Upstream MIT, commit `4b6fea2875e4f2e3e8a8fee181803e54f7056845`, published 2.0.26; no new patch added by S1b-C. | Upstream supplies equivalent connection-scoped transport/auth factory plus before/after tool approval hooks, with native token persistence disabled and the connected journey passing without these transformations. |
