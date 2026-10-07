# Renulus — Flow

The user selected Flow on October 4, 2026. This records its existing visual
authority, ported from the UX exploration; it does not introduce another world.

Flow begins with one question in an open learning area, served by a stable
212px left rail and a quiet continuation area. The renderer uses Source Sans 3
bundled locally, the unchanged C — Renal flow mark, and restrained petrol teal.
The shell removes prototype switches, invented progress and synthetic results.

The domain is nephrology learning: filtration, renal flow, source passages,
clinical reasoning, teaching, revision and the ESENeph track. The colour world
is warm reading paper, white clinical surfaces, pale sage wayfinding, petrol
teal instruments and dark green ink. Flow's signature appears in the renal
mark, active destination, primary action, focused input and source/action links.
The selected layout leads with a question rather than a grid of dashboard metrics.

Tokens are in apps/desktop/src/ui/tokens.css. Paper #faf9f6; surface #ffffff;
rail #eff2ec; renal teal #17675f; hover #11564f; soft teal #e9f1ed; primary ink
#243b34; strong ink #18392f; secondary #50635c; muted #53655b; line #dce3db.
Warning and error colours have independent semantic meanings. Use borders for
quiet separation; shadows only for overlays. A 4px spacing base governs 8, 12,
16, 24, 32 and 40px rhythm. Inputs are inset into a quiet surface.

Typography: body 16px/1.5, metadata 13px, controls 15px/600, section titles
21px/600, page titles 34px/600 with -0.028em tracking. Reading measure is at most
72ch. Navigation and primary controls have 44px minimum targets. Panel radius
is 12px; compact controls 7px. Text hierarchy uses size, weight and colour.

Reusable primitives are exported by src/ui/index.ts. Use native buttons,
inputs, selects and dialogs. Focus has a 2px teal outline with 3px offset;
reduced motion removes movement. Loading skeletons preserve composition;
empty states explain a real next action; errors retain work and offer recovery.

At narrower widths the rail becomes an inline expandable navigation region,
columns stack and controls wrap. Keyboard navigation uses Ctrl+K to find a
destination, Alt+1–8 for routes, Escape for the destination dialog. Temporary
case scope remains visible during handoffs; no payload enters URL/history.
