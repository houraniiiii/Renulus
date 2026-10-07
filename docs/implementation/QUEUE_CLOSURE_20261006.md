# Accepted vertical slices — October 6, 2026

The parent reconciled existing implementation and receipt evidence while the
c7b3b5de matching manufacture continued. No test, import, conversion, provider
request or source-original read was repeated for these tracker closures.

| Issue | Accepted boundary | Retained evidence and limits |
| --- | --- | --- |
| #14 source selection and CC BY admission | Default selection, exact hash-bound reviews, operation-specific permissions/component holds and supported admission | Selection integration 716045f1; 70 affected policy checks; 15 actual review bindings; 29 E07/L03 admissions. The existing 28-entry E06 receipt has every queued original and exact rights/attribution verified. Queued is distinct from searchable; currentness/component/EMF holds remain. |
| #15 Office imports | Real pinned Docling/HybridChunker PPTX/DOCX/XLSX conversion, original/locator API recovery and installed format UI | Integration 909d2968 and shared archive allowlist fix; exact previously failed three-format recovery passed once with controlled vectors; native 035ca7bd Office UI/ingestion/citation/original gates individually passed. Whole native05 remains failed. Unsupported vector/active-object containers remain refused. |
| #16 direct-import priority | Bounded durable hint, single-worker ordering, fairness, restart/stale/replay safety | Integration 6bac014b; 19 focused checks plus three overlapping affected checks; parent separately recorded 20 integrated queue/worker checks. These use real API/SQLite/worker with controlled conversion adapters, and do not establish parser performance or final installed acceptance. |

Detailed closure evidence is recorded on each live GitHub issue. Supporting
reports are [selection](source-selection-review.md),
[collection guards](collection-coverage.md),
[classified admission](classified-file-adoption.md),
[publisher scope](e06-publisher-scope-review.md),
[E06 plan](finalise-source-adoption.md), [Office](office-supplements.md),
[Office UI](library-office-ui.md) and [priority](interactive-imports.md).

The parent reread `.local/e06-source-adoption-queued.json`, SHA256
`ad70440b748fad63d6db27b9c9b00980a251658f683ec0c53fdeff1685857384`.
All 28 entries are queued, `owned_original_verified=true` and
`rights_and_attribution_exact=true`. Actual admission ran October 5,
10:34:39–10:34:53 UTC at source 7a11da65 without lifespan, worker, engines,
external network or credential inspection. Existing admissions are not repeated.

Image-original issue #17 remains open for the parent’s current installed
deletion/recovery reconciliation. Its accepted prior actual CPU proof is
preserved separately: source 55d553d1, 102.085 seconds; actual Docling/RapidOCR,
zero passages/genuine document export, exact 1,878-byte original, empty retrieval
without embeddings and supported original deletion/refusal. Receipt SHA256
`8ebf27fae21f2bde9cbee2a49f9f89a1aabe3d4a0f5cd8011052498e3b7bfa6a`.
Native05 also individually verified its distinct 781-byte no-text PNG. Neither
is relabelled as a whole current native or live acceptance pass.

Final matching installed lifecycle, connected learning, selected-subscription
generation/capture and installation maintenance remain in #12/#18 and the
64-row [requirement audit](finalise-audit.md). The product freeze remains
c7b3b5dea9258845273a8df95ca24f5da5bf1ca5; this record changes no product code.
