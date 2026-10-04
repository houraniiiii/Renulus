# Evidence for the approved Renulus starting stack

2026-10-04 · Decision follow-up to the completed public-source research round.
This record preserves the link between the user's approval, inspected evidence
and work still required. It is not a second implementation plan. No new source
investigation, installation, model download or runtime test was performed when
recording the approval.

## Decision and scope

After reviewing the research, the user accepted the strongest starting stack
and requested planning updates with the evidence retained in research:

**Hermes + Mem0 OSS + Docling/Docling-core HybridChunker + FastEmbed + LanceDB
OSS.** Reuse Hermes's memory/context interfaces and compressor. Canonical source
and learner records stay in SQLite. Mem0 initially uses its existing local
Qdrant client for a derived memory index; LanceDB serves the document library.
Local Qdrant is the initial integration configuration, not a request to run
a Qdrant server.

The [user answer record](../planning/2026-10-04-user-answers.md),
[confirmed decisions](../DECISIONS.md), [architecture](../planning/ARCHITECTURE.md)
and [implementation stages](../planning/IMPLEMENTATION_PLAN.md) govern selection
and delivery. Exact package/model/artifact pins and working integrations are
not established. This request authorises documentation, not app implementation.

## Preserved research

| Investigation | Evidence retained |
| --- | --- |
| [Framework recommendation](2026-10-04-context-framework-recommendation.md) | Stack rationale, capability mapping, reuse comparison and alternatives |
| [Memory engines](2026-10-04-memory-engines.md) | Real engine versus hosted client, licences/defaults, Hermes seams, capture/deletion gaps and alternative engines |
| [Document ingestion](2026-10-04-document-ingestion.md) | Extraction/chunking/provenance, tagged source, OCR/model terms, Windows-wheel inspection and Docling/LiteParse comparison |
| [RAG and context](2026-10-04-rag-and-context.md) | Hermes contracts, embedded search, CPU embeddings, framework integration limits and package artifacts |
| [Comparable projects and public signals](2026-10-04-comparable-projects-and-signals.md) | Source donors, module coupling, deployment/licence boundaries, Trending observations and labelled public-discussion anecdotes |

Original findings, observed release dates, source revisions, discussion links
and uncertainty statements remain in those notes. Source review and static
package inspection do not establish runtime reliability, clinical accuracy or
educational effectiveness. Dated decision follow-ups identify the later approval
without rewriting that evidence as a successful test.

## Primary evidence behind the selection

These references were already inspected during the research round. Immutable
revisions/tags are evidence snapshots, not a compatible dependency lock.
Documentation/model pages can change; check the exact artifacts on adoption.

| Component | Primary evidence | Reason to adopt |
| --- | --- | --- |
| Hermes | [Memory-provider contract](https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/memory_provider.py), [context-engine contract](https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/website/docs/developer-guide/context-engine-plugin.md), [Mem0 OSS integration](https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/plugins/memory/mem0/README.md) | Existing runtime/context machinery and in-process integration; avoids another agent loop |
| Mem0 OSS | [Memory engine](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/memory/main.py), [Apache-2.0 licence](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/LICENSE), [local Qdrant adapter](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/vector_stores/qdrant.py) | Actual extraction/update/recall engine with embedded storage, distinct from hosted MemoryClient |
| Docling | [Tagged engine](https://github.com/docling-project/docling/tree/v2.133.0), [pipeline configuration](https://github.com/docling-project/docling/blob/v2.133.0/docling/datamodel/pipeline_options.py), [standard PDF pipeline](https://github.com/docling-project/docling/blob/v2.133.0/docling/pipeline/standard_pdf_pipeline.py) | Structured conversion, layout/table processing and OCR adapters with CPU configuration |
| Docling-core HybridChunker | [Pinned chunker](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/chunker/hybrid_chunker.py), [document representation](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/types/doc/document.py) | Token-aware structured chunks, headings and source-item provenance; reduces custom assembly |
| FastEmbed | [Open engine](https://github.com/qdrant/fastembed), [model catalogue](https://qdrant.github.io/fastembed/examples/Supported_Models/), [Mem0 adapter](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/embeddings/fastembed.py) | ONNX CPU embeddings without a model server; explicit model/cache configuration still needed |
| LanceDB OSS | [Pinned engine/licence snapshot](https://github.com/lancedb/lancedb/tree/7f5933594f42eeeec1ce73a7ce8e0cd0113cbd82), [hybrid search](https://docs.lancedb.com/search/hybrid-search), [native full-text search](https://docs.lancedb.com/search/full-text-search) | Embedded vector/lexical indexes, filters and fusion; takes explicit vectors without a hosted embedder |

Windows release/wheel observations and package-version mismatches are retained
in the ingestion and RAG notes. Those artifacts lower packaging uncertainty;
they do not prove that the resolved set works in the packaged desktop app.

## Known integration obligations carried into planning

| Obligation | Inspected limitation / evidence | Owner and stage |
| --- | --- | --- |
| Approved generation route | Stock provider defaults do not implement the selected subscription/model policy; memory extraction is generative work | F0 transport and M5 adapter; S0/S4 |
| Reliable eligible capture | Hermes's Mem0 plugin can truncate/skip best-effort writes and needs additional scope filtering | F0/M5; durable queue and scope checks in S4 |
| Mem0 removal and reindexing | Engine deletion retains previous text in history; plugin dimension changes can recreate collections | M5/F0; history purge and staged rebuild in S4 |
| Original-document citations | Preserve Docling item-to-page/region references through chunking; OCR/table output needs corpus checks | M2; S2 |
| No-save OCR/cases | [Tesseract CLI source](https://github.com/docling-project/docling/blob/v2.133.0/docling/models/stages/ocr/tesseract_ocr_cli_model.py) writes temporary images | M2/M3/F0; S0/S2 no-persistence checks |
| LanceDB physical cleanup | [Versioned tables](https://docs.lancedb.com/tables/versioning) can retain removed content until cleanup | M2/integration owner; S2/S4 |
| Helper artifacts | Weights/tokenizers/OCR data and native dependencies have separate terms and resource footprints | F0/integration owner; S0 manifests, S2/S4 performance, S6 notices |
| Expected memory scale | [Qdrant local mode](https://github.com/qdrant/qdrant-client/blob/cf747f4b6fa71ba35dfb467931f3fa65f2cdf263/qdrant_client/local/qdrant_local.py) has small-data limits | M5; S4 volume/recovery checks |

Recorded top-level code terms are MIT for Hermes and Docling/Docling-core,
and Apache-2.0 for Mem0, FastEmbed, LanceDB and the Qdrant client. Preserve
upstream notices and review the actual shipped binary/model bundle. This is
a licence-scope record, not blanket clearance. **BGE-small-en-v1.5 remains an
evaluation baseline**, not a selected artifact; its
[model card](https://huggingface.co/BAAI/bge-small-en-v1.5) does not pin converted
weights or tokenizer files.

## Alternatives retained without adding dependencies

Docling is the primary pipeline. LiteParse + reusable chunkers remains a bounded
comparison if the selected path fails a defined resource/extraction target.
Cognee is the broader alternative; Hindsight, Mnemosyne, Xberg and the other
engines remain researched options. AnythingLLM/Kotaemon modules and
LlamaIndex/Haystack primitives may supply an identified narrow gap. None is an
automatically selected extra layer.

Supermemory remains excluded. Its
[self-hosting overview](https://github.com/supermemoryai/supermemory/blob/7cc19fa34683a4fe74166ee5d794d271a21b5a92/apps/docs/self-hosting/overview.mdx)
describes the separate non-public engine. Retain that finding and the
[earlier evaluation](2026-10-planning/supermemory-fit.md) as dated evidence.
