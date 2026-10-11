# H03 counter-evidence readiness — October 11, 2026

Published baseline: `97c432aafc56907f6287c1a63263f644085a8884`. Source-only research; no execution, provider calls or acquisition. Repository references below are relative to `C:/Users/karol/.codex/worktrees/oc-memory/repo` at that commit.

**Conclusion:** no production generative tokenizer/accounting artifact or route-to-counter registration was identified behind ProviderManager/DeploymentEvidence in the bounded adopted inventory. Unknown accounting must continue to deny migrated dispatch. Approved models remain Sol/Astra/Luna and MiMo/DeepSeek ([DS]:77–79), with the exact IDs in [P]:10–12; no tokenizer mapping follows from their names.

The adopted local artifact is BGE-small's **WordPiece** tokenizer, SHA256 [BT], acquired from `Qdrant/bge-small-en-v1.5-onnx-Q` revision `aa8f8b060edb00e03bfdd08813a2949946c8ba55`. [BM] lines42–60 pin it; [BH] lines77–90 bind it to 512-token embeddings, not generative routes. Its pinned model card [BR] line2 declares MIT. Installed `tokenizers==0.23.2` metadata [TM] lines2–8 declares Apache licensing; this is library metadata, not a qualified model tokenizer. Actual helper manifest equals [BM].

Hermes [HE] lines2383–2400/2615–2627 supplies rough text/request estimates; its licence [HL] is MIT. Pinned OpenCode [OT] lines3–5 divides characters by four; [OC] lines925–962 applies estimates to system/history/tools and flat media costs. [OL] is MIT. The declared cohort source is `4b6fea2875e4f2e3e8a8fee181803e54f7056845` ([HC]:21). These estimators are not production inclusive counters or proven upper bounds for the approved routes.

[D]:374/389–402 already defines `InputCounter(bytes, NativeManifest) -> Awaitable[int|None]`: verified tokenizer **and** protocol/system/history/tool/image rules; character estimates and tokenizing JSON/base64 as prompt text are excluded. [N]:65–134 captures admitted input identity, including media SHA/length/MIME/detail; it establishes no count. `counter_revision` is a trusted injected label, not an artifact verifier ([D]:496–498).

Normal assembly has no hidden registration: [M]:395–406 returns protected route identity only; [S]:330–336 calls [G]:135–169 without its optional registry factory; [B]:49–51/156–159 preserves that injection. [R]:192–208 already accepts the immutable evidence lookup. No DeploymentEvidence constructor was found in runtime production code.

The smallest prerequisites are:

1. Adopt a licensed, hash-pinned artifact and accounting-rules revision qualified for each exact route/model/protocol; prove complete final-body/manifest accounting, including image preprocessing/detail, or a safe inclusive upper bound. Bind it through the existing evidence lookup/registry factory, retaining actual counter finalizers. No second authority or new counter port is needed.
2. Separately supply current account/deployment input, output, combined-window and capability evidence bound to protected credential revision. Catalogue membership, successful answers and synthetic counters cannot establish these externally specific limits.

Technical enforcement exists: [D]:483–504/578–598 checks identity, missing evidence/count, final manifest/body, output/input/window and currentness after awaited counting. Existing synthetic tests [T]:123–168/517–525 cover unknown/invalid counts and capacity denial. They establish enforcement, not tokenizer accuracy, account entitlement or H03 acceptance.

Local primary-source fingerprints (SHA256; line references above):

| ID | File | SHA256 |
| --- | --- | --- |
| DS | `docs/DECISIONS.md` | `3f7bb06c2d76a6e161f233f544791da7b3255dfdcc2445e0979255254c2c770b` |
| P | `runtime/renulus/runtime/policy.py` | `e2c85ad79a5dc2f397cf9621ef240654a4e107c16fd396fc0767c52dc8210854` |
| D | `runtime/renulus/runtime/harness_deployment.py` | `0ec5fa315a9e8d052e2871c6f22e848aac6d6f7bf650a19fe57e9ca99cc6486a` |
| N | `packages/harness/src/native-manifest.ts` | `1f214bafffcab3ea45fdfb3bf893c8720d96da2b18aa2c0cd6959b3dc51e9b54` |
| M | `runtime/renulus/runtime/manager.py` | `1880ad1f7dcd649730ca59939d8d1532a3b6492d71dc0ea2adbe6dfb65857ca4` |
| S | `runtime/renulus/server.py` | `e9834cfc7734b2d68ae9f525e67cb6287a9ca2f47acb832d77bd66117147c366` |
| G | `runtime/renulus/runtime/harness_startup.py` | `4ff321f6d769dcdf70a23b1e732371336c72d795c0f07d8a5c65896770b4d36a` |
| B | `runtime/renulus/runtime/harness_bootstrap_runtime.py` | `9dab8816ff600a74bab4900de1a34e5b6369c413ff9c4f7f7b95b4bf90b4a498` |
| R | `runtime/renulus/runtime/harness_model_registry.py` | `e48e5714f72fd4b9f0f30c035d3e9ddab8c17aa82a9079ea28b97ef96fa23ff8` |
| T | `tests/runtime/test_harness_deployment.py` | `19106cf0da6365f793ca3f091f42ce40298a9a3b0a02bc45dd140787abc9104f` |
| HC | `runtime/renulus/harness_contracts.py` | `b464ab7833d04914944d6ac817e6a364bd52da99a93c0926d56258adc31d62ec` |
| BM | `packaging/runtime/helper-assets.json` | `3d8ba8f76428f2c7fc0348167dd9b8c70e2f47f29dbd6705e01a6c0fdea97fce` |
| BH | `runtime/renulus/runtime/helpers.py` | `4fbb1ee6685798fbc1ee286fb118e36df66e4dc4a67184aa0a8f265c37f3f53c` |
| HE | `upstream/hermes/agent/model_metadata.py` | `051d4dde2d4e92aa6f96411df37b7ee25b9308f881be5bbaa4810cd02fd532e0` |
| HL | `upstream/hermes/LICENSE` | `821556e6336796450ab852d375117b48a4887e71d255794fd6318d99982a5ab6` |
| BT | `C:/Renulus/dev/helper-assets/fastembed/bge-small-en-v1.5/tokenizer.json` | `d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66` |
| BR | `C:/Renulus/dev/helper-assets/fastembed/bge-small-en-v1.5/README.md` | `01e220eed6921254f7e086bb3506d1c03f019f5f747bb9ac2f6ec5ce541edc12` |
| TM | `C:/Renulus/dev/python/Lib/site-packages/tokenizers-0.23.2.dist-info/METADATA` | `0485b3a1a959fa9fd8c50c92eefdf25edf1c6868affe71f7f3475d14c2894307` |
| OT | `C:/Renulus/scratch/ocf/src/packages/core/src/util/token.ts` | `a0b394f41ee02130da05e82d468aa705b684bff33287ebf1191a3e695bfef12c` |
| OC | `C:/Renulus/scratch/ocf/src/packages/core/src/session/compaction.ts` | `e386ce7bbe0ce2008c3bb1c1ed7c517b45cf93d475c5f26549601b550c15189a` |
| OL | `C:/Renulus/scratch/ocf/src/LICENSE` | `625f0f619133f89bbbb2abe37369613dfa1885eba1e50d02170deb62bb42cb6b` |
