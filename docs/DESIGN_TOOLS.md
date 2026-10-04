# Renulus design tools

Recorded: **2026-10-04**. The audited file-based tooling has been preserved in
Renulus for later interface work. This cleanup creates no product context,
design system, UI or application architecture.

## Installed files and source pins

| Package | Pinned identity | Local files |
| --- | --- | --- |
| Impeccable | Skill **4.5.0**; source `e103efe779e2dd01274dabae83531fef00bf2563`; original npm installer **4.1.0**; Windows x64 engine **0.1.11** | [Codex edition](../.agents/skills/impeccable/SKILL.md), [Claude edition](../.claude/skills/impeccable/SKILL.md), their references, launchers, browser helpers, font catalogues and four agent definitions per harness |
| Interface Design | Source `2f9be3206855bcb2d1d0af262c8bae25cba6658d` | [Codex edition](../.agents/skills/interface-design/SKILL.md), [Claude edition](../.claude/skills/interface-design/SKILL.md), templates, examples, review and deslop workflows |

The copied vendor payload contains **149 files**, including the two existing
Windows executable caches. All copied bytes match the credential-free manifest
checked during the cleanup audit. Vendor contents were left unchanged. Generic
examples such as `src/App.jsx` belong to those resources; they are not Renulus
application code or a selected implementation architecture.

The installation provenance is the audited `nephro-agent-os` copy on this date.
That old workspace is not a runtime dependency. Its project configuration,
local settings, authentication, profiles and native trust state were not copied.
Licence files and source notices remain with both tool editions; see
[third-party notices](../THIRD_PARTY_NOTICES.md).

## Fresh project configuration

- [`.codex/config.toml`](../.codex/config.toml) registers the four bundled
  `impeccable_*` agent TOMLs using `../.agents/skills/impeccable/agents/` paths
  relative to the configuration directory. It also declares the public Figma
  plugin `figma@openai-curated-remote` and public connector
  `connector_68df038e0ba48191908c8434991bbac2`.
- [`.codex/hooks.json`](../.codex/hooks.json) declares Impeccable PostToolUse and
  Stop handlers. The Codex matcher is `Edit|Write|apply_patch`; handlers have
  5-second and 30-second limits. Its Windows command uses the bundled `.cmd`
  launcher; its POSIX command uses the corresponding shell launcher.
- [`.claude/settings.json`](../.claude/settings.json) declares the official
  `anthropics/claude-plugins-official` marketplace and
  `figma@claude-plugins-official`. Its Impeccable SessionStart, PostToolUse and
  Stop definitions use `${CLAUDE_PROJECT_DIR}` and the Claude bundle's launcher.
  These are fresh shared declarations. No `settings.local.json` was copied.

Hook commands, matchers and timeouts follow Impeccable's pinned
[`scripts/lib/transformers/hooks.js`](https://github.com/pbakaus/impeccable/blob/e103efe779e2dd01274dabae83531fef00bf2563/scripts/lib/transformers/hooks.js).
The Codex payload lives in `.agents/skills`, so its hook paths use that directory.
The bundled [hook guidance](../.agents/skills/impeccable/reference/hooks.md)
also documents shared Claude settings as a supported location. Public Figma
identities came from the credential-free installation declarations; account
state and account-specific wiring are excluded.

**Hook trust has not been established for the new Renulus path by this work.**
No hook activation, consent writer, trust bypass or global configuration change
was performed. Codex's local trust is tied to the absolute project path and hook
definition; it must be reviewed locally before relying on automatic execution.
Claude's loading and execution of these declarations also remain unverified in
a fresh native session.

Figma selection flags do not establish installation, authentication, an active
connection or permission to use an account. This work installed no Figma plugin,
performed no OAuth flow and changed no native plugin-access restrictions.

## Discovery and local launchers

| Capability | Codex | Claude |
| --- | --- | --- |
| Impeccable | `$impeccable` | `/impeccable` |
| Interface Design | `$interface-design` | `/interface-design` |
| Interface Design review | `$interface-design-review` | `/design-review` |
| Interface Design deslop | `$interface-design-deslop` | `/design-deslop` |

Codex's skill files are under `.agents/skills/`. Claude's skills, agents and
commands are under `.claude/skills/`, `.claude/agents/` and `.claude/commands/`.
Native discovery of these files has not been exercised in the new root.

Both Impeccable editions contain `scripts/impeccable`,
`scripts/impeccable.cmd`, `scripts/VERSION`, and the existing
`scripts/bin/windows-x64/impeccable.exe`. Each executable is 17,096,584 bytes
with SHA-256 `605b5b442d2a65d270ef989de13371444849526249f511d397ca7424c184db49`.
The Windows launcher can use its adjacent binary. The supplied launchers may
download a pinned platform binary when none is present; no launcher, installer
or download command was run during this preservation work.

## Verification and Git boundaries

File verification covers copied hashes, literal local documentation links,
configuration syntax, registered agent paths, licence/notice presence and
launcher/binary presence. It establishes file integrity and valid declarations.
It does not establish native hook execution, browser/image access, visual
quality, application functionality or educational/clinical performance.

The preservation checks passed for **149 vendor hashes**, **224 literal local
links**, all **four Codex agent paths**, and the fresh TOML/JSON declarations.
Both launcher pairs and pinned Windows executables are present. No executable
or native provider was launched to obtain these results.

Keep both `scripts/bin/` directories as ignored local caches. The supplied
vendor `.gitignore` files already exclude them; root policy should also cover
`.claude/settings.local.json` and credentials/native runtime state. Global
Codex/Claude homes and T3 native state belong outside the repository.

When staging for use on Unix hosts, preserve executable mode on both
`scripts/impeccable` shell launchers. This work made no Git index changes.

Root `PRODUCT.md`, `DESIGN.md`, `.interface-design/system.md` and `.impeccable/`
were not created. Future interface work remains governed by the
[Renulus brief](PROJECT_BRIEF.md) and the user's scope for that work.
