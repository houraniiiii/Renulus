# Third-party notices

Recorded: **2026-10-04**. Renulus preserves selected development tooling as
unchanged vendor resources. Their licences govern those resources separately
from any Renulus-authored work. The owner has selected MIT for Renulus's own code
and CC BY 4.0 for original teaching content. Scoped licence files will accompany
source/content adoption; those choices do not relicense vendor resources.

## Hermes — planned adoption

- Upstream: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).
- Research revision: `af90026aa09949579bd423d24def3d38f743cde0`.
- [Licence at that revision](https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/LICENSE):
  MIT, copyright (c) 2025 Nous Research.
- Status: selected fork foundation; application source has not been imported.
  Retain the full upstream licence, identify downstream changes and record the
  actual imported revision during S0. Its transitive dependencies retain their
  own terms; the top-level MIT licence does not cover every bundled asset.

See the [adoption evidence](docs/research/2026-10-planning/hermes-adoption.md).
Supermemory remains excluded; other unselected candidates are preserved as
research. Planning selection does not mean a package is installed/distributed.

## Knowledge and memory stack — selected for planned adoption

The user approved this starting stack on 2026-10-04. No application package,
helper-model artifact or engine source has been installed/imported by this
planning update. The following are the top-level code terms recorded in research:

| Component | Planned use | Recorded code licence |
| --- | --- | --- |
| Mem0 OSS | Learner-memory processing through Hermes | Apache-2.0 |
| Docling / Docling-core HybridChunker | Structured extraction, OCR integration and chunking | MIT |
| FastEmbed | CPU embeddings | Apache-2.0 |
| LanceDB OSS | Embedded document full-text/vector retrieval | Apache-2.0 |
| Qdrant Python client local mode | Initial derived Mem0 memory index | Apache-2.0 |

The [stack evidence](docs/research/2026-10-04-starting-stack-evidence.md) links
the inspected engine/licence sources. On adoption retain complete applicable
licences/notices, identify patches and record the actual compatible versions.
Inventory the native dependencies and model/tokenizer/language artifacts that
are actually shipped, with hashes and their independent terms. Top-level code
licences do not cover every helper weight or binary. No final embedding or OCR
artifact is selected by this table, and it is not a distribution clearance.

## Impeccable

- Upstream: [pbakaus/impeccable](https://github.com/pbakaus/impeccable).
- Author: Paul Bakaus.
- Preserved source revision: `e103efe779e2dd01274dabae83531fef00bf2563`.
- Skill version: **4.5.0**. Original installer version: **4.1.0**.
  Preserved local Windows x64 engine: **0.1.11**.
- Licence: Apache License 2.0, retained in the
  [Codex bundle](.agents/skills/impeccable/LICENSE) and
  [Claude bundle](.claude/skills/impeccable/LICENSE).
- Original third-party notices remain in the
  [Codex NOTICE](.agents/skills/impeccable/NOTICE.md) and
  [Claude NOTICE](.claude/skills/impeccable/NOTICE.md).

Those NOTICE files attribute the iOS and Android platform guidance to
[ehmo/platform-design-skills](https://github.com/ehmo/platform-design-skills),
whose original licence is MIT. The notices and platform reference files remain
unchanged. The upstream copyright and complete MIT permission notice are retained
in [the supplemental platform licence](licenses/ehmo-platform-design-skills-MIT.txt),
covering both editions. It was retrieved on 2026-10-04 from
[`ehmo/platform-design-skills` revision `dc2be825d8b439caea78e9eaa8fb3ac23b0ff3e9`](https://github.com/ehmo/platform-design-skills/blob/dc2be825d8b439caea78e9eaa8fb3ac23b0ff3e9/LICENSE).
Impeccable's shipped browser helpers, screenshot helper and font
catalogue metadata were preserved with the bundle. No external font binaries
were acquired by this work.

The two copied Windows engine executables are local ignored caches. Their
SHA-256 is `605b5b442d2a65d270ef989de13371444849526249f511d397ca7424c184db49`.
Copying those caches is distinct from publishing or installing a new release.

## Interface Design

- Upstream: [Dammyjay93/interface-design](https://github.com/Dammyjay93/interface-design).
- Preserved source revision: `2f9be3206855bcb2d1d0af262c8bae25cba6658d`.
- Licence: MIT, copyright (c) 2026 Damola Akinleye.
- The complete licence remains in the
  [Codex core](.agents/skills/interface-design/LICENSE),
  [Claude core](.claude/skills/interface-design/LICENSE),
  [Codex review workflow](.agents/skills/interface-design-review/LICENSE) and
  [Codex deslop workflow](.agents/skills/interface-design-deslop/LICENSE).

The Claude review/deslop commands and Codex companion skills preserve the same
upstream workflow bodies with harness-specific frontmatter. Templates, example
systems and vendor example source paths are reference resources.

## Figma declarations

The fresh project configuration names the public official Figma plugin IDs
`figma@openai-curated-remote` and `figma@claude-plugins-official`, the public Codex
connector `connector_68df038e0ba48191908c8434991bbac2`, and the official Claude
marketplace `anthropics/claude-plugins-official`. No Figma package, account
credentials, OAuth state or account-specific configuration was copied into
Renulus by this work. These declarations are not a licence to redistribute
Figma content or evidence of a connected account.
