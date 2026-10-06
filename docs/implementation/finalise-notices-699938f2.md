# Targeted distribution notices audit — October 6, 2026

**The matching installation contains the principal Renulus, content, Hermes,
font, renderer, Python and CPU-helper notices. One concrete completeness gap
remains: ANTLR 4.9.3 refers to a BSD 3-clause LICENSE.txt that is absent from its
inventoried package. Supply that original notice as a small distribution
supplement. This audit does not change or reject the tested runnable freeze.**

Assigned worktree: `C:/rn-finalise-20261005/lanes/distribution-notices-20261006`;
branch `codex/distribution-notices-20261006`, starting commit
`dc6676fbb3d9ff96eab49474e5450bdce8e5f002`. Product freeze remains
`699938f20efb6bbc2cf8df684cc5c6c3450e6eaf`. Parent owns native-reader evidence,
integration, audit/tracker updates, repairs and worktree retirement.

Read AGENTS, README, project brief, workspace and decisions; the distribution
requirements in the implementation plan; matching installed acceptance, audit
G7, package-inventory correction, retained packaging report, desktop notices and
helper provenance. S0.01/S0.07/S6.06 require preservation of adopted notices and
source/artifact provenance. This is their bounded static notice check, not a
new licensing programme or complete-product acceptance.

## Target identity and performed method

Delivery root below means `C:/Renulus-native-delivery/desktop-20261005`.
Installed paths in the table are relative to `installed-699938f2`; backend paths
are relative to `installed-699938f2/resources/backend`. Payload metadata came
from `payloads/backend-699938f2`; manufacturing metadata came from
`matching-699938f2/delivery-provenance.json`.

The supplied compact current-target inventory was read and its SHA256 verified.
It records **39,255 backend files and 5,742 frozen-source checks** already
performed by next01 at this exact target. Its installed-identity gate passed;
the originating invocation subsequently failed, exit 1. Those dispositions
remain unchanged. Its backend inventory digest equals the retained payload
inventory digest, and manufacture records the same source and artifact pins:

| Recorded artifact | SHA256 |
| --- | --- |
| Installer | `ce1ed76147585477412a8d5319d485fdb03c5e1f3daae2ed02c2ca6669261f5d` |
| Executable | `37e82a40e5143336ffca364d64e2f58e013411727d7a6455462ec53a31b1a802` |
| ASAR | `02d8037b3e70d3ab3411c2a7f4a905ccf0cc984e1f506b9bfaa996b83e641ff8` |
| Backend inventory | `3b0fc2c9d277ba78cdeef461f53875b8f0fb0d4a6ae1c5cf0e89e1bd476326af` |

No executable, ASAR, installer, model or complete payload rehash was repeated.
The 39,255-entry JSON was read as retained public path/size/hash metadata;
there was no filesystem rescan. Twenty-four exact installed backend licence,
notice and provenance files were individually hashed: **24/24 match** their
retained inventory entries. Fifteen exact installed desktop/installer notice
files were hashed: eleven equal their frozen desktop snapshot copies, and the
four generated installer-tool notices have no counterpart in that source
snapshot. Their actual installed paths/sizes/hashes are retained. The installed
`resources/THIRD_PARTY_NOTICES.md` equals the frozen desktop notice file.

Ten selected Python distribution METADATA files were read for names, versions
and licence fields. Text inspection covered scoped licences, original helper
model cards, provenance, selected licence openings/conditions and the four-line
public ANTLR licence-reference header. Reading/hashing a selected file proves
presence and identity; it is not a review of every dependency or embedded asset.

## What actually reaches the installation

| Material | Installed location and observation | Disposition |
| --- | --- | --- |
| Renulus code | Backend `LICENSE`, 1,292 bytes, complete MIT grant, copyright 2026 Renulus contributors and scope exclusions. Builder metadata also admits desktop LICENSE to ASAR. | Full MIT text directly present in installed backend; ASAR contents were not reopened. |
| Original teaching content | Backend `content/LICENSE`, 1,085 bytes; attribution, CC BY 4.0 and both licence/legalcode URLs. Shipped foundations 1.1.2 manifest records authors, version and explicit attribution/change instruction. | Scoped notice reaches the content. This file is a grant/link notice, not the entire legalcode. |
| Hermes | Backend `upstream/hermes/LICENSE`, 1,070 bytes, complete MIT copyright 2025 Nous Research; duplicate desktop `resources/licenses/hermes-MIT.txt`. Backend `packaging/runtime/hermes-source.json` retains immutable import pin, archive digest, original licence digest and R001–R003 patch provenance. Desktop notice identifies lifecycle imports and subsequent downstream patch. | Licence and attribution/provenance present. No upstream source or patch was executed. |
| Font | `resources/licenses/source-sans-3-OFL.txt`, 4,314 bytes, complete SIL OFL 1.1 and original package notice. Frozen renderer package pins Source Sans 3 5.3.0. The retained public font package LICENSE has the same notice wording. | Installed text matches frozen notice copy; no font-service acquisition performed. |
| Renderer dependencies | `resources/licenses/react-MIT.txt`, `react-dom-MIT.txt` and `lucide-ISC-and-Feather-MIT.txt`. Frozen package pins React/DOM 19.3.0 and Lucide 1.52.0; their full notices are retained. | Directly present; development dependency trees are not presumed shipped. |
| Electron/Chromium | Root `LICENSE.electron.txt`, 1,096 bytes; root `LICENSES.chromium.html`, 20,472,830 bytes. | Presence/size observed. Electron text hashed; the large Chromium HTML was not read, hashed or exhaustively reviewed. |
| CPython | Backend `python/LICENSE.txt`, 35,407 bytes, in the retained embedded CPython 3.14.4 payload. | Installed file identity equals inventory; no Python import or execution. |
| Selected OSS engines | Backend `dependencies/*dist-info/licenses/`: Mem0 2.2.1 Apache-2.0; Docling-slim 2.133.0 / Docling-core 2.99.0 MIT; FastEmbed 0.8.1 Apache-2.0 plus its Qdrant NOTICE; LanceDB 0.39.0 and Qdrant client 1.19.1 Apache-2.0. Docling 2.133.0 wrapper metadata declares MIT but does not itself list a licence file; Docling-slim supplies the retained code notice. | Selected full licence files and FastEmbed NOTICE reach installed dependencies and match inventory. No claim that all 148 listed distributions were legally reviewed. |
| Other native dependencies sampled | Backend `dependencies/onnxruntime/LICENSE` and `ThirdPartyNotices.txt`; OpenCV dist-info `LICENSE.txt` and `LICENSE-3RD-PARTY.txt`; pypdfium2 dist-info licence directory is inventoried. | Selected installed text identities checked. Transitive source/object-code obligations are not exhaustively assessed. |
| BGE embedding helper | `resources/licenses/runtime-helpers/BGE-upstream-MIT.txt`; original BGE/Qdrant card in backend helper assets; pinned manifest/provenance identifies BAAI and the ONNX port. | Full original MIT notice, card attribution and source/hash records present. |
| Heron layout helper | `resources/licenses/runtime-helpers/Heron-Apache-2.0.txt`; original Heron card declaring Apache-2.0. | Full Apache text and card present. |
| TableFormer helper | `resources/licenses/runtime-helpers/TableFormer-CDLA-Permissive-2.0.txt`; original model card declaring CDLA-Permissive-2.0. | Full agreement accompanies weights; its sharing condition expressly calls for the agreement text. |
| OCR helpers | `resources/licenses/runtime-helpers/RapidOCR-Apache-2.0.txt` and `PaddleOCR-Apache-2.0.txt`; exact ModelScope v3.9.2 URLs/hashes in backend helper manifest, with retained public rights-source record in helper PROVENANCE. | Both full texts reach installation. Rights-source evidence is the retained October 4 acquisition, not a new upstream check. |
| Installer-tool notices | `resources/licenses/windows-installer/`: electron-builder MIT, NSIS licence, 7-Zip licence and COPYING. | All four installed files present and pinned. Their presence does not imply every build-tool executable is shipped. |

The helper provenance record specifically preserves five acquired texts and
their source digests. The bundle/manifest retain **19 helper files, 483,597,181
bytes** and the three embedding/Docling/OCR groups. Model binaries were not
read or revalidated in this lane. Full helper texts live in the desktop
resources licence directory, not in the backend-only payload licence directory.
The final combined installation therefore matters when judging their presence.

CC BY 4.0 section 3(a)(1)(C), inspected in the already shipped pypdfium2 licence
text, permits the licence text **or** a URI/hyperlink. The original-content
notice supplies the link and pack attribution. Absence of a dedicated full
legalcode beside the content is not, by itself, a missing licence-text
obligation. A full copy is also shipped at backend
`dependencies/pypdfium2-5.14.0.dist-info/licenses/LICENSES/CC-BY-4.0.txt`; that
dependency location is not used to relabel the content notice as full legalcode.

## Concrete omission and smallest repair

ANTLR Python runtime 4.9.3 METADATA says `License: BSD`. There is no licence
file in its retained dist-info directory or `dependencies/antlr4/` notice
paths. The shipped `dependencies/antlr4/Token.py` licence header identifies
copyright 2012–2017 The ANTLR Project and says its BSD 3-clause licence can be
found in `LICENSE.txt` in the project root. That referenced file is absent
from this package. The helper notice preserves source/wheel digests and
describes retained source headers, but neither it nor METADATA contains the
complete project BSD conditions/disclaimer. Headers alone do not supply the
missing referenced text.

The minimal parent repair is to retain the original ANTLR 4.9.3 project BSD
3-clause copyright/licence text associated with the recorded public sdist (SHA256
`f224469b4168294902bb1efa80a8bf7855f24c99aef99cbefc1bcd3cce77881b`) as a
scoped notice. A recorded sdist digest does not establish that its archive
contains LICENSE.txt; obtain the original text from retained public source
material, or the exact official upstream release licence if that file is absent.
For a future source-packaging update, the scoped notice can be
`apps/desktop/licenses/runtime-helpers/ANTLR4-BSD-3-Clause.txt`, with its exact
text/source digest in helper provenance. The existing `licenses/**` and
licence-directory resource mappings already carry such a file; no dependency,
model, runtime or UI change is needed. Parent owns any distribution supplement
or later manufacture and its identity record. This lane performs no repair or
repackaging and leaves the tested freeze and installed sources unchanged.

### Practical companion disposition for the current frozen app

**A public companion notices folder is the minimum current-delivery repair;
manufacture and app tests need not be repeated for this documentation addition.**
Parent can supply `matching-699938f2/notices-699938f2/` beside the original
installer, containing these three small files:

1. `ANTLR4-4.9.3-BSD-3-Clause.txt`: the verbatim original project copyright,
   all three licence conditions and disclaimer, with no placeholder owner/year.
   A generic BSD template or the wheel's short METADATA field is insufficient.
2. `README.md`: identify the library and wheel version 4.9.3, the full app
   freeze `699938f20efb6bbc2cf8df684cc5c6c3450e6eaf`, unchanged installer
   filename and SHA256 from the identity table above, and the exact public
   source/release identity for the supplied licence. State that this folder
   supplements the installed ANTLR header and does not replace the other
   already-shipped scoped notices. Include the existing developer-wheel pin
   `d234a2e0a26cf1f0a1ae5b727d8c71c1c3305ef183f962f729a0b4b915bd20e7`.
3. `manifest.json`: record the same app/installer binding, licence source
   identifier, and the measured byte counts and SHA256 values of the actual
   companion licence and README. These companion hashes are pending actual
   preparation; none is invented or reported as performed here.

Distribute the unchanged installer **together with** the companion folder,
preferably in one public delivery ZIP/directory containing the original
installer bytes and this notices folder. A separate notices asset must be
clearly paired and supplied to the same recipients, including the owner of the
existing installation. An undelivered file remaining in a developer worktree
does not repair notice delivery. Keep the folder outside the installed/payload
trees, ASAR and executable: all previously accepted app hashes and inventory
remain valid. Adding documents beside the installer is not remanufacturing it.
The original standalone installer still has the omission if subsequently
redistributed without its companion; record closure for the combined delivery
unit only, and require redistributors to carry the notice with it.

The already-shipped BSD-3-Clause reference text at backend
`dependencies/pypdfium2-5.14.0.dist-info/licenses/LICENSES/BSD-3-Clause.txt`
(SHA256 `ad9a9e823df025f42389c1812eae28019f657d1ed7b3a4ebfd5010b0736a0da4`)
states that binary notices may be reproduced in accompanying documentation or
other distribution materials. It is a template with placeholder owner/year,
so it supplies that condition's evidence, not the missing ANTLR attribution.
Parent need only verify the exact original ANTLR text and the small companion
files/binding; no runtime, helper, model or provider execution is required by
this repair. Until the companion is actually supplied, the ANTLR gap remains
open. This lane has created no companion folder and changed no delivery input.

No other missing file is established in this targeted audit. Original teaching
content already carries its CC BY licence link and attribution; font, Hermes
and the selected helper full texts already reach the installation. The stock
FastEmbed NOTICE also names Jina/Gemma catalogue models: preserve that upstream
notice, but distinguish it from the frozen app's actual embedding/Docling/OCR
helper manifest. Catalogue mentions alone do not establish those other weights
are shipped or add a licence gate for them. The public contributor-directory
minimisation suggestion below is optional future packaging hygiene, not a
missing-notice obligation or prerequisite for current local use.

## Acquired/private-data boundary

The retained backend inventory has public runtime/source/dependencies, Python,
helper assets, source-register metadata and original teaching packs.
`content/` contains 31 records. Outside dependency source code, no path matches
the checked `.local`, `.git`, `.venv`, Renulus-data, profile, originals, acquired,
credential/account-state directory names or auth/state database/env filenames.
Two profile-name matches are Faker dependency source modules, not learner
profiles. The packaging source allowlist admits committed runtime, original
content, licences, Hermes and packaging metadata; acquired collection/profile
roots are not inputs. Thus retained path/provenance evidence supports exclusion
of the acquired collection and local private application state from this
distribution. It does not prove semantic absence of private information in
every public source file; no raw/account/profile/collection bytes were opened.

The public Hermes snapshot also includes **1,746 contributor-directory entries,
37,667 bytes**, including its `.gitkeep`, under
`upstream/hermes/contributors/emails/`. These are inventoried upstream-public
files, not evidence of importing the owner's private correspondence. Their
contents were not read, copied or hashed here, and addresses are not reproduced
in receipts/report. This directory is unnecessary for runtime/attribution and
may be omitted from a later scoped public snapshot for data minimisation while
preserving the upstream licence/provenance. No current-artifact deletion is
recommended or performed.

## Compact receipts, changes and handoff

All receipt paths below are absolute. Receipt hashes are actual SHA256 values.
The file-hash receipt lists exact source paths, sizes and hashes for selected
installed files; observations records inventory comparisons, selected metadata,
public root counts and scope flags. No full inventory copy is created.

| Receipt/source | SHA256 |
| --- | --- |
| `C:/rn-finalise-20261005/parent-native-recovery-699938f2-699938f2-next01/completed-current-inventory.json` | `e1c7e2dc03a79b37f5b195d03f4f3fcee22c434ab80daa14f3abde81e0953904` |
| `C:/Renulus-native-delivery/desktop-20261005/matching-699938f2/delivery-provenance.json` | `9ab9e469ea4e925c72ec19531521a41ff95a00cea121c6bc7fb7a4d1fd34a2c4` |
| `C:/Renulus-native-delivery/desktop-20261005/payloads/backend-699938f2/inventory.json` | `3b0fc2c9d277ba78cdeef461f53875b8f0fb0d4a6ae1c5cf0e89e1bd476326af` |
| `C:/rn-finalise-20261005/lanes/distribution-notices-20261006/.local/notices-699938f2/observations.json` (17,222 bytes; observed 13:30:09.7160925 UTC) | `e3fd7159a4ea03ef48509fd5834c5c510df5f5b3d75bac806f32729505e65961` |
| `C:/rn-finalise-20261005/lanes/distribution-notices-20261006/.local/notices-699938f2/file-hashes.json` (14,876 bytes) | `ec306565862f2610c77724afac74863d412926abbd3224c48a64bd7ef0844f2a` |

Only tracked change: `docs/implementation/finalise-notices-699938f2.md`.
Ignored lane-owned outputs: `.local/notices-699938f2/inspect-static.ps1`,
`observations.json`, `file-hashes.json`. The script is a PowerShell static
metadata/licence inspector; it imports no app runtime and invokes no helper.
Its console-only dictionary projection was corrected after receipt generation;
receipt bytes above were preserved. Parent must retain these ignored receipts
before worktree retirement.

This practical-disposition follow-up reread only the existing report/receipts,
retained helper/package notices and one already-shipped BSD reference text.
The original two receipt hashes remain unchanged. Only this report was amended;
there was no second inventory inspection, runtime/native/installer execution,
payload mutation, companion preparation or licence acquisition. Parent's
existing-profile reader slice remains independent on freeze699938f2.

Verification is scoped text/path/hash comparison, ignored-output validation,
explicit Git changed-file review and `git diff --check`. No tests, builds,
native/installer/helper/model/provider execution, network acquisition, E-data
inspection, credentials access, push or other-lane mutation occurred. Commit
uses hooks/signing disabled. No exhaustive legal clearance, successful live
journey, complete release pass or external review prerequisite is asserted.
