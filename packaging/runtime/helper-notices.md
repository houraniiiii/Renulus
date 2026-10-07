# Selected CPU helper provenance

Development acquisition and CPU verification: October 4, 2026.
The exact public acquisition register is [helper-assets.json](helper-assets.json).
Each record contains immutable source URLs, revisions, sizes and SHA-256 hashes.
The runtime requires the identical manifest at the explicit profile's
`helpers/manifest.json` and validates the necessary model/tokenizer files.
Model binaries remain ignored development assets.

| Component | Attribution and source | Observed terms | Preserved material |
| --- | --- | --- | --- |
| BGE small English v1.5 | BAAI; quantized ONNX port by Qdrant, revision aa8f8b060edb00e03bfdd08813a2949946c8ba55 | MIT in the pinned Qdrant model card | Original README.md, tokenizer metadata and source URLs |
| Heron layout | Docling project, revision 8f39ad3c0b4c58e9c2d2c84a38465abf757272d8 | Apache-2.0 in the pinned model card | Original README.md and configuration |
| TableFormer accurate | Docling project, docling-models v2.3.0 resolved to fc0f2d45e2218ea24bce5045f58a389aed16dc23 | CDLA-Permissive-2.0 in the pinned model card | Original README.md and tm_config.json |
| RapidOCR English detection/recognition/classification | RapidOCR/PaddleOCR, official v3.9.2 Modelscope URLs; filenames/hashes from installed RapidOCR 3.9.2 registry | Artifact distribution notices require the upstream OCR model terms as well as the RapidOCR code notice | Exact source URLs, shipped hashes and original registry filenames in the manifest |
| ANTLR Python runtime 4.9.3 | ANTLR Project, official PyPI sdist | BSD 3-clause identified by the source headers | Wheel contains original headers; source and wheel hashes in windows-cp314-wheels.json |

Package and model terms remain their upstream terms; Renulus's MIT licence does
not relicense them. Before distributing a native bundle, the installer owner
must include the complete package/model licence texts, copyright and notices,
including OCR artifact-specific terms. This development inventory does not claim
the release notice set or clean-machine installer is complete.

ANTLR 4.9.3 has no official wheel. Build its pure Python `py3-none-any` wheel once
in the developer packaging environment and bundle that reviewed wheel. Source
SHA-256: f224469b4168294902bb1efa80a8bf7855f24c99aef99cbefc1bcd3cce77881b.
Verified developer wheel SHA-256:
d234a2e0a26cf1f0a1ae5b727d8c71c1c3305ef183f962f729a0b4b915bd20e7.
Doctors do not build it. Wheel build timestamps may change a rebuilt wheel's hash;
record the actual wheel shipped rather than assuming byte reproducibility.
