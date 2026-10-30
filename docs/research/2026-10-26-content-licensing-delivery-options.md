# Content licensing and delivery options for Renulus

**Checked:** 2026-10-26. **Status:** research and proposals; no product changes or corpus acquisition. This note supports, and does not replace, the single source register in [docs/SOURCES.md](../SOURCES.md). Source IDs below refer to that register. Public availability, copyright permission, acquisition permission and scientific currentness are separate checks.

## Recommendation

Renulus can ship a useful library spanning nephrology now using its original material and specifically licensed third-party works. A practical minimum is:

1. **Keep the existing original foundations pack 1.4.2:** 27 topics, 251 assessment questions and 59 synthetic teaching cases. Its six JSON files total **1,172,015 bytes** in this checkout. It spans physiology, electrolytes, AKI/critical care, CKD, glomerular/tubular/inherited disease, infection, cancer, dialysis, transplantation, medicines, pregnancy/life course, nutrition and supportive care. These are counted repository artifacts, not evidence of complete curriculum coverage or educational efficacy. Keep assessment-reserved questions out of teaching retrieval and generated practice.
2. **Proposed next authoring increment:** one concise original overview and five original teaching cards for each of the 27 topics: **27 overviews and 135 cards**, drawing on existing objectives/cases and verified source locators. This gives every topic useful initial teaching depth. Publish a new immutable revision after source and answer checks; retain the stated assistant-review status. These additions do not exist merely because they are recommended here.
3. **Add a small eligible full-text shelf:** the three exact CC BY 4.0 journal versions verified in option B below. They establish a workable route across kidney protection, dialysis and pregnancy. Preserve their publication dates; the older documents are dated study references until currentness is checked, rather than automatically current guidance. Expand by topic as individual rights and relevance are verified; no entire-journal licence is assumed.
4. **Include a dated official-link catalogue** covering all 27 topics, using KDIGO, UKKA and ERA channels and precise publication identities. Offer permitted full-text downloads separately. Add a few manually obtained, attributed Servier kidney/nephron illustrations if adopted.
5. **Offer selected personal imports** from local folders or a user-selected Drive download, with each file's actual permissions. Accept member/institutional material through its allowed reading or permission route. Drive can also deliver an openly licensed Renulus pack with its manifest; storage location does not change the licence.

The existing baseline is evidenced by [content/LICENSE](../../content/LICENSE), the [1.4.2 manifest](../../content/packs/renulus-foundations/1.4.2/manifest.json), [topics](../../content/packs/renulus-foundations/1.4.2/topics.json), [questions](../../content/packs/renulus-foundations/1.4.2/questions.json) and [cases](../../content/packs/renulus-foundations/1.4.2/cases.json). Its manifest states `complete_curriculum: false`, `complete_esen_eph_blueprint: false` and `independent_human_review: false`. Installed availability was not tested in this research.

## Six concrete source and delivery options

### A. Renulus original packs: the default preload

**Exact scope:** original taxonomy descriptions/objectives, synthetic cases, stems, choices and rationales under `content/`; selected published pack `renulus-foundations/1.4.2`, dated 2026-10-07. The scoped [licence](../../content/LICENSE) is **CC BY 4.0**, with the pack's own attribution string.

**Feasible operations:** bundle, distribute through an installer or Drive, cache, extract, index/embed, display, and adapt into teaching summaries/cards. Index only the teaching export; the reserved-bank boundary is a product assessment rule, independent of the public copyright licence. No inference/training call is needed for delivery.

**Required notices:** credit Renulus contributors, identify pack/version, retain supplied copyright/licence notices, link CC BY 4.0 and identify changes. Citation metadata does not license the cited documents. Third-party prose, figures, manual chapters and official exam items are outside this grant. The [CC BY 4.0 legal code, sections 2–3](https://creativecommons.org/licenses/by/4.0/legalcode.en) supplies the reproduction/adaptation grant and notice requirements; applying that grant to indexing and model-input copies is an interpretation of those broad copyright permissions, not a separate AI certification.

### B. Three exact CC BY journal versions: reusable reading and adaptation

These are individual licensed works, including journal-published association guidelines. Their publisher **Rights and permissions** sections were checked, not inferred from publisher identity or a free PDF button.

| Exact work and version | Verified rights and identity | Recommended use |
| --- | --- | --- |
| Roddick et al., **UK Kidney Association Clinical Practice Guideline: SGLT-2 Inhibition in Adults with Kidney Disease 2023 UPDATE**, BMC Nephrology 24:310; version of record **2023-10-25**; DOI **10.1186/s12882-023-03339-3**; PMCID **PMC10598949** | [Publisher licence/version](https://link.springer.com/article/10.1186/s12882-023-03339-3#rightslink): **CC BY 4.0**, including adaptation and redistribution; third-party credit-line exclusions apply. [PubMed identity](https://pubmed.ncbi.nlm.nih.gov/37880609/). | Kidney protection/diabetes/CKD teaching, attributed reading and cards. Check intervening changes before current-guidance labels. |
| Ashby et al., **Renal Association Clinical Practice Guideline on Haemodialysis**, BMC Nephrology 20:379; version of record **2019-10-17**; DOI **10.1186/s12882-019-1527-3**; PMCID **PMC6798406** | [Publisher licence/version](https://link.springer.com/article/10.1186/s12882-019-1527-3#rightslink): **CC BY 4.0**. [PMC licence record](https://pmc.ncbi.nlm.nih.gov/articles/PMC6798406/). | Dated dialysis study reference and eligible adaptations. Licence permission does not establish that 2019 guidance remains current in 2026. |
| Wiles et al., **Clinical practice guideline on pregnancy and renal disease**, BMC Nephrology 20:401; version of record **2019-10-31**; DOI **10.1186/s12882-019-1560-2**; PMCID **PMC6822421** | [Publisher licence/version](https://link.springer.com/article/10.1186/s12882-019-1560-2#rightslink): **CC BY 4.0**. [PMC licence record](https://pmc.ncbi.nlm.nih.gov/articles/PMC6822421/). | Dated pregnancy/life-course study reference, with source checks before new teaching keys. |

For these licensed portions, copying/bundling, local extraction/indexing, attributed excerpts and distributed adaptations have an affirmative copyright route. Preserve authors, title, DOI/version, copyright/licence notice and change history. Treat images, supplements and separately credited material as assets needing their own scope check. The BMC notices also apply **CC0 1.0 to data made available in those articles unless otherwise stated**; that does **not** make the article text CC0, establish that any particular dataset is available, or authorize patient-data use. No datasets were inspected.

**Acquisition route:** Europe PMC documents an eligible OA subset and its [REST fullTextXML interface](https://europepmc.org/RestfulWebService), [OA download services](https://dev.europepmc.org/downloads/openaccess), and [copyright/acquisition conditions](https://dev.europepmc.org/Copyright). Automated article retrieval must use its documented REST/SOAP/OAI/bulk services; do not scrape batches from article web pages. Check the returned article/version licence and asset exclusions before activation.

**Bounded verification:** three public, keyless **metadata-only** REST requests returned `isOpenAccess: Y`, `inEPMC: Y`, matching DOIs/PMCIDs and OA Europe PMC links on this date:

- [SGLT-2 record](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID%3A37880609%20AND%20SRC%3AMED&format=json&resultType=core&pageSize=1).
- [Haemodialysis record](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID%3A31623578%20AND%20SRC%3AMED&format=json&resultType=core&pageSize=1).
- [Pregnancy record](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID%3A31672135%20AND%20SRC%3AMED&format=json&resultType=core&pageSize=1).

This establishes a documented permitted acquisition route and matching eligible records. Full-text endpoint responses, byte hashes, rate limits, correction completeness and a Renulus downloader were **not verified**. Metadata's DOI availability label said subscription required despite the explicit publisher CC BY statements; record-level flags are discovery aids, not the final rights decision. A missing/null retraction field was not treated as retraction clearance. PMC is an alternative through its [documented services](https://pmc.ncbi.nlm.nih.gov/tools/textmining/); its legacy distribution layout changed in August 2026, so do not prescribe obsolete FTP packages.

### C. KDIGO: an affirmative NC/ND route with exact-file boundaries

The official **2025 ADPKD full guideline**, Kidney International 107(Suppl 2S), S1–S239, DOI **10.1016/j.kint.2024.07.009**, has **CC BY-NC-ND 4.0** frontmatter. Its [official PDF, printed S13 / PDF page 14](https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2025-ADPKD-Guideline.pdf#page=14) expressly permits noncommercial copying/distribution, extracts and **“text or data mine the article”**, and personal adaptations without distributing them. Credit the work and retain DOI/licence links and notices. [Topic and suite](https://kdigo.org/guidelines/autosomal-dominant-polycystic-kidney-disease-adpkd/).

**Usable route:** unaltered, attributed noncommercial copies; personal offline study; permitted text mining. Local search/embeddings are a proposed application of the mining grant, requiring implementation to preserve source/output boundaries. A shared adapted summary pack and sending text to a remote model service are **not verified** by that wording. Ask KDIGO for those exact operations, including downstream retention and outputs, if desired.

The [CC BY-NC-ND 4.0 legal code, section 2](https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.en) also permits producing/reproducing noncommercial adaptations without sharing them, and allows necessary technical format changes. ND does not itself forbid private adaptation. NC depends on the actual use; free software or nonprofit status alone does not settle it. [CC's NC explanation](https://creativecommons.org/faq/#does-my-use-violate-the-noncommercial-clause-of-the-licenses) supports seeking clarification for the specific use.

**Acquisition distinction:** a public download is offered; a supported bulk/agent interface or automated-site-acquisition permission was **not verified**. Manual official download and eligible personal handling remain feasible. A setup agent can use an approved endpoint or individually licensed Renulus delivery artifact if that route is subsequently established.

**Do not generalize across KDIGO files:** the [2024 CKD full guideline, S129 / PDF page 14](https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2024-CKD-Guideline.pdf#page=14) prints CC BY-NC-ND alongside restrictive reproduction/storage boilerplate. Preserve both statements; do not invent their reconciliation. For that exact file, personal reading/download is the practical verified route; a broader integration grant needs clarification. [KDIGO Rights & Permissions](https://kdigo.org/ufaq-category/rights-permissions/) gives a case-by-case request route, potentially free for educational/nonprofit requests, without guaranteeing a fee waiver. No request was sent.

### D. Official links and currentness records: broad coverage with little storage

Bundle Renulus-authored topic labels and factual bibliographic/currentness records with external links. No body text, abstracts, figures or licensed page layout need be copied. This is a concrete delivery mode even when full-text reuse is not established; it is not a full-text RAG corpus.

- [KDIGO CKD topic](https://kdigo.org/guidelines/ckd-evaluation-and-management/): identifies the **2024 final** and a **2027 focused-update public-review draft** open through November 4, 2026. These must be distinct records; the newer date does not make the draft final.
- [KDIGO anemia topic](https://kdigo.org/guidelines/anemia-in-ckd/kdigo-2026-anemia-in-ckd-guideline/): identifies the **2026 guideline**. The link catalogue can expose this scope without assuming every suite asset has identical reuse terms.
- [UKKA guidelines and commentaries](https://www.ukkidney.org/health-professionals/guidelines/guidelines-commentaries): records publication and review dates. The checked catalogue gives an SGLT-2 review date of April 13, 2027 and a hyperkalaemia review date of October 19, 2026. The latter date has passed; that is a review-status flag, not proof of a replacement. The association catalogue record and journal version in B have distinct dates/identities.
- [ERA Guidance](https://www.era-online.org/era-guidance/): an official route to kidney disease guidance, commentaries and practice documents. Label article type and check the linked publication's own terms. A journal commentary is not the underlying KDIGO guideline.

**Link scope:** propose ordinary external navigation to publicly offered landing pages with no framing, mirrored content, logos or implied endorsement. A universal contractual deep-linking grant was **not verified**. In particular, the separate [UKKA Education Hub terms, section 8](https://education.ukkidney.org/terms) allow homepage links but require permission for deeper links there; use its homepage unless permission is obtained. Do not transfer that subdomain rule to the main UKKA guideline site or assume that all sites have one rule.

Store final/draft, edition, topic/chapter replacement, correction/retraction relationships, checked-at and failed-check dates separately. Propose weekly bounded catalogue checks and checks before freshness-sensitive teaching updates; automated catalogue access must first be verified for each endpoint. A failed refresh cannot advance a current label. Repository/publisher absence is not evidence of no correction.

### E. Servier Medical Art: reusable illustrations, with a manual acquisition path

The exact [Kidney](https://smart.servier.com/smart_image/smart-kidney/) and [Nephron](https://smart.servier.com/smart_image/nephron/) pages provide image downloads and identify **CC BY 4.0**. [Servier's terms, section 3](https://smart.servier.com/terms-of-use/) distinguish the licensed medical images from proprietary site text/layout/structure and trademarks. Images can be copied, distributed commercially and adapted with credit, a licence link and change notices; no endorsement is implied.

**Feasible delivery:** manually obtain a few selected images through official downloads in a separately authorized adoption step, record exact asset hashes and licences, then include those images and notices in Renulus packs. A setup agent could later download the resulting eligible Renulus pack from its approved release location. Site Content has a bot/scraper restriction; an automated image acquisition endpoint or exception is **not verified**. This is a reason to use the manual acquisition plus licensed redistribution route, not to discard the usable illustrations. Site screenshots/logos are outside the image grant. No image was downloaded into this repository.

### F. User-supplied local/Drive/member/institutional files, including ERA

**Delivery proposal:** a user selects named files locally, or downloads named Drive files into a chosen local folder, then deliberately imports them. A rights manifest travels alongside an eligible pack. Do not enumerate a Drive, import every synchronized file, or treat possession, a shared-link setting, subscription access or a user declaration as a new copyright grant.

**Affirmative paths:** original user-authored teaching with adequate rights; CC BY/CC0 files under their exact grants; specifically permitted institutional files; unchanged authorized personal study copies; and rights-holder permission for additional processing. Indexing, remote model input, adaptations and public sharing are separate operations. If only reading rights are established, retain an external-reader/link route while seeking the requested extra permission. A university's subscription/AI terms must be checked for that institution and file; none were inspected here.

The current [ERA Neph-Manual landing page](https://www.era-online.org/era-neph-manual/) describes an active-member educational resource spanning nephrology, with theory, illustrations and tests. It does not establish a universal downloadable edition, export API, or per-chapter processing grant.

The English-language text served at ERA's official [Terms and Conditions page, sections 8–9](https://www.era-online.org/ru/publications/terms-and-conditions/) permits reasonable copies of defined **Work** for personal/professional noncommercial use and one's own teaching with ERA/author acknowledgement; it restricts modifications, commercial use and data collection/use without written consent. The English canonical URL returned 403 in this browsing run; this official locale page served the English terms. **Whether those Work permissions cover a particular Neph-Manual chapter/export, and its local indexing or remote AI use, is not verified.** They are not a blanket manual redistribution grant.

**Concrete permission path:** ask ERA to identify covered chapters/assets/MCQs and revisions, permit member-selected local download/retention, OCR/chunking/embedding, retrieval excerpts, input to the selected subscription models, retention/deletion, and private generated study aids. Request public summary/card/MCQ redistribution separately, including adaptation and illustration rights. Existing owner authorization establishes the acquisition direction; it does not replace ERA's content licence. Continue using official member reading and any expressly offered authorized file/export in the meantime. No credentials, account pages, supplied private files or Drive contents were read.

## Compare the five delivery approaches

These are proposals. A different delivery channel does not remove licence conditions.

| Approach | Concrete feasible route | What must be recorded / remaining boundary |
| --- | --- | --- |
| **1. Bundled/preloaded full text** | Original Renulus packs and licensed portions of the three B works. A separate unchanged NC collection is possible under its exact grant, after confirming the actual distribution's NC scope. | Exact version/hash and asset exclusions; notices and change history; full-text inclusion does not automatically authorize every model/service use. Do not label a mixed bundle entirely MIT or original Renulus CC BY. |
| **2. Preloaded summaries/cards** | Original teaching across all topics; attributed adaptations of verified CC BY portions; private NC/ND adaptations where granted. | A summary is not an automatic copyright exemption. Preserve source provenance and distinguish original factual explanation from protected expression, tables, illustrations or adapted questions. Public ND adaptations need a separate basis/permission. |
| **3. Link-only catalogue** | D: official landing pages, source IDs and concise Renulus-authored metadata, with explicit currentness/access states. | Linking/deep-link terms where applicable; no mirrored source content; remote page reading is separate from indexed app retrieval. Do not copy abstracts on the assumption all metadata is freely reusable. |
| **4. Opt-in setup downloading** | B through documented Europe PMC interfaces, checked per article/version. After authorized adoption, eligible image/teaching packs can be delivered from Renulus's approved distribution location. | Opt-in selection and size estimate; permitted endpoint/method, licence, integrity, attribution and version validation before index activation. No login scraping, automatic paid fallback or whole-biomedical-corpus download. KDIGO/ERA automation remains not verified. |
| **5. User-supplied local/Drive files** | F, with selected files and precise access/licence/permission evidence. Eligible CC BY packs have the same reuse route whether installed, on disk or delivered through Drive. | Reading, local processing, remote disclosure and redistribution assessed separately; no Drive crawl or credentials needed. Restricted personal copies retain their restrictions. A new permission can unlock additional operations. |

The factual-expression distinction is supported by [WIPO's copyright explanation](https://www.wipo.int/en/web/copyright/protection). It does not provide a universal exemption for paraphrases or summaries. Proposed authoring should independently explain facts using multiple verified references and review the resulting prose/media; do not automatically publish source-to-summary transformations of restricted manuals.

### Operation decisions to carry into a manifest

- **Reading/display:** allowed within each verified grant; ERA/manual and institutional scope stays file-specific.
- **Local extraction/OCR, indexing and embeddings:** an affirmative copyright route exists for original and licensed CC BY portions; applying the grant to these technical copies is an inference. KDIGO ADPKD expressly permits noncommercial mining; precise implementation/output boundaries still need checking. Unknown rights remain `not_verified` rather than being described as impossible.
- **Model input:** for CC BY portions, reproduce/adapt permission supplies the copyright basis, subject to notices and exclusions. Provider contractual rights, onward retention and output handling are independent and were not researched or tested here. For NC/ND and restricted files, the remote-provider operation is `not_verified`; the verified reading/local route remains available. Do not turn a local mining permission into a training or unrestricted disclosure grant.
- **Adaptation and redistribution:** CC BY permits both with compliance; CC0 applies only to material actually dedicated; ND can permit private adaptations and unchanged sharing while withholding public adapted sharing. For all-rights-reserved material, source reading, specific permissions or a verified applicable exception can supply a route. No general EU/national-law exception is asserted by this note.
- **Training:** outside the authorized Renulus task and product direction; not an acquisition or processing goal here.

## Proposed licence manifest

Use one canonical record per acquired **version and asset**, linked to `docs/SOURCES.md`. Keep public bibliographic/use-status data separate from private agreements and entitlements. Store no credentials, private signed agreements or user file paths in public Git. Proposed minimum fields:

- Identity: record/register IDs, title, authors/rightsholder, DOI/PMID/PMCID, version-of-record versus manuscript, language/jurisdiction, publication date and actual bytes/hash.
- Origin/acquisition: canonical origin and retrieval URLs, endpoint/method, acquired-at, checked-at, entitlement class and permitted retention. Cloud/file delivery provenance is separate from original publication provenance.
- Rights: precise licence identifier/version/URL, article/asset-level scope, excluded material, exact evidence URL/locator and check date; permission reference where relevant; permitted operations with conditions and evidence.
- Attribution: required credit/copyright/licence/warranty notices, source link, change description and retained earlier change notices; no-endorsement requirement.
- Lifecycle: correction, retraction, supersession and chapter replacements, access/licence change, review due, failed verification, related versions, content-review date and affected teaching/item IDs.
- Storage: original/extracted/index revision IDs, physical byte sizes, derivative dependencies, rebuild state, retention and deletion rules.

Example **candidate**, deliberately not an acquired/ready record:

```json
{
  "schema_version": 1,
  "record_id": "candidate:PMC10598949:vor-2023-10-25",
  "source_register_ids": ["G02", "L03"],
  "title": "UK Kidney Association Clinical Practice Guideline: SGLT-2 Inhibition in Adults with Kidney Disease 2023 UPDATE",
  "creators": "Roddick et al.; preserve complete supplied author credit on adoption",
  "doi": "10.1186/s12882-023-03339-3",
  "pmcid": "PMC10598949",
  "version": "version-of-record:2023-10-25",
  "origin_url": "https://doi.org/10.1186/s12882-023-03339-3",
  "proposed_acquisition_url": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10598949/fullTextXML",
  "acquired_at": null,
  "content_sha256": null,
  "original_bytes": null,
  "access_class": "public-open-licence",
  "licence": {
    "id": "CC-BY-4.0",
    "version": "4.0",
    "url": "https://creativecommons.org/licenses/by/4.0/",
    "scope": "article licensed portions; asset credit-line audit pending",
    "evidence_url": "https://link.springer.com/article/10.1186/s12882-023-03339-3#rightslink",
    "evidence_checked_on": "2026-10-26"
  },
  "operations": {
    "display": {"status": "allowed", "condition": "retain required notices"},
    "redistribute_original": {"status": "allowed", "condition": "licensed portions; attribution; asset exclusions"},
    "local_extract_index_embed": {"status": "conditional", "basis": "inference from CC BY reproduction/adaptation grant; asset scope check"},
    "model_input_remote": {"status": "conditional", "basis": "CC BY copyright grant; provider contract and onward handling not verified"},
    "share_adaptation": {"status": "allowed", "condition": "attribution; identify changes; exclusions"},
    "automated_download": {"status": "conditional", "basis": "documented Europe PMC service; exact response/version/integrity not yet checked"}
  },
  "attribution": {
    "credit": "Authors; full title; BMC Nephrology 24:310 (2023); DOI; copyright notice; CC BY 4.0",
    "changes": "none; candidate only",
    "preserve_supplied_notices": true
  },
  "currentness": {
    "status": "dated-reference-currentness-not-verified",
    "corrections": [],
    "correction_search_complete": false,
    "superseded_by": [],
    "retraction_status": "not_verified",
    "review_due": null,
    "last_failed_check_at": null
  },
  "ready_for_index": false
}
```

An empty relationship list is not a completed search. Capture actual hash/acquisition time only after authorized acquisition, and never substitute the publisher page's timestamp for the document's publication/version date. A licence change, repository removal, scientific retraction and corrected document are distinct events. Preserve dated permission evidence; any withdrawal handling depends on the applicable grant rather than a presumed universal revocation rule.

## Proposed bounded storage: 50 GB default, at most 150 GB by choice

This is a budget proposal, not measured installed usage or a new cleanup authorization. The minimum content above does not require tens of GB. Start with a small preload and selected downloads. Use **50 GB as the default managed-storage ceiling**, offer a deliberate increase to 100 GB or at most **150 GB total**, and count app-managed copies, indexes, staging and rollback together.

| Budget component | Default maximum |
| --- | ---: |
| Selected acquired/imported originals, including current preload | 15 GB |
| Extracted text, OCR and page/image derivatives | 8 GB |
| Derived search/vector/memory indexes | 6 GB |
| Canonical SQLite, saved learning and authored content | 4 GB |
| Download/cache/temporary working space | 3 GB |
| Retained managed prior versions and rollback | 4 GB |
| Managed app/runtime/helper artifacts | 5 GB |
| Reserved headroom for atomic rebuild/replacement | 5 GB |
| **Total** | **50 GB** |

These are engineering caps, not claims about compression ratios or index sizes. Check projected and actual bytes before starting import/rebuild. Deduplicate identical bytes by hash with separate provenance/rights records, and use one extraction/index per actual revision and pipeline configuration. Avoid redundant complete libraries. Stage only a bounded batch; pause before exceeding the reserve. Retire rebuildable caches first. Do not silently delete originals, saved learning, required history or the only old revision; offer an explicit move/export or stop new acquisition when protected content fills its allocation.

The user's existing external collection or Drive may exceed this budget; no inventory or deletion of either was performed. Count a copy when Renulus manages it. Do not count a cloud placeholder as available offline content or promise its storage behavior. Default no videos, whole PMC/OpenAlex snapshots or whole-Drive synchronization. Existing workspace/storage decisions remain authoritative until a later implementation explicitly adopts a new policy.

## Findings for the parent and precise open questions

**Parent reconciliation, October 26:** the E06 identity/provenance error below
has now been corrected in `docs/SOURCES.md`, with this note linked there as
dated evidence. No teaching pack or question key was changed by that correction.

1. **Source-register mismatch, verified:** E06 in `docs/SOURCES.md` describes DOI `10.1007/s00467-026-07189-7` as an April 29 anti-CD20 educational review with MCQs/keys. The [actual publisher record](https://link.springer.com/article/10.1007/s00467-026-07189-7) is Kasap, İrdem and Yüksel, **Coexistence of acute post-streptococcal glomerulonephritis and acute rheumatic fever: case report and systematic review**, version of record **2026-02-17**, Pediatric Nephrology 41:2863–2875. It does verify **CC BY 4.0**, with credit-line exclusions. The claimed review identity, date and MCQ provenance are not established by that DOI. This actual article is a possible licensed pediatric/glomerular reading candidate; it was not adopted or counted as a reviewed question source.
2. **Repository status text is dated:** `content/README.md` calls 1.4.0 the latest authored pack, while the checked published 1.4.2 manifest/files contain 251 questions and 59 cases. This note uses those concrete files. Parent owns any reconciliation elsewhere.
3. **KDIGO:** confirm automated acquisition conditions, reconcile the CKD PDF boilerplate, and obtain specific permission/clarification if remote subscription processing or shared adapted teaching is desired. The ADPKD personal/noncommercial/mining grant already supplies useful operations; no blanket prohibition is warranted.
4. **ERA/member/institutional:** obtain chapter/export-specific terms and rights for OCR, index/embeddings, remote model input, saved outputs and any redistributed derivatives/MCQs. The general Work definition and personal-copy clause do not settle the manual. No private agreement was inspected.
5. **Servier:** an automated image-acquisition endpoint is not verified. Manual download followed by attributed licensed redistribution is the concrete route; adopting images remains future work.
6. **Acquisition/currentness:** three literature metadata records and their publisher licences were checked; exact acquired XML/PDF versions/hashes, third-party assets, latest corrections and full currentness clearance remain not verified. Review those during a separately authorized, selective adoption step.

All external checks were public documentation/licence/bibliographic browsing at zero acquisition/API cost. There were no paid-provider calls, model training, downloads into a corpus, private/local collection scans, Drive access or product changes. The research skill's primary-source/single-note workflow was applied in this delegated research lane; no further delegation was needed. Only this note is owned by the research task; no commit or PR was created.
