# Renulus design

## Authority and implementation status

Design C is the selected replacement as of October 10, 2026. Follow the
[C implementation spec](docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md) for the
screen map, later user decisions, interactions and acceptance. DC01 reconciles
the editable Figma references before implementation uses them as visual targets.

The canonical source implements the Design C shell and connected modules. The
owner's October 19/20 MVP instruction authorized local shortcut cutover; the
ordinary launcher now selects the Design C source app with OpenCode v2 saved
learning chat. The previous packaged Flow app remains at `C:/Renulus/app` for
recovery. See the [MVP delivery record](docs/implementation/MVP_20261019.md) for
the current source delivery, verification and limits. This bounded current-PC
cutover does not pass full H20 or matching packaged Windows acceptance. Earlier
DC20/DC21 deferral text records the pre-MVP checkpoint.

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

The source C shell has global destinations and projects/chats on the left, a
central conversation or destination and an optional adjustable Workspace on the
right. Its expanded rail is 272px and the Workspace starts at 480px. At narrow
widths the selected Workspace becomes the focused pane with a Back to chat
action; the rail collapses and retains search/navigation controls. The separator
supports keyboard resizing. Safe tab references, reader locations and width are
stored through canonical Workspace preferences; source text and transient Study
receipts are not layout preferences.

## Accessibility and state

The focus outline is 2px teal with a 3px offset; reduced motion removes movement.
C uses the shared destination search and keyboard/focus primitives across
navigation, chat, readers and assessment. Hidden source checks cover narrow
windows, 200% zoom and keyboard reachability at their documented scope. Physical
Windows accessibility and the complete matching installed matrix remain separate
acceptance gates.

Conversation scope must be clear. Saved-by-default behaviour and optional
temporary mode follow the C spec; payloads do not belong in URL/history.
