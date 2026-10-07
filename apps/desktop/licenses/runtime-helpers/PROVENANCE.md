# Bundled public CPU helper notices

Initial capture October 4, 2026; ANTLR notice supplemented October 6, 2026.
These texts supplement the pinned original model cards,
configs, source URLs and hashes in backend/packaging/runtime/helper-assets.json.
They do not change the helper inventory: 19 files, 483,597,181 bytes.

| Material | Observed terms and preserved notice | Text source | SHA256 |
| --- | --- | --- | --- |
| BAAI BGE small English v1.5 / Qdrant ONNX port | MIT in the pinned Qdrant card; the upstream FlagEmbedding notice is preserved verbatim, including its copyright | FlagOpen/FlagEmbedding LICENSE at fd1a2bdf69488ffebe0327999d4400d8c8058a0b (blob 360931513aa6c02f933a403202afa99ac2c5bc88) | 587a673933425dbc36ec61268d3b954051b2d3ef3c9b322ede357976055ffdd5 |
| Docling Heron layout | Apache-2.0 in model card at 8f39ad3c0b4c58e9c2d2c84a38465abf757272d8; original card remains with the assets | https://www.apache.org/licenses/LICENSE-2.0.txt | cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30 |
| Docling TableFormer accurate | CDLA-Permissive-2.0 in model card at fc0f2d45e2218ea24bce5045f58a389aed16dc23; original card remains with the assets | SPDX license-list-data 31ba1a50e5397e00a304dbadc76531740e89ee48 details/CDLA-Permissive-2.0.json, licenseText; official agreement https://cdla.dev/permissive-2-0 | 4531a67d443284d93ffed0803df5b10634aff21c3d77e381f2d48af01d875868 |
| RapidOCR OCR distribution | ModelScope RapidAI/RapidOCR public metadata reports Apache License 2.0; exact asset URLs remain pinned to v3.9.2. Original RapidOCR notice retained | RapidAI/RapidOCR LICENSE at v3.9.2 (blob ab68e50ab2d0af41c9c8c30947a694a6285cde3f) | 3e0af25fdd06aa9586ae97adb00ea927ebe5a3805ac77d2d3a81ce5f55693333 |
| PaddleOCR detection/recognition/classification origin | Original upstream copyright/Apache-2.0 notice retained alongside the RapidOCR redistribution notice | PaddlePaddle/PaddleOCR LICENSE at dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf | 3840c5c0c61c294264d2dd77b8777be6ddd90121ef4e0e64abcd22edea581d6e |
| ANTLR Python runtime 4.9.3 | Complete original project text: BSD 3-clause, copyright 2012–2017 The ANTLR Project, plus upstream MIT notices for JavaScript helpers; preserved verbatim as ANTLR4-BSD-3-Clause.txt | https://raw.githubusercontent.com/antlr/antlr4/4.9.3/LICENSE.txt | b1b379fcaf3219593a4c433feb1b35c780bed23fafaae440b1ae2771a9521e3a |

Model cards and immutable revisions were checked through the public HuggingFace
model repository API. OCR licence metadata came from
https://modelscope.cn/api/v1/models/RapidAI/RapidOCR. The three pinned OCR assets
are PP-OCRv6 det_small/rec_small and PP-OCRv4 mobile classification.
No model inference or account was used for this notice acquisition.

The CPython archive retains its LICENSE.txt. Dependency wheels retain their
dist-info licences, metadata and source notices, including the ANTLR source
headers. Electron retains its LICENSE and LICENSES.chromium.html. Hermes's
original MIT licence and Renulus's original teaching-content CC BY 4.0 licence
remain in their bundled source locations. Renulus MIT does not relicense them.

ANTLR 4.9.3 supplementary notice was acquired by one read-only public download
of the exact tag-pinned URL above on October 6, 2026, HTTP 200. The complete
2,699-byte response was written directly to `ANTLR4-BSD-3-Clause.txt`, without
decoding/reformatting or trimming. Its SHA256 is
`b1b379fcaf3219593a4c433feb1b35c780bed23fafaae440b1ae2771a9521e3a`.
The full upstream file also retains Mathias Bynens MIT notices for
`codepointat.js` and `fromcodepoint.js`. No other source/model/package
acquisition or runtime execution accompanied this notice addition.

The accepted installer/source freeze
`699938f20efb6bbc2cf8df684cc5c6c3450e6eaf` predates this supplementary source
notice. Parent owns copying, hashing, validating and supplying it as a
documented public companion beside that unchanged installer. Actual companion
delivery is recorded separately; this source addition does not change or
relabel the frozen installed artifact. Existing desktop `licenses/**` and
licence-directory resource mappings include this file on future manufacture.
