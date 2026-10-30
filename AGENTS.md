# Renulus workspace

Read `README.md`, `docs/PROJECT_BRIEF.md` and `docs/WORKSPACE.md` before substantial
work. Keep edits scoped to the user's current request.

- This is Renulus, the independent open-source nephrology learning project. Its
  only Git remote is `origin`, pointing to `houraniiiii/Renulus`. Keep the original
  clinical MVP and its repositories separate. The user explicitly authorised
  this separation on 2026-10-04; old origin-preservation instructions apply only
  inside the inherited archive, not here.
- The name is Renulus. The selected logo is C — Renal flow. The agreed character
  is modern medical: calm, precise and approachable, with a subtle renal shape.
- Renulus is an English-first Windows-only learning harness for nephrologists
  practising in the EU, with specialisation, active study and staying current at
  its centre. Use existing models; the project owner will not host a service or
  model inference. Use the selected OpenCode Go and/or Codex subscriptions and
  exact model list in docs/DECISIONS.md. The October 20 MVP verified one live
  Codex/Sol text answer; account-specific Go/tool/image acceptance remains
  separately scoped. Do not substitute conversational models or add paid API
  or user-managed local-runtime requirements. Small CPU models bundled and managed by Renulus
  for embeddings/OCR are explicitly accepted; no GPU, Docker, model server or
  setup is required of doctors.
- Support education across nephrology from the outset. The user explicitly
  rejected perfecting acid–base or any one subject first. Build capabilities
  and verify them across varied domains; do not narrow scope around a demo.
  General topics plus an ESENeph track, guidelines plus selected research,
  personal Windows computers, and text/PDF/image inputs are confirmed.
- Product research and planning are now authorised. Record the user's answers in
  `docs/planning/2026-10-04-user-answers.md` and keep proposed implementation
  choices distinct from confirmed decisions. Separate Chat/Explain and Test;
  reviewed-bank assessment and generated practice have different roles. Daily
  practice case discussion is in scope. No implementation is authorised merely
  by a request to research decisions.
- `docs/DECISIONS.md` distinguishes confirmed choices from unresolved work.
  `docs/SOURCES.md` is the single current development source/acquisition register.
  The owner confirms ERA user downloads as an acquisition direction and optional
  user-supplied web/literature retrieval API keys, including explicitly selected
  paid tools. These are not mandatory paid APIs or generative-model fallbacks;
  do not incur provider usage incidentally. Track current final editions,
  corrigenda, chapter replacements, retractions and access-specific user imports.
  References are dated evidence and candidates, not product requirements or
  claims of implemented functionality, educational efficacy or clinical accuracy.
- Design C is the selected UI and the October 19/20 source MVP is selected by
  this PC's ordinary shortcut. The former packaged Flow app remains for recovery;
  full packaged acceptance is not established by this local cutover. For this
  migration, read `docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md`, including the
  relevant ticket, dependencies and shared behaviour rules. Confirmed user
  decisions govern; labelled planning defaults remain adaptable with a recorded
  rationale. Figma supplies visual references, not proof of implemented capability.
- Follow the C spec's delivery waves and `docs/planning/ARCHITECTURE.md` and
  `docs/planning/PARALLEL_WORK.md` for module ownership and worktree boundaries.
  The older Round 3 implementation plan retains foundation guidance but does not
  override later UI or retention decisions. Use `codex/` branches from the shared
  committed baseline. Every feature must deliver a connected working flow.
- OpenCode v2 is the selected harness direction as of 2026-10-10;
  the October 26 target is full integration with TypeScript/Effect and Python,
  retaining the selected data engines. Follow
  `docs/planning/BACKEND_FINALISATION_SPEC.md` for finalisation and its mapping of
  `docs/planning/OPENCODE_V2_INTEGRATION_PLAN.md` and the existing H tickets.
  Specification authority does not itself authorise runtime implementation.
  The later October 19/20 MVP instruction authorizes this PC's source-app
  cutover: saved learning chat now uses OpenCode v2. Read
  `docs/implementation/MVP_20261019.md` for its actual evidence and limits;
  other producers retain their existing implementations. Preserve working
  Hermes adapters and Electron/React components until each connected migration
  replaces them. This bounded delivery does not pass the full H20/package gate.
  Preserve upstream licences and patch provenance. Supermemory was evaluated
  and is now excluded from adoption by the user's later research request;
  replacement engines must themselves be open source.
- The user approved the starting stack on 2026-10-04: Mem0 OSS through Hermes's
  in-process integration, Docling/Docling-core HybridChunker, FastEmbed and
  LanceDB OSS. SQLite owns canonical records; Mem0 initially uses its local
  Qdrant client for a derived memory index. Preserve Hermes context management
  for legacy producers; migrated saved chat uses the OpenCode context seam.
  Pinned versions, helper artifacts and adapters have scoped implementation
  evidence; remaining account, workflow and delivery gates remain separate.
  Alternatives retained in research are not selected extra dependencies.
  Keep the selection and dated evidence linked in the planning files.
- Renulus's own code uses MIT; original teaching content uses CC BY 4.0.
  Third-party and user-owned material retain their own terms. Add scoped licence
  files/notices during source and content adoption before distribution.
- Old code, datasets, dependencies, Git history and reports are retained outside
  the active workspace. Do not automatically restore or scan them. Old archived
  AGENTS files do not govern Renulus. Bring in reviewed reusable material only
  when the user requests work that needs it.
- Preserve originals, credentials and private/native application state. Do not
  read, copy, commit or transport secrets, patient records, private correspondence
  or unclassified datasets without explicit authorisation. Use synthetic data
  for tests. Follow `docs/SOURCES.md` for content-use boundaries.
- Do not train models, call paid providers, alter services or deploy incidentally.
  Check the current branch and working tree before handoffs; publish only within
  the user's authorised scope.
- Use Figma and the installed design skills when relevant to interface work.
  Preserve one coherent design system. The user and assistant lead review;
  use concrete source and behaviour checks rather than repetitive disclaimers
  or an invented external-panel prerequisite.
- Use the app-scoped Renulus Playwright controller for interactive development
  and UI checks while the owner uses this PC. Read
  `docs/implementation/APP_CONTROL.md`. Keep its test windows hidden and use
  its owned synthetic profile/backend. Do not use Computer Use, OS input,
  focus(), bringToFront() or foreground-window helpers for these checks.
  Physical Windows dialogs, installation and external handoffs need their
  separately scoped native acceptance; hidden tests do not prove them.
  If this chat cached an older MCP connection, use
  `tools/renulus-control/client.mjs` with the documented fixed configuration.
  It sends the same MCP requests without desktop input.
