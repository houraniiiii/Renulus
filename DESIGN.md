# Renulus design

## Authority and implementation status

Design C is the selected replacement as of October 10, 2026. Follow the
[C implementation spec](docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md) for the
screen map, later user decisions, interactions and acceptance. DC01 reconciles
the editable Figma references before implementation uses them as visual targets.

The app currently implements Flow, selected on October 4. The foundations below
describe its existing code and reusable visual language. Its layout and retention
behaviour are baseline evidence, not requirements to preserve where C supersedes
them. Update this implementation record from actual C components as they land;
do not document a prototype as a shipped capability.

## Character

Renulus is calm, precise and approachable. Nephrology learning, clinical
reasoning, source passages and ESENeph revision supply the product context.
Keep the C — Renal flow mark, warm reading surfaces and restrained petrol teal.
The selected C direction prioritises the conversation and the material being read.
Prototype names, suggestions, progress and results must become real-data states.

## Colors

Implemented semantic tokens live in [tokens.css](apps/desktop/src/ui/tokens.css).
Reuse their meanings while reconciling C; coordinate shared changes through
the integration owner.

| Role | Existing value |
| --- | --- |
| Paper / surface / rail | `#faf9f6` / `#ffffff` / `#eff2ec` |
| Renal teal / hover / soft | `#17675f` / `#11564f` / `#e9f1ed` |
| Primary / strong ink | `#243b34` / `#18392f` |
| Secondary / muted ink | `#50635c` / `#53655b` |
| Divider | `#dce3db` |

Warning and error colours retain independent semantic meanings. Use borders
for quiet separation and shadows for overlays. Teal identifies active navigation,
primary actions, focus and source/action links.

## Typography

Source Sans 3 is bundled locally. The implemented baseline uses body 16px/1.5,
metadata 13px, controls 15px/600, section titles 21px/600 and page titles
34px/600 with -0.028em tracking. Reading measure is at most 72ch. Establish
hierarchy through size, weight and colour; verify C against its real content
and zoomed layouts rather than copying a fixed screenshot width.

## Spacing and shape

The existing 4px base supplies 8, 12, 16, 24, 32 and 40px spacing. Panel radius
is 12px and compact controls 7px. Navigation and primary controls have 44px
minimum targets. Inputs sit within quiet surfaces.

## Components

Reuse the primitives exported by [ui/index.tsx](apps/desktop/src/ui/index.tsx)
and their [styles](apps/desktop/src/ui/styles.css). Prefer native buttons,
inputs, selects and dialogs. Shared token/component changes have one owner.
Loading states preserve composition; empty states offer a real next action;
errors retain work and provide recovery. Connect components to canonical state
and real operations before treating a screen as complete.

## Layout and responsive behaviour

Flow's implemented baseline has a 212px left rail, an open learning area and
quiet continuation content. Its narrow layout expands navigation inline and
stacks columns. These describe the existing shell.

The C target has global destinations and projects/chats on the left, a central
conversation or destination, and an optional adjustable workspace on the right.
DC01/DC03/DC07 define and verify its dimensions, collapsed states, pane-aware
layouts and resize behaviour. The spec distinguishes observed Figma dimensions
from proposed implementation defaults; neither the old rail width nor the
prototype's 360px workspace is a fixed C requirement.

## Accessibility and state

The existing focus outline is 2px teal with a 3px offset; reduced motion removes
movement. Flow currently uses Ctrl+K for destination search, Alt+1–8 for routes
and Escape for the destination dialog. C must provide coherent keyboard and
focus behaviour across navigation, chat, readers and assessment, with the
spec's narrow-window, zoom and high-contrast checks.

Conversation scope must be clear. Saved-by-default behaviour and optional
temporary mode follow the C spec; payloads do not belong in URL/history.
