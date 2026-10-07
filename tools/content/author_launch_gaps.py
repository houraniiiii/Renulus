# SPDX-License-Identifier: MIT
"""Publish the finite launch-cell additions as immutable original CC BY 4.0 content.

No network, provider, document/model helper or private profile is used by this
publisher. Primary reading is recorded separately; it is not a currency upgrade
of the 35 inherited snapshots. Historical authoring modules remain reproducible.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

import author_foundations as base
import author_eseneph as previous
from renulus.content.validation import validate_pack
from revision_checks import validate_revision, validate_review_evidence

ROOT = base.ROOT
DATE = '2026-10-05'
VERSION = '1.1.2'
MAPPING_VERSION = '2026-10-05-launch1'
PRIOR = ROOT / 'content/packs/renulus-foundations/1.1.1'
RELEASE = PRIOR.parent / VERSION
REVIEW_PATH = ROOT / 'content/reviews/renulus-foundations-1.1.2.json'
MAPPING_PATH = ROOT / 'content/mappings/esen-eph-2026-10-05-launch1.json'

UTI = 'G07-NG112-2024-launch'
ALPORT = 'G01-Alport-2024-launch'
PD = 'L01-ISPD-peritonitis-2022-corrected-launch'
PD_ACCESS = 'L01-ISPD-catheter-2023-launch'
HD = 'G02-HD-access-2025-launch'
BK = 'L01-BK-consensus-2024-launch'
SEX = 'L01-US-MEC-2024-launch'
TRANSITION = 'G07-NG43-2016-launch'
DYING = 'G07-NG31-2015-launch'
CKD = 'K01-2024-launch-locators'
ANEMIA = 'K02-2026-launch-locators'
AIN = 'L01-AIN-treatment-review-2025-launch'

# Citation/fact use only: third-party prose, tables, algorithms and figures are
# not bundled, translated into the pack or relicensed as Renulus content.
RIGHTS = ('Original independently expressed Renulus questions/cases only. The cited '
          'publication retains its own terms; no primary text, table, figure, algorithm '
          'or official question is distributed. This reference is not an AI import, '
          'syndication or commercial redistribution permission for the source.')

def source(sid, rid, title, edition, url, canonical, scope, check, rights):
    return {'id': sid, 'register_id': rid, 'title': title, 'edition': edition,
            'publication_status': 'final', 'url': url, 'canonical_topic_url': canonical,
            'checked_on': DATE, 'check_status': 'locator_checked',
            'currency': 'dated_final_baseline', 'scope': scope,
            'rights_note': rights + ' ' + RIGHTS,
            'check_note': check + ' Scoped primary reading on 2026-10-05; this is not '
                          'a complete latest-edition/corrigendum/retraction clearance.'}

NEW_SOURCES = [
    source(UTI, 'G07', 'NICE NG112 recurrent urinary tract infection',
        '2018; recommendations updated 12 December 2024',
        'https://www.nice.org.uk/guidance/ng112/chapter/Recommendations',
        'https://www.nice.org.uk/guidance/ng112',
        'Specialist evaluation, recurrence prevention and review; supplementary UK context, no antimicrobial dosing.',
        'Official 50-page PDF read: 1.1.4 and 1.2.1-1.2.8. SHA256 23d4f73b39d9313ed89a629d10ecff40d151e1be950b85af51aeeccd2e5068eb. The PDF states the 2024 update date.',
        'NICE copyright/Notice of rights; factual reference only, no licensed connector or source-text redistribution.'),
    source(ALPORT, 'G01', 'ERKNet/ERA/ESPN Alport diagnosis and management guideline',
        '2024 guideline; NDT version of record 40(6), 2025, 1091-1106; DOI 10.1093/ndt/gfae265',
        'https://doi.org/10.1093/ndt/gfae265', 'https://www.era-online.org/era-guidance/',
        'Persistent familial hematuria, COL4A3/4/5 testing and genotype/phenotype interpretation; not ADPKD management.',
        'Version-of-record full text read through Europe PMC PMC12209846: Q4 recommendations 4.1/4.2 and explanation, Q6, Q8, Q9, Q16 and Q19. Recovery corrected the contextual-diagnosis locator from Q7 to Q8; test-sensitivity limits are Q9. XML SHA256 af7f19d41bee5781636a36365c01e79ec5ba19b2b91dd1073b5d6799f7990cb6.',
        'Publisher full text states CC BY 4.0; Torra et al., ERKNet/ERA/ESPN, NDT. No source extracts included.'),
    source(PD, 'L01', 'ISPD peritonitis guideline recommendations',
        '2022 final; published corrigenda 2023 and 2024 retained',
        'https://doi.org/10.1177/08968608221080586', 'https://ispd.org/guidelines/',
        'Diagnostic criteria, cloudy effluent evaluation and prompt specimen/treatment reasoning; no dose or refractory-treatment algorithm.',
        'Public publisher diagnostic passage checked: Identification and initial management of peritonitis. Corrigenda were read on recovery: 2023 DOI 10.1177/08968608231166870 corrects Figure 8 enterococcal treatment; 2024 DOI 10.1177/08968608241251453 corrects the refractory-peritonitis cell-count definition in Table 1. Neither corrected treatment nor refractory definitions are taught here. The initial diagnostic criterion uses >100 cells/microliter after at least two hours with >50% neutrophils. Direct script access failed and a recovery full-text request timed out; indexed publisher diagnostic text and the public correction notices were accessible. No corrected-original-byte identity or source-wide clearance is claimed.',
        'PDI/SAGE/ISPD publication retains its terms; independent clinical facts and attribution only.'),
    source(PD_ACCESS, 'L01', 'ISPD catheter-related infection recommendations',
        '2023 update; DOI 10.1177/08968608231172740',
        'https://doi.org/10.1177/08968608231172740', 'https://ispd.org/guidelines/',
        'Definitive exit-site infection, redness alone, tunnel involvement and assessment; no antibiotic regimen.',
        'Public publisher full text read: Definition and diagnosis of catheter-related infection; purulent exit discharge, with or without erythema, differs from erythema alone. Tunnel inflammation calls for assessment including ultrasound. Direct script access failed; public web publisher read succeeded, no local original-byte hash claimed.',
        'PDI/SAGE/ISPD publication retains its terms; independent clinical facts and attribution only.'),
    source(HD, 'G02', 'UK Kidney Association vascular access for haemodialysis guideline',
        'Guideline April 2023; peer-reviewed publication August 2025; DOI 10.1186/s12882-025-04374-y',
        'https://doi.org/10.1186/s12882-025-04374-y',
        'https://www.ukkidney.org/health-professionals/guidelines/vascular-access-haemodialysis',
        'Ongoing HD access assessment, aneurysm bleeding risk, clinical stenosis and trained aseptic catheter use.',
        'Publisher version read through Europe PMC PMC12351868: guidelines 3.12, 4.1-4.2, 4.6-4.7, 5.4-5.5 and chapter 6 catheter dysfunction/infection rationale. XML SHA256 c44e7aa029ae1c49c48d415514b647e75629a7fa87f2fb5589bce37397a80af3.',
        'Aitken et al., BMC Nephrology 2025, publisher CC BY 4.0. No source extracts included.'),
    source(BK, 'L01', 'Second international BK polyomavirus consensus guidelines',
        'Transplantation 2024; DOI 10.1097/TP.0000000000004976',
        'https://doi.org/10.1097/TP.0000000000004976',
        'https://pmc.ncbi.nlm.nih.gov/articles/PMC11335089/',
        'Recipient plasma surveillance, persistent DNAemia, graft dysfunction and coordinated immunosuppression review.',
        'Publisher full text read through Europe PMC PMC11335089: Tables 5-7, diagnostics and management. XML SHA256 a193a7d1749e107fecc986f15454700fb0b480c8f1e1e3605aa43fc9213a89ef. Decisions retain assay/context limits and rejection risk.',
        'Kotton et al., Transplantation 2024, article CC BY-NC-ND 4.0; reference to facts only, no derivative/source reproduction.'),
    source(SEX, 'L01', 'U.S. Medical Eligibility Criteria for Contraceptive Use',
        'CDC MMWR 2024; DOI 10.15585/mmwr.rr7304a1; supplementary US context',
        'https://www.cdc.gov/mmwr/volumes/73/rr/rr7304a1.htm',
        'https://www.cdc.gov/contraception/hcp/usmec/',
        'CKD nephrotic/dialysis contraceptive safety categories, known hyperkalemia and drospirenone, informed choice.',
        'Official MMWR and appendices read. Main HTML SHA256 b61c19cf0a113052281f7b5227bc102e25b015a82918dc644aacec654443d319; appendix HTML SHA256 e5c2c946a0c40f15d2e92b4dca3989efcec2600ad818b7cbf9d09ce0cb4c1999. Appendix C and D CKD rows checked; not a European product-authorisation rule.',
        'CDC public guidance; US-government work except separately credited material. No table/extract reproduced.'),
    source(TRANSITION, 'G07', 'NICE NG43 transition from children to adult services',
        '2016 final; official 34-page PDF read 2026-10-05',
        'https://www.nice.org.uk/guidance/ng43/chapter/Recommendations',
        'https://www.nice.org.uk/guidance/ng43',
        'Developmental readiness, named coordinator, joint handover and re-engagement; supplementary UK service context.',
        'Official PDF: 1.1.2, 1.2.3-1.2.6, 1.3.1 and 1.4.1-1.4.3. SHA256 1ea6d24335861b75ef50e1fd45641a4b02307ec30e8e3d9875ea54d5aae17d7d. Publication year is retained rather than relabelled a 2026 edition.',
        'NICE copyright/Notice of rights; factual reference only, no licensed connector or source-text redistribution.'),
    source(DYING, 'G07', 'NICE NG31 care of dying adults in the last days of life',
        '2015 final; official 32-page PDF read 2026-10-05, copyright notice 2024',
        'https://www.nice.org.uk/guidance/ng31/chapter/Recommendations',
        'https://www.nice.org.uk/guidance/ng31',
        'Uncertainty/communication, medicine review, routes and anticipatory symptom care; no kidney-specific drug doses.',
        'Official PDF: 1.1.2-1.1.6, 1.2.3-1.2.5, 1.5.1-1.5.5 and 1.6.1-1.6.4. SHA256 da38e12a8d4d200ba213d9abd11927643c223e0b437eca6bf8ecc85a154e521f.',
        'NICE copyright/Notice of rights; factual reference only, no licensed connector or source-text redistribution.'),
    source(CKD, 'K01', 'KDIGO CKD evaluation and management: launch case locators',
        '2024 final; separately read snapshot, no change to inherited K01 sources',
        'https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2024-CKD-Guideline.pdf',
        'https://kdigo.org/guidelines/ckd-evaluation-and-management/',
        'Muscle mass/filtration markers, symptomatic BP tolerance, frailty/nutrition/activity and supportive care.',
        'Official 199-page PDF read: recommendation 1.2.2.1; practice points 3.4.1, 3.3.1.3 and 3.3.1.5; recommendation 3.2.2.1 and practice points 5.5.1-5.5.3. SHA256 0b77a9e32ca6c7bbccbddf902be4427bf8bc0d2dd7e3ffbc18042f602f371b27.',
        'KDIGO/Elsevier rights retained; independently expressed facts, no source excerpts.'),
    source(ANEMIA, 'K02', 'KDIGO anemia in CKD: launch case locators',
        '2026 final; separately read snapshot, no change to inherited K02 source',
        'https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2026-Anemia-in-CKD-Guideline.pdf',
        'https://kdigo.org/guidelines/anemia-in-ckd/',
        'Anemia workup/correctable causes and adult ESA maintenance goal; no dosing protocol.',
        'Official 99-page PDF read: practice points 1.2.1 and 3.1.2, recommendation 3.3.1 and practice point 3.3.1. SHA256 5e72c6f6f5f880e5d842fb8a461585770ba7dac3549da4625745b43f8bc131e1.',
        'KDIGO/Elsevier rights retained; independently expressed facts, no source excerpts.'),
    source(AIN, 'L01', 'A systematic review of treatment for acute interstitial nephritis',
        'Kidney International Reports 2025; DOI 10.1016/j.ekir.2025.05.009; systematic review, not a guideline',
        'https://doi.org/10.1016/j.ekir.2025.05.009',
        'https://pmc.ncbi.nlm.nih.gov/articles/PMC12347843/',
        'Stop a suspected offending exposure, consider alternative causes and discuss limited treatment evidence.',
        'Publisher full text read through Europe PMC PMC12347843: Introduction, Results and Discussion/Conclusion. XML SHA256 f81037a0a19d68d34dccbbeca655f0cf10b72a432802e6be8989f5164d1d3633. Histologically diagnosed studies and heterogeneous steroid regimens do not establish a universal course.',
        'Yu et al., Kidney International Reports 2025, article CC BY-NC-ND 4.0; reference to facts only, no source reproduction.'),
]

ITEM_REVIEW = {**base.REVIEW, 'reviewed_on': DATE,
    'method': 'Scoped primary locator read; assistant source/key, distractor and objective-meaning review of original synthetic content.'}
NEW_QUESTIONS, NEW_CASES, ITEM_EVIDENCE = [], [], []

def q(suffix, topic, objective, source_id, locator, stem, key, wrong, rationale, *, secondary=(), skill='interpretation', claim):
    base.q('RN12-' + suffix, topic, objective, source_id, locator, stem, key, wrong,
           rationale, secondary=secondary, items=NEW_QUESTIONS)
    item = NEW_QUESTIONS[-1]
    item['review'] = dict(ITEM_REVIEW)
    ITEM_EVIDENCE.append({'id': item['id'], 'version': 1, 'kind': 'question',
        'reviewed_on': DATE, 'reviewer_kind': 'assistant', 'independent_human_review': False,
        'source_locators': item['sources'], 'key_text': key, 'skill': skill,
        'checked_claim': claim, 'objective_support': [{'objective_id': item['objective_ids'][0],
            'checked_claim': claim, 'source_locators': item['sources']}],
        'distractor_check': 'All three alternatives were checked against the scope and conditions in the stem; option rationales state why each is inferior.'})

q('UTI-001', 'T17', 2, UTI, 'NG112 1.1.4: specialist evaluation of recurrent UTI',
  'An adult man has three culture-confirmed symptomatic lower UTIs in six months. Each improved with treatment, but no cause has been established. What is the best next preventive-care step?',
  'Seek specialist advice to investigate the recurrence and plan management.',
  [('Start indefinite prophylaxis without investigating the recurrence.', 'The recurrent male-tract presentation warrants specialist evaluation before choosing a long-term strategy.'),
   ('Label the positive cultures colonization because symptoms resolved between episodes.', 'The episodes were symptomatic, and interval recovery does not turn them into asymptomatic bacteriuria.'),
   ('Reserve further evaluation until the first episode of septic shock.', 'Recurrent infection already provides an indication to investigate; severe deterioration is not a required trigger.')],
  'Review episode timing, cultures, resistance, tract symptoms and possible underlying causes. NG112 calls for specialist advice for recurrent UTI in people with a male genitourinary system; prevention should follow that assessment.',
  secondary=('T02','T13'), claim='T17.O02: evidence-based evaluation of recurrent suspected/confirmed infection; specialist advice for recurrent male-tract UTI.')
q('UTI-002', 'T17', 2, UTI, 'NG112 1.2.5-1.2.8: trigger-linked prophylaxis and review',
  'A nonpregnant woman has recurrent culture-confirmed cystitis linked to a recognizable trigger. Acute infection has been treated; behavioral measures and, where appropriate, vaginal estrogen have been insufficient. Which approach fits a trial of single-dose prophylaxis?',
  'Use the identified trigger, previous cultures and preferences to select a trial with planned review.',
  [('Ignore previous susceptibility results because a preventive dose cannot select resistance.', 'Preventive exposure still has adverse-effect and resistance implications.'),
   ('Treat the preventive trial as a replacement for evaluating new acute symptoms.', 'Breakthrough symptoms need clinical assessment rather than automatic extra preventive doses.'),
   ('Continue without a review date if the first month is symptom-free.', 'A trial needs reassessment of benefit, harms and ongoing need.')],
  'Discuss likely benefit, adverse effects and a review within six months. This is a prevention decision after current infection and appropriate earlier steps have been addressed, not an antibiotic dose-selection exercise.',
  secondary=('T19','T24'), skill='common_reasoning', claim='T17.O02: stepwise recurrence prevention with trigger/culture-informed selection and review, within the specified NG112 population.')
q('ALPORT-001', 'T02', 2, ALPORT, 'Alport guideline Q4, recommendation 4.1 and genetic-testing explanation',
  'A 24-year-old has persistent dysmorphic hematuria, high-frequency hearing loss and a parent with unexplained kidney failure. Ultrasound shows no cysts. Which investigation addresses the suspected inherited glomerular disorder?',
  'Discuss appropriately counselled testing that includes COL4A3, COL4A4 and COL4A5.',
  [('Limit genetic testing to PKD1 and PKD2 because all familial kidney disease is cystic.', 'This phenotype supports an inherited basement-membrane disorder, not an ADPKD-only panel.'),
   ('Exclude inherited disease because kidney ultrasound is normal.', 'A collagen-IV disorder need not produce renal cysts.'),
   ('Use hearing loss alone as molecular confirmation of Alport syndrome.', 'The extra-renal finding supports the differential but is not a genetic result.')],
  'Combine the urinary phenotype, family history and hearing findings. The 2024 guideline supports Alport gene testing in this setting and analysis of all three relevant collagen-IV genes, with counselling and explanation of test limitations.',
  secondary=('T12','T24'), claim='T02.O02: choose a confirmatory genetic test and distinguish a suggestive phenotype from molecular confirmation; no ADPKD objective is claimed.')
q('ALPORT-002', 'T02', 1, ALPORT, 'Alport guideline Q8 and Q19.2: heterozygous COL4A3/4 variants, contextual diagnosis and unexpected nephrotic syndrome',
  'A patient with a heterozygous pathogenic COL4A3 variant develops unexpectedly abrupt nephrotic-range proteinuria. Which interpretation best integrates the genotype and new clinical course?',
  'Assess the phenotype, family segregation and possible additional kidney disease rather than attributing every new finding to the variant.',
  [('The pathogenic label establishes that every subsequent kidney abnormality has one cause.', 'A molecular finding does not exclude a coexisting lesion or explain every change in tempo.'),
   ('A heterozygous COL4A3 variant cannot have any renal significance.', 'Heterozygous collagen-IV variants can be clinically relevant, with variable expression.'),
   ('A normal examination of one relative disproves a variably expressed inherited condition.', 'Family evaluation must account for penetrance and phenotype rather than a single observation.')],
  'The guideline cautions against treating common heterozygous COL4A3/4 findings as a sufficient explanation for every phenotype. A discrepant course merits clinical reassessment and, when it would change decisions, discussion of additional investigations.',
  secondary=('T12','T10','T22'), skill='common_reasoning', claim='T02.O01: combine chronology and urinary phenotype with genotype; do not replace diagnostic reasoning with an inherited label.')
q('PD-001', 'T17', 2, PD, 'ISPD 2022: Identification and initial management, diagnostic criteria',
  'A PD patient has abdominal pain and cloudy effluent. After a three-hour dwell, effluent contains 240 leukocytes/microliter with 70% neutrophils. Culture is pending. Which interpretation is best?',
  'Clinical and effluent-cell criteria already support PD peritonitis; obtain microbiology and arrange prompt treatment without waiting for a positive culture.',
  [('Peritonitis cannot be considered until culture is positive.', 'Two of the three diagnostic components are already present; culture-negative episodes can occur.'),
   ('The cell count excludes peritonitis because it is below 1000/microliter.', 'The guideline threshold after a sufficient dwell is above 100/microliter, with over 50% neutrophils.'),
   ('Cloudiness alone proves that a specific organism is responsible.', 'Clinical appearance does not establish microbiologic identity.')],
  'ISPD uses at least two of compatible symptoms/cloudy effluent, the specified effluent-cell pattern after at least two hours, and positive culture. Send appropriate effluent specimens and act promptly; the key does not prescribe an antibiotic regimen.',
  secondary=('T20','T02'), claim='T17.O02: interpret infection findings and culture limits; 2022 diagnostic criteria, not corrected dosing or refractory-treatment algorithms.')
q('PD-002', 'T22', 2, PD_ACCESS, 'ISPD 2023: Definition and diagnosis of catheter-related infection',
  'At a PD catheter exit site there is purulent discharge with mild surrounding erythema. The patient is afebrile. What is the most appropriate interpretation and assessment priority?',
  'This meets the definition of exit-site infection; assess the tunnel and obtain appropriate microbiology.',
  [('It is only colonization because there is no fever.', 'Fever is not required for a local catheter infection.'),
   ('Redness and purulent discharge are equally nonspecific findings.', 'Erythema alone is not definitive, whereas purulent discharge is a defining feature.'),
   ('A normal-looking external segment excludes tunnel involvement.', 'Tunnel inflammation requires its own assessment; surface appearance is not a complete test.')],
  'Purulent discharge, with or without erythema, supports exit-site infection. Examine for tunnel tenderness, swelling or inflammation and consider ultrasound for suspected tunnel disease. Treatment needs organism, severity and local-protocol review.',
  secondary=('T17','T20'), claim='T22.O02: identify catheter infection/access risk and plan the next assessment without mistaking absence of fever for safety.')
q('HD-001', 'T22', 2, HD, 'UKKA vascular access guidelines 4.6-4.7 and aneurysm rationale',
  'An HD fistula aneurysm develops a scab over thin skin and the patient reports prolonged bleeding after dialysis. Which plan best addresses the access risk?',
  'Arrange prompt access-team review, avoid cannulating the compromised skin and plan safe dialysis access.',
  [('Use the scabbed segment because it is the easiest site to palpate.', 'Atrophic or eroded skin is vulnerable and should not be cannulated.'),
   ('Monitor diameter alone and ignore the bleeding history.', 'Skin erosion and prolonged bleeding are clinically important risk features.'),
   ('Reassure the patient that aneurysms cannot bleed if a thrill is present.', 'A patent fistula can still have dangerous bleeding-risk features.')],
  'Assess skin integrity, interval growth and bleeding, as well as access function. The access team balances severity, treatability, future access options and the patient’s priorities; a scab is not a reassuring cover over vulnerable skin.',
  secondary=('T20',), claim='T22.O02: bleeding-risk access assessment and planning; high-risk skin and bleeding features support referral and safe cannulation planning.')
q('HD-002', 'T20', 2, HD, 'UKKA vascular access guideline 3.12: assessment before every cannulation',
  'An established HD fistula worked normally two days ago. Before today’s needles are inserted, which unit practice is still required?',
  'An appropriately trained cannulator assesses the access by inspection, palpation and auscultation.',
  [('Prior successful dialysis replaces today’s access assessment.', 'Access function, skin and complications can change between sessions.'),
   ('Only the annual vascular review should assess access health.', 'Every-session assessment supports safe ongoing cannulation.'),
   ('The machine’s prior pressure readings establish that today’s access is normal.', 'Previous circuit readings do not replace present clinical assessment.')],
  'The guideline recommends an access assessment before each cannulation. It helps identify a new problem and plan safe use; the recommendation does not prove that one examination detects every lesion.',
  secondary=('T22',), skill='common_reasoning', claim='T20.O02: ongoing dialysis-unit care includes trained access assessment at each cannulation, not a pre-dialysis planning tag.')
q('HD-003', 'T20', 2, HD, 'UKKA vascular access guideline 4.2: stenosis with clinical dysfunction',
  'Repeated difficult cannulation and inadequate achievable blood flow prompt assessment. Imaging confirms a significant fistula stenosis corresponding to these problems. What best fits access management?',
  'Discuss intervention for significant stenosis with clinical access dysfunction and the patient’s access plan.',
  [('Every imaging stenosis must be treated even if it has no clinical consequence.', 'The recommendation couples radiologic significance with clinical dysfunction.'),
   ('A visible stenosis can never explain low dialysis blood flow.', 'A corresponding lesion can impair access function and delivery.'),
   ('Abandon all future fistula options without discussing alternatives.', 'Treatment and access choices require context and shared planning.')],
  'Clinical findings drive the investigation and interpretation. A treatable lesion, alternative accesses, prognosis and preferences shape the intervention; a radiology label alone is not the whole decision.',
  secondary=('T22',), claim='T20.O02: ongoing HD delivery/access problems support investigation and intervention when a corresponding significant lesion is present.')
q('HD-004', 'T20', 2, HD, 'UKKA vascular access guidelines 5.4-5.5: catheter care and aseptic access',
  'A tunnelled HD catheter needs connection for treatment. Which arrangement best meets the guideline’s unit-care requirement?',
  'Use trained dialysis staff, or a trained/supervised patient or carer, with a strict aseptic approach.',
  [('Anyone familiar with ordinary intravenous lines can connect it without dialysis training.', 'Tunnelled dialysis access has specific competence and safety requirements.'),
   ('A catheter dressing makes aseptic connection technique unnecessary.', 'A covered exit site does not protect an opened hub from contamination.'),
   ('Home dialysis requires the patient to connect without training or supervision.', 'Appropriate patient/carer training or supervision is part of the recommendation.')],
  'Competence and asepsis are operational requirements for ongoing catheter use. The option includes supported home care; it does not imply that a patient must manage the access alone.',
  secondary=('T17','T22'), skill='common_reasoning', claim='T20.O02: safe ongoing HD unit/home catheter care, with trained access and asepsis; not a claim of procedural competence from answering an item.')
q('BK-001', 'T17', 2, BK, 'BK consensus Tables 5 and 7: sustained DNAemia and immunosuppression reduction',
  'Four months after kidney transplantation, plasma BK DNA is 3200 and 4600 copies/mL in samples two weeks apart from the same laboratory. Creatinine is stable. What is the best next response?',
  'Arrange transplant-team review for persistent DNAemia, immunosuppression reduction and serial monitoring in the patient’s immunologic context.',
  [('Ignore both results until creatinine rises.', 'Persistent DNAemia can warrant action before overt graft dysfunction.'),
   ('Automatically give high-dose steroids for presumed rejection.', 'The findings do not establish rejection and increased immunosuppression can worsen viral replication.'),
   ('Treat the positive plasma tests as proof of biopsy-confirmed BK nephropathy.', 'DNAemia and tissue-confirmed nephropathy are distinct diagnostic states.')],
  'The consensus suggests reduction when 1000-10,000 copies/mL is confirmed on two measurements within two to three weeks. Review the assay, immunologic risk, drug exposure and follow-up with the transplant team; the key is not a patient-specific reduction schedule.',
  secondary=('T21','T19','T02'), claim='T17.O02: recipient infection surveillance and interpretation of persistent plasma BK DNAemia; this is not candidate-prevention coverage.')
q('BK-002', 'T19', 1, BK, 'BK consensus Tables 6-7 and management rationale: competing rejection risk',
  'Immunosuppression has been reduced for persistent BK DNAemia. The viral load falls, but serum creatinine rises. Which reasoning is most appropriate?',
  'Reassess viral, rejection, medication and other graft causes with the transplant team; a falling viral load alone does not explain the dysfunction.',
  [('A falling BK result excludes rejection after immunosuppression reduction.', 'Reduced exposure can increase rejection risk; the viral trend is not a rejection test.'),
   ('The creatinine rise proves that immunosuppression should be stopped completely.', 'It does not establish a cause or justify an unreviewed complete withdrawal.'),
   ('Serial viral tests can replace every clinical or tissue assessment of graft dysfunction.', 'Virology is one component of the assessment and has assay/context limits.')],
  'Balance viral control against rejection risk and review drug concentrations and the clinical course. Additional investigation, including biopsy when indicated, may be needed; neither biomarker alone determines the entire regimen.',
  secondary=('T21','T02','T27'), skill='common_reasoning', claim='T19.O01: medication benefit/risk tradeoffs after transplant, with the diagnostic uncertainty and rejection risk of reducing immunosuppression.')
q('SEX-001', 'T24', 2, SEX, 'US MEC 2024 Appendix D: CKD receiving hemodialysis, combined hormonal contraception',
  'An adult receiving HD asks about starting an estrogen-containing combined contraceptive pill. Using the 2024 U.S. MEC as supplementary safety evidence, which advice is correct?',
  'HD is a category-4 condition for combined hormonal contraception; discuss suitable alternatives and the person’s priorities.',
  [('Dialysis removes the estrogen-related risk, so the method is unrestricted.', 'HD does not neutralize the safety concerns in this category.'),
   ('This classification means the person cannot use any contraception.', 'The classification is method-specific; other options need individual evaluation.'),
   ('The category is a prediction that infertility makes contraception unnecessary.', 'Medical eligibility and the possibility of conception are different questions.')],
  'Category 4 denotes an unacceptable health risk for that method in that condition. Discuss alternatives without coercion, considering bleeding, other conditions and medicines. This U.S. source does not replace European product information or local reproductive-care advice.',
  secondary=('T19','T20'), claim='T24.O02: dialysis-specific reproductive treatment tradeoffs; the scope is contraception, not a complete fertility/sexual-dysfunction curriculum.')
q('SEX-002', 'T19', 1, SEX, 'US MEC 2024 Appendix C: CKD, drospirenone POP and known hyperkalemia',
  'A patient with CKD and known persistent hyperkalemia wants a drospirenone-only contraceptive pill. Which medication-safety distinction is supported by the 2024 U.S. MEC?',
  'Known hyperkalemia makes drospirenone POP use category 4; assess a suitable alternative rather than treating all progestin-only pills as identical.',
  [('All progestin-only pills have identical potassium effects and eligibility.', 'The guidance gives a specific hyperkalemia restriction for drospirenone.'),
   ('Potassium monitoring makes known hyperkalemia an unrestricted indication.', 'First-cycle monitoring advice for CKD without known hyperkalemia does not remove this restriction.'),
   ('The restriction applies only to an estrogen-containing formulation.', 'The specified drug/condition interaction also concerns the drospirenone-only pill.')],
  'Check the exact preparation, potassium status and interacting medicines. The drospirenone-specific restriction is distinct from broad assumptions about a contraceptive class, and alternatives need individual review.',
  secondary=('T24',), claim='T19.O01: a kidney-related drug/condition risk; distinguish known hyperkalemia from the different monitoring advice for CKD without known hyperkalemia.')
q('TRANS-001', 'T24', 2, TRANSITION, 'NG43 1.1.2 and 1.2.3: developmental readiness and timing',
  'A 17-year-old kidney transplant recipient is approaching transfer to adult services. They understand their diagnosis but still need help organizing medication and appointments. What should guide the handover?',
  'Plan with the young person and both services around development, readiness and support needs, rather than age alone.',
  [('Transfer automatically on a birthday regardless of readiness or active concerns.', 'An age-only rule does not address developmental and practical needs.'),
   ('Postpone all preparation until the person can manage without any support.', 'Preparation and supported skill-building are part of transition, not rewards for already being independent.'),
   ('Let the child service end contact before the adult team meets the young person.', 'A coordinated handover helps prevent a gap in care.')],
  'NG43 recommends developmentally appropriate, coordinated transition. Prepare practical self-management with the young person and agree timing in context; a checklist score or birthday alone does not establish safe transfer.',
  secondary=('T21','T27'), skill='common_reasoning', claim='T24.O02: a supported transition decision with developmental context; no inference that transplant-candidate items cover this facet.')
q('TRANS-002', 'T27', 2, TRANSITION, 'NG43 1.2.5-1.2.6 and 1.4.1-1.4.3: named worker and re-engagement',
  'After transfer, a young transplant recipient misses the first adult clinic and reports confusion about prescription renewal. Which response best protects continuity?',
  'Use the agreed coordinator to contact the young person, identify barriers and reconnect the child/adult teams and medication plan.',
  [('Discharge for nonattendance without exploring the missed handover.', 'The guidance calls for active re-engagement rather than assuming the person chose to abandon care.'),
   ('Ask the family to manage indefinitely without involving the young person.', 'Support should build participation and respect the young person’s preferences.'),
   ('Create a second uncoordinated prescription plan in another service.', 'Competing plans can worsen the continuity problem.')],
  'A named worker and a shared plan clarify responsibility. Ask about transport, communication, understanding and prescription access, agree the next contact and involve supporters with the young person’s agreement.',
  secondary=('T24','T21'), claim='T27.O02: specify the continuity uncertainty and coordinate the relevant services; nonattendance needs re-engagement, not an arbitrary nonadherence label.')
q('DYING-001', 'T26', 1, DYING, 'NG31 1.1.2-1.1.6 and 1.2.3-1.2.5: uncertainty and communication',
  'A patient with kidney failure has chosen to stop maintenance dialysis after a shared goals discussion. They are increasingly drowsy and may be entering the last days of life. What is the best communication approach?',
  'Explain the clinical assessment and its uncertainty, revisit preferences and plan continuing supportive care with those the patient wants involved.',
  [('State an exact time of death because dialysis has stopped.', 'The decision and current signs do not permit that precision.'),
   ('Avoid further review because a withdrawal decision ends care.', 'Support, symptom assessment and reassessment continue.'),
   ('Assume the family’s preferred treatment automatically overrides the patient’s expressed goals.', 'Communication and decisions need the patient’s wishes and capacity context.')],
  'Recognizing possible dying includes looking for deterioration, stabilization or temporary recovery. Communicate uncertainty honestly, confirm desired involvement and keep a practical supportive-care plan; do not equate withdrawal with abandonment.',
  secondary=('T20','T27'), skill='common_reasoning', claim='T26.O01: goals-based advance/supportive care in an actual withdrawal and possible dying context, rather than merely a conservative-care definition.')
q('DYING-002', 'T19', 1, DYING, 'NG31 1.5.1-1.5.5 and 1.6.1-1.6.4: medication and anticipatory care',
  'A dying patient with kidney failure can no longer swallow reliably. Which medication plan best fits individualized last-days care?',
  'Review benefit and harm of current medicines, choose feasible routes and individualized anticipatory symptom treatment with renal/pharmacy input.',
  [('Continue every preventive medicine orally regardless of swallowing or expected benefit.', 'Route, burden and expected symptom benefit require review.'),
   ('Give one fixed anticipatory drug package to everyone without considering symptoms or kidney failure.', 'Anticipatory prescribing is individualized and medicine harms differ.'),
   ('Stop all medicines including helpful symptom relief because dialysis has been withdrawn.', 'Symptom care continues, with appropriate route and risk review.')],
  'Review likely symptoms, prior effective treatments, interactions, organ function and administration routes. Agree a plan that can be used when needed and reviewed; this item deliberately does not prescribe a kidney-specific opioid or sedative dose.',
  secondary=('T26','T27'), claim='T19.O01: benefits, harms and feasibility of medicines in kidney failure/last days; no unverified renal-specific dosing claim.')

def stage(narrative, prompts, points, *citations):
    return {'narrative': narrative, 'prompts': prompts, 'teaching_points': points,
            'sources': [base.cite(sid, locator) for sid, locator in citations]}

def case(suffix, topic, secondary, title, summary, stages, take_home, support):
    objectives = [o for o, _, _ in support]
    base.case('RN12-CASE-' + suffix, topic, list(secondary), objectives, title,
              summary, stages, take_home, items=NEW_CASES)
    item = NEW_CASES[-1]
    item['review'] = dict(ITEM_REVIEW)
    rows = []
    for objective, numbers, claim in support:
        locators = []
        for number in numbers:
            for citation in item['stages'][number - 1]['sources']:
                if citation not in locators:
                    locators.append(citation)
        rows.append({'objective_id': objective, 'stage_ids': ['stage-' + str(n) for n in numbers],
                     'checked_claim': claim, 'source_locators': locators})
    ITEM_EVIDENCE.append({'id': item['id'], 'version': 1, 'kind': 'case',
        'reviewed_on': DATE, 'reviewer_kind': 'assistant', 'independent_human_review': False,
        'source_locators': item['sources'], 'key_text': None, 'skill': 'mixed_domain_reasoning',
        'checked_claim': ' '.join(r['checked_claim'] for r in rows),
        'objective_support': rows,
        'review_limit': 'Synthetic open teaching discussion; prompts and cited teaching points are reviewed, no deterministic case key or clinical outcome is invented.'})

case('UTI', 'T17', ('T02','T13','T19','T24'),
  'Recurrent lower UTI: establish the pattern before prevention',
  'A postmenopausal adult with recurrent symptomatic cystitis weighs preventive choices after treatment of the current episode.',
  [stage('A 62-year-old has four episodes of dysuria and frequency in eight months, with positive cultures during symptoms. She is well between episodes and currently has no fever, flank pain or pregnancy possibility. The current episode has been treated.',
      ['Which chronology and microbiology distinguish recurrence from a persistent untreated episode?', 'Which new systemic or tract features would change the evaluation?'],
      ['Review episode dates, symptoms, culture/susceptibility results and response rather than treating a positive result without context.', 'Recurrent upper infection or recurrent lower infection with an unknown underlying cause warrants specialist advice; do not assume every recurrence is uncomplicated.'],
      (UTI, 'NG112 1.1.4 and 1.2.6: recurrence evaluation, underlying cause and prior cultures')),
   stage('She reports vaginal dryness and has already tried reasonable behavioral measures. She asks whether a preventive option must be a daily antibiotic.',
      ['How do symptom context and preferences influence the next preventive discussion?', 'What distinction should be made between vaginal and systemic estrogen?'],
      ['Where appropriate, discuss vaginal estrogen after insufficient or unsuitable behavioral measures, including preferences, local symptoms and potential harms.', 'Systemic hormone replacement therapy is not prescribed specifically to prevent recurrent UTI; a local preventive discussion is different.'],
      (UTI, 'NG112 1.2.1-1.2.4: vaginal estrogen and limits of systemic HRT')),
   stage('Despite agreed earlier measures, culture-confirmed episodes remain associated with a recognizable trigger. She prefers a limited preventive trial.',
      ['What must be reviewed before selecting a trigger-linked trial?', 'How will benefit, harm and breakthrough symptoms be reassessed?'],
      ['Confirm current infection is treated and consider prior susceptibility, frequency/severity, adverse effects and preferences before a single-dose trial.', 'Agree a review within six months and a plan to seek help for acute symptoms; a preventive trial is not indefinite treatment or an acute-infection substitute.'],
      (UTI, 'NG112 1.2.5-1.2.8: single-dose prophylaxis conditions and review'))],
  ['Classify the symptomatic recurrence before prevention.', 'Choose and review prevention in the actual patient context.'],
  [('T02.O01',[1],'Chronology, urine cultures, response and tract/systemic features frame the problem.'),
   ('T17.O02',[1,2,3],'Evidence-based evaluation and stepwise prevention of recurrent infection with reviewed follow-up.')])

case('ALPORT', 'T02', ('T12','T24','T10','T22'),
  'Familial hematuria beyond a cystic-disease label',
  'Persistent glomerular hematuria, hearing findings and family history guide a collagen-IV investigation.',
  [stage('A 23-year-old has persistent dysmorphic hematuria, mild albuminuria and high-frequency hearing loss. A parent developed kidney failure of uncertain cause. Ultrasound shows no cysts.',
      ['How does the combination change the inherited differential?', 'What can a normal cyst assessment establish here?'],
      ['Combine urine phenotype, hearing findings and pedigree; absence of cysts does not exclude an inherited glomerular disorder.', 'An Alport-spectrum evaluation is supported by this pattern. The topic label for inherited disease is not an ADPKD-specific objective link.'],
      (ALPORT, 'Q4, recommendation 4.1: clinical indications for Alport testing')),
   stage('The patient asks for a definitive blood test and wants to know whether siblings should be tested immediately.',
      ['Which genes and limitations should the test discussion include?', 'How will counselling and family evaluation support interpretation?'],
      ['Discuss comprehensive COL4A3/4/5 testing and its technical and interpretive limits; not every negative test excludes disease.', 'Use informed genetic counselling and appropriate family/segregation assessment. Avoid equating any reported variant with a confirmed causal result.'],
      (ALPORT, 'Q4 recommendation 4.1 and explanation; Q9: initial testing and test-sensitivity limits')),
   stage('A heterozygous pathogenic COL4A3 result is identified. Later, abrupt nephrotic-range proteinuria appears, unlike the earlier slow course.',
      ['Does the genotype explain every new finding?', 'Which uncertainty now needs clinical or tissue reassessment?'],
      ['Interpret genotype with clinical expression and family segregation. A discrepant new course can indicate an additional kidney disorder.', 'Discuss additional investigations, including biopsy when it would change decisions; the molecular result does not freeze the differential.'],
      (ALPORT, 'Q8; Q16.2; Q19.2: contextual diagnosis and biopsy considerations in heterozygous COL4A3/4 disease'))],
  ['Inherited hematuria is broader than ADPKD.', 'A genetic finding needs phenotype and uncertainty-aware interpretation.'],
  [('T02.O01',[1,3],'Clinical tempo, urine phenotype and family findings frame an inherited diagnostic problem and a later discrepant course.'),
   ('T02.O02',[2,3],'Choose appropriately counselled confirmatory testing and explain its technical/causal limits; no ADPKD objective is claimed.')])

case('PD-INFECTION', 'T20', ('T17','T22','T02'),
  'Cloudy PD effluent and a catheter-exit problem',
  'A continuing PD patient needs prompt peritonitis evaluation and a separate catheter-infection assessment.',
  [stage('A PD patient develops abdominal pain and cloudy effluent. After a three-hour dwell, the count is 260 leukocytes/microliter with 75% neutrophils. Culture is not yet available.',
      ['Which diagnostic components are already present?', 'What should happen while culture is pending?'],
      ['Clinical and effluent-cell criteria support peritonitis; culture is one of three components, not a prerequisite for acting.', 'Arrange prompt PD-team assessment, appropriate effluent cell/differential and culture sampling, and timely empiric management under the local protocol.'],
      (PD, 'Identification and initial management: diagnostic criteria, specimen collection and prompt treatment')),
   stage('Inspection also reveals purulent exit-site discharge. There is tenderness along the catheter tunnel, while the external segment otherwise appears intact.',
      ['How do purulence and redness alone differ?', 'What additional access assessment is needed?'],
      ['Purulent discharge supports exit-site infection even without fever. Redness alone is not a definitive equivalent.', 'Assess tunnel inflammation separately, obtain appropriate microbiology and consider ultrasound for suspected tunnel disease.'],
      (PD_ACCESS, 'Definition and diagnosis of catheter-related infection: exit-site and tunnel criteria')),
   stage('Microbiology becomes available. The team must review clinical response, exit/tunnel findings and continuing PD access.',
      ['Which findings and patient priorities belong in the follow-up plan?', 'Why should a standard peritonitis response not erase the access problem?'],
      ['Integrate organism, susceptibility and response with the catheter infection assessment; the related complications need coordinated follow-up.', 'Continuing PD and any catheter intervention require specialist planning. This discussion does not supply a drug-dose table or refractory-peritonitis day/count algorithm.'],
      (PD, 'Subsequent management: organism and response review'),
      (PD_ACCESS, 'Treatment and surgical interventions: catheter-related infection assessment'))],
  ['Do not wait for culture before responding to a compatible PD peritonitis presentation.', 'Assess catheter exit and tunnel complications explicitly.'],
  [('T17.O02',[1,2,3],'Interpret peritonitis/infection evidence and culture limits with prompt evaluation.'),
   ('T22.O02',[2,3],'Assess catheter infection and access-intervention risks rather than using a dialysis tag alone.'),
   ('T20.O02',[1,3],'Coordinate ongoing PD care, access and follow-up with modality preferences; no complete prescription pathway is claimed.')])

case('HD-ACCESS', 'T20', ('T22',),
  'An aneurysmal fistula with new bleeding-risk features',
  'An established HD patient needs safe ongoing dialysis and a reviewed access plan.',
  [stage('At a routine HD session, an aneurysmal fistula has thin shiny skin and a small scab. The patient describes longer bleeding after the last two treatments.',
      ['Which changes are clinically concerning?', 'Can the easiest needle site still be used without reconsideration?'],
      ['Assess skin erosion, recent growth, spontaneous or prolonged bleeding and access function; a scab is a risk finding, not reassurance.', 'Avoid cannulating compromised skin and arrange prompt access-team review with a safe dialysis plan.'],
      (HD, 'Guidelines 4.6-4.7 and aneurysm rationale: bleeding risk and atrophic skin')),
   stage('Clinical assessment and targeted imaging identify an outflow lesion associated with the access problems. The patient is worried that every intervention means losing the fistula.',
      ['How should clinical findings and imaging be interpreted together?', 'What choices and uncertainties should be explained?'],
      ['A radiologically significant stenosis with clinical dysfunction supports intervention discussion; imaging alone is not the entire indication.', 'Explain treatability, alternatives and risks with the access team rather than assuming a single inevitable outcome.'],
      (HD, 'Guidelines 4.1-4.2 and 4.6-4.7: shared decisions, symptomatic stenosis and aneurysm treatment')),
   stage('The team proposes an access treatment plan and a way to maintain dialysis while vulnerable sites are avoided. The patient wants clear instructions for the next session.',
      ['Who needs the updated cannulation/access instructions?', 'How will preferences and an unexpected bleed be handled?'],
      ['Document safe access use and communicate the plan to the dialysis team and patient. New bleeding or deterioration needs urgent reassessment.', 'Balance immediate safety, access preservation, alternative access and the patient’s priorities; answering this case does not establish procedural competence.'],
      (HD, 'Guidelines 3.12 and 4.1; aneurysm bleeding-risk rationale'))],
  ['Review new skin and bleeding changes before cannulation.', 'Access planning must keep ongoing HD and future options in view.'],
  [('T20.O02',[1,2,3],'A focused ongoing-HD access case includes session safety, continuing delivery and patient preferences.'),
   ('T22.O02',[1,2,3],'Bleeding/access-complication assessment supports intervention planning and safe cannulation decisions.')])

case('HD-SESSION', 'T20', ('T17','T22','T27'),
  'A catheter problem during continuing hemodialysis',
  'A focused HD session case connects operational access checks, infection evaluation and the next treatment plan.',
  [stage('A patient on regular HD has a tunnelled catheter and increasingly poor achievable blood flow. Staff review catheter/access findings and the effect on delivering today’s treatment.',
      ['Why is this an ongoing dialysis-care problem?', 'What should be checked before assuming a new prescription alone solves it?'],
      ['Assess access function and the clinical context when blood flow is inadequate; a prescription on paper does not establish delivered treatment.', 'Connection and manipulation require trained dialysis staff or appropriately trained/supervised patient/carer involvement and strict asepsis.'],
      (HD, 'Guidelines 5.4-5.5; chapter 6 catheter dysfunction rationale')),
   stage('During reassessment the patient develops fever and rigors. The exit site looks normal, and staff wonder whether that excludes a catheter-related bloodstream infection.',
      ['What can the normal exit site establish?', 'Which specimens and immediate clinical assessment are needed?'],
      ['A catheter-related bloodstream infection can occur with a normal exit and tunnel appearance; assess systemic severity promptly.', 'Obtain appropriate blood cultures before antimicrobial treatment where feasible without unsafe delay, and coordinate prompt specialist/local-protocol management.'],
      (HD, 'Catheter-related infection rationale: bloodstream infection, cultures and prompt treatment')),
   stage('The team reviews microbiology and response and discusses catheter management and the next HD treatment with the patient.',
      ['What factors determine the access plan?', 'How will today’s problem be carried into the next session?'],
      ['Severity, organism, response, local access options and the need to continue dialysis shape catheter management; no universal retention or removal rule is taught here.', 'Communicate the reviewed plan, monitoring and next-treatment arrangements to the patient and dialysis team, with aseptic-access instructions.'],
      (HD, 'Chapter 6 catheter-related infection rationale and guideline 5.4'))],
  ['A focused HD case concerns what happens during and after actual ongoing treatments.', 'Normal external catheter appearance does not exclude bloodstream infection.'],
  [('T20.O02',[1,3],'Ongoing HD delivery, operational catheter care and a communicated next-session access plan.'),
   ('T17.O02',[2,3],'Evaluate suspected catheter infection using systemic findings and appropriate microbiology.'),
   ('T22.O02',[1,2,3],'Review access dysfunction/infection and the risks shaping catheter management.')])

case('BK-AFTERCARE', 'T21', ('T17','T19','T02','T27'),
  'BK surveillance after transplantation: viral control and graft risk',
  'A recipient’s serial plasma results guide aftercare while rejection and other causes remain in the differential.',
  [stage('Four months after transplantation, protocol surveillance finds plasma BK DNA at 3200 copies/mL and 4600 copies/mL two weeks later using the same assay. Creatinine is unchanged.',
      ['Why do the serial results matter even with stable creatinine?', 'Is this already biopsy-proven nephropathy?'],
      ['Persistent plasma DNAemia is actionable surveillance evidence; it need not wait for overt dysfunction.', 'Distinguish plasma viral load from tissue-confirmed disease and retain assay/context limits. Adult surveillance is recommended monthly to month nine, then every three months to two years.'],
      (BK, 'Tables 5 and 7; diagnostics: surveillance and persistent DNAemia')),
   stage('The transplant team reviews adherence, drug exposure and immunologic risk, and plans a stepwise reduction with serial testing.',
      ['Which medication benefit and harm are in tension?', 'Why is a coordinated plan needed rather than an unsupervised stop?'],
      ['Reduce excessive immunosuppressive pressure in context while monitoring viral control and rejection risk.', 'Review concentrations and the regimen with the transplant team; the case does not prescribe a universal patient-specific reduction schedule.'],
      (BK, 'Tables 6-7: practice guidance and management recommendations')),
   stage('The BK load falls, but creatinine rises. The recipient asks whether the improved viral result proves the kidney is recovering.',
      ['Which alternative causes and investigations need review?', 'What uncertainty should the shared plan record?'],
      ['A viral trend alone does not explain new dysfunction. Reassess rejection, medication effects, ongoing viral disease and other graft causes.', 'Coordinate additional clinical and, when indicated, biopsy assessment with the transplant team. Record uncertainty and follow-up rather than declaring either rejection or viral recovery from one marker.'],
      (BK, 'Diagnostics and management rationale; Tables 6-7: graft dysfunction and rejection risk'))],
  ['Recipient aftercare is distinct from transplant-candidate evaluation.', 'Balance viral control, medication exposure and graft/rejection risk.'],
  [('T02.O01',[1,3],'Serial viral results and graft-function chronology frame a recipient diagnostic problem.'),
   ('T17.O02',[1,3],'Evidence-based recipient infection surveillance and evaluation, not pre-transplant candidate prevention.'),
   ('T19.O01',[2,3],'Medication benefits/risks and exposure review when treating BK replication.'),
   ('T27.O02',[2,3],'Coordinate recipient care with the transplant team and explicitly retain graft-cause uncertainty.')])

case('SEXUAL-HEALTH', 'T24', ('T19','T20','T27'),
  'A private contraception discussion in kidney failure',
  'A patient on HD discusses contraception, potassium-related drug risk and future reproductive preferences.',
  [stage('A 31-year-old receiving HD asks privately about reliable contraception. She is considering an estrogen-containing combined pill and does not want pregnancy now.',
      ['How can the discussion respect her priorities?', 'Which kidney-failure-specific method risk needs explanation?'],
      ['Offer informed, noncoercive discussion of efficacy, burdens and risks rather than assuming dialysis makes conception impossible or removes reproductive preferences.', 'The 2024 U.S. MEC places combined hormonal contraception in category 4 for HD. Use this as supplementary safety evidence with European product/local reproductive-care review.'],
      (SEX, 'Using US MEC categories; Appendix D, CKD/hemodialysis row')),
   stage('She asks whether a drospirenone-only pill avoids every concern. Her kidney team confirms known persistent hyperkalemia.',
      ['Why must the exact preparation and condition be checked?', 'Does advice about potassium monitoring remove this restriction?'],
      ['Known hyperkalemia is a specific category-4 restriction for drospirenone POPs; not every progestin-only method has the same risk.', 'The separate advice to consider first-cycle potassium measurement in CKD without known hyperkalemia does not make this presentation eligible.'],
      (SEX, 'Appendix C, CKD and drospirenone POP clarification')),
   stage('She prefers to compare other options and asks how a future pregnancy plan would fit her kidney care.',
      ['What belongs in a shared reproductive-care plan?', 'Which questions require another clinician or current product information?'],
      ['Compare appropriate alternatives in the setting of kidney failure, bleeding preferences, other conditions and medicines; do not select a method by class label alone.', 'Arrange reproductive/kidney-team advice for pregnancy planning and medication review. This case covers a contraception decision, not full fertility or sexual-dysfunction assessment.'],
      (SEX, 'Person-centered contraceptive counselling and medical eligibility categories'))],
  ['Sexual/reproductive health belongs in kidney care with privacy and informed choice.', 'Check method-specific kidney/drug risks and coordinate unanswered questions.'],
  [('T24.O02',[1,3],'Kidney-failure-specific reproductive treatment tradeoffs with informed choice.'),
   ('T19.O01',[2,3],'Review exact contraceptive preparation, known potassium risk and interacting conditions/medicines.'),
   ('T27.O02',[3],'Coordinate reproductive and kidney-care questions rather than inventing a comprehensive fertility plan.')])

case('TRANSITION', 'T24', ('T21','T27','T19'),
  'Supported transfer to adult transplant care',
  'A young recipient and both teams build practical continuity rather than relying on a birthday or an adherence label.',
  [stage('A 17-year-old recipient can explain why medication matters but relies on a parent for prescriptions and transport. Adult-clinic transfer is approaching during an unsettled school period.',
      ['Which developmental and practical needs matter?', 'How should the young person participate in timing and preparation?'],
      ['Assess readiness, understanding, support and preferences, not age alone; preparation can begin while practical skills are still developing.', 'Build developmentally appropriate participation and agree timing with both services and the young person.'],
      (TRANSITION, 'NG43 1.1.2 and 1.2.3: developmental support and transfer timing')),
   stage('A named worker coordinates a joint contact with the adult team. The young person identifies uncertainty about prescription renewal and whom to call for a missed dose.',
      ['How will responsibility and contact routes be made clear?', 'What should be practiced before transfer?'],
      ['Use a named coordinator, a shared plan and adult-team contact before transfer.', 'Clarify prescription access, contact routes and practical self-management with agreed support; the case does not supply a transplant drug-dose rescue rule.'],
      (TRANSITION, 'NG43 1.2.5-1.2.6 and 1.3.1: named worker and meeting the adult service')),
   stage('The first adult appointment is missed. The young person reports that messages went to an old phone number and the prescription route is still unclear.',
      ['How should the services re-engage?', 'Which uncertainty and next contact should be recorded?'],
      ['Contact the young person and explore barriers rather than discharging or labelling the event without inquiry.', 'Reconnect the agreed coordinator, adult service and necessary child-service support, update contacts and review medication continuity with the relevant team.'],
      (TRANSITION, 'NG43 1.4.1-1.4.3: nonattendance and re-engagement'))],
  ['Transition is a supported process, not only a transfer date.', 'Coordinate and repair practical gaps in recipient care.'],
  [('T24.O01',[1],'Adapt assessment to development, support and practical context.'),
   ('T24.O02',[1,2,3],'Plan and revisit a transition with supported self-management and re-engagement.'),
   ('T27.O02',[2,3],'Make prescription/contact responsibility explicit across child and adult services.')])

case('DYING', 'T26', ('T20','T19','T27'),
  'Continuing care after a decision to withdraw dialysis',
  'An actual last-days scenario revisits uncertainty, wishes and a practical symptom-medication plan.',
  [stage('An adult with advanced illness has chosen to stop HD after a shared goals and capacity discussion. Several days later they become more drowsy with reduced intake. The team assesses whether they may be entering the last days of life.',
      ['What should be communicated about the assessment and uncertainty?', 'Whom does the patient want involved?'],
      ['Assess deterioration, potential stabilization and reversible contributors; a withdrawal decision alone does not predict an exact time of death.', 'Confirm preferences for information and involvement, explain uncertainty and continue supportive review in the agreed goals.'],
      (DYING, 'NG31 1.1.2-1.1.6 and 1.2.3-1.2.5: recognizing dying and communication'),
      (CKD, 'Practice points 5.5.1-5.5.3: supportive care and advance planning')),
   stage('Swallowing is unreliable. The current chart contains long-term preventive medicines and several drugs that could help symptoms, with different kidney-failure risks.',
      ['Which medicines still offer useful benefit?', 'What needs review before choosing a route or symptom treatment?'],
      ['Review expected benefit, burden, adverse effects, interactions and wishes rather than continuing or stopping everything indiscriminately.', 'Choose feasible routes and renal-aware symptom options with appropriate pharmacy/palliative input; no fixed opioid or sedative dose is asserted.'],
      (DYING, 'NG31 1.5.1-1.5.5: medicine review and administration route'),
      (CKD, 'Chapter 4.3: medication management and kidney-function context')),
   stage('The patient and those they want involved agree a symptom/contact plan. The family asks whether anticipatory medicines must all be given immediately.',
      ['How should anticipatory prescribing be individualized?', 'What review and support continue?'],
      ['Anticipate likely symptoms, specify when and how suitable medicines would be used, and review response and harms; having medicines available is not an instruction to administer them all.', 'Document who to contact and reassess changing needs and preferences. Withdrawal does not end care or support.'],
      (DYING, 'NG31 1.6.1-1.6.4: individualized anticipatory medicines and review'))],
  ['Withdrawal and possible dying require continuing goals-based support.', 'Individualize medicine benefit, route and symptom plans with kidney-failure context.'],
  [('T26.O01',[1,3],'Use the patient’s goals in withdrawal/last-days support and revisited advance care planning.'),
   ('T19.O01',[2,3],'Assess medication benefit/harm, organ-function context and feasible administration; no unverified dose protocol.'),
   ('T27.O02',[1,2,3],'Coordinate kidney, palliative and pharmacy care, including uncertainty and contact responsibilities.')])

case('FRAILTY-MARKERS', 'T01', ('T08','T09','T25','T24'),
  'A better creatinine number after loss of muscle and function',
  'A frail older adult’s filtration interpretation, symptomatic BP and nutrition/activity plan must be considered together.',
  [stage('An older adult with CKD has lost weight and muscle during prolonged poor intake. Creatinine falls and eGFRcr rises without other evidence of recovery. A medication decision depends on kidney function.',
      ['Why may the creatinine change be misleading?', 'What additional filtration assessment may help this decision?'],
      ['Reduced creatinine generation with muscle loss can raise eGFRcr without equivalent improvement in filtration.', 'Where eGFRcr is less accurate and GFR changes a decision, use combined creatinine/cystatin-C estimation when available; review its non-GFR determinants too rather than treating it as infallible.'],
      (CKD, 'Recommendation 1.2.2.1 and Table 8: less accurate eGFRcr/non-GFR determinants')),
   stage('Seated BP is 118/68 mmHg and standing BP is 90/58 mmHg with dizziness and near-falls. The patient asks whether every medicine should be intensified to reach a numerical target.',
      ['Which symptoms and risks modify the BP goal?', 'What must be reviewed before changing treatment?'],
      ['Consider less intensive BP lowering with symptomatic postural hypotension and frailty/fall risk.', 'Review measurement, symptoms, volume, medicines and comorbidity, and individualize a tolerable plan; a target does not erase these harms.'],
      (CKD, 'Practice point 3.4.1: less intensive BP lowering with frailty/falls or symptomatic postural hypotension')),
   stage('To protect the kidneys, the patient has imposed severe protein restriction and stopped walking. Nutritional stability and strength are deteriorating.',
      ['How should CKD advice change with frailty and poor intake?', 'What activity plan is safe and useful here?'],
      ['Avoid prescribing low/very-low protein diets in metabolic instability; in older adults with frailty or sarcopenia consider higher protein and energy targets with dietetic review.', 'Tailor activity to cardiovascular and physical tolerance and fall risk, using a supported gradual plan rather than an unqualified weekly target.'],
      (CKD, 'Practice points 3.3.1.3 and 3.3.1.5; recommendation 3.2.2.1 and practice points 3.2.2.1-3.2.2.3'))],
  ['Muscle-dependent creatinine changes need interpretation, not automatic recovery claims.', 'BP, nutrition and activity goals must fit symptoms and stability.'],
  [('T01.O02',[1],'Explicitly explain muscle loss and non-GFR creatinine generation, with confirmatory filtration-marker limits.'),
   ('T09.O02',[2],'Individualize BP treatment for symptomatic postural hypotension, frailty and fall risk.'),
   ('T25.O01',[3],'Tailor nutrition and activity to CKD, unstable intake, sarcopenia and safe physical tolerance.')])

case('ANEMIA-GOALS', 'T08', ('T19','T02'),
  'Investigate anemia before choosing an ESA goal',
  'An adult with CKD needs an anemia cause assessment and an individualized maintenance decision after correctable causes are addressed.',
  [stage('An adult with CKD G4 develops fatigue and Hb 90 g/L. Ferritin is 18 micrograms/L and TSAT is 10%. The anemia has been attributed to low erythropoietin without reviewing blood loss or other causes.',
      ['Which initial tests and causes should be reviewed?', 'Why is CKD not the whole diagnosis?'],
      ['Use CBC, reticulocytes, ferritin and TSAT for initial evaluation, expanding the workup when indicated.', 'Iron deficiency and possible blood loss require assessment; CKD does not justify assuming isolated erythropoietin deficiency.'],
      (ANEMIA, 'Practice point 1.2.1 and Figure 6: initial anemia investigation')),
   stage('The team investigates and treats correctable causes and follows the response. Anemia and symptoms persist, prompting an ESA discussion.',
      ['What must precede the decision?', 'Which benefits, harms and preferences matter?'],
      ['Address correctable causes, including iron deficiency, before ESA/HIF-PHI treatment.', 'Discuss symptom and transfusion considerations against harms and the patient’s priorities; this is not an automatic treatment based on one Hb result.'],
      (ANEMIA, 'Practice point 3.1.2 and recommendation 3.1.1: correctable causes before anemia drug therapy')),
   stage('During adult ESA maintenance the Hb rises to 129 g/L. The patient asks whether pushing it into the normal range would be a better goal.',
      ['What ceiling and individualization does the guideline support?', 'How should the team review the current course?'],
      ['KDIGO recommends an adult ESA target below 115 g/L, with individual selection that accounts for benefits and potential harms.', 'Reassess the treatment course and monitoring with the clinician rather than pursuing normalization or inventing a dose adjustment from this teaching case.'],
      (ANEMIA, 'Recommendation 3.3.1 and practice point 3.3.1: adult ESA maintenance target'))],
  ['Investigate anemia and correctable causes before attributing it to CKD alone.', 'An adult ESA goal is individualized below the stated ceiling, not normalization.'],
  [('T08.O03',[1,2],'Explicit CBC/reticulocyte/iron assessment and investigation of correctable causes rather than assumed EPO deficiency.'),
   ('T08.O04',[2,3],'Individualize adult ESA goals and avoid excessive Hb targets; the reviewed ceiling is below 115 g/L.')])

case('DRUG-AIN', 'T11', ('T06','T19','T22'),
  'A new drug exposure and persistent kidney injury',
  'A possible drug-related interstitial injury requires exposure review, safe alternatives and honest treatment uncertainty.',
  [stage('An adult develops AKI after a new medication exposure. The chronology raises concern for AIN, but volume, infection and other drug-related mechanisms remain possible.',
      ['Which exposure and alternative-cause details are needed?', 'What can chronology establish by itself?'],
      ['Review timing, all exposures, the clinical/urine course and plausible alternative causes; a temporal association is not tissue confirmation.', 'Coordinate withdrawal of a suspected offending agent and, when treatment is still required, a suitable alternative rather than knowingly continuing the same exposure without review.'],
      (AIN, 'Introduction and Discussion: diagnosis, underlying cause and offending-agent cessation')),
   stage('Kidney dysfunction persists despite exposure review and appropriate supportive care. The team is uncertain whether interstitial inflammation or another lesion explains the course.',
      ['Would further diagnostic clarification change treatment?', 'What limits does the treatment literature have?'],
      ['Discuss whether biopsy would clarify a persistent uncertain lesion and change decisions; it is not declared mandatory for every suspected case.', 'The 2025 treatment review included histologically diagnosed AIN studies. That evidence population does not make every clinically suspected case equivalent.'],
      (AIN, 'Methods inclusion criteria and Discussion: histologic evidence population and clinical uncertainty')),
   stage('A steroid course is proposed. The patient asks whether one regimen is proven for every case and whether the original culprit medicine should be restarted to check the diagnosis.',
      ['How should benefit, harm and uncertain treatment evidence be discussed?', 'How should the exposure decision be documented?'],
      ['The review describes heterogeneous timing, regimens and outcomes, with limited high-quality evidence; it does not establish one compulsory steroid course.', 'Document the suspected culprit, alternatives and future prescribing discussion. Deliberate re-exposure is not a routine diagnostic substitute in this teaching scenario.'],
      (AIN, 'Results, Discussion and Conclusion: variable steroid regimens and evidence limits'))],
  ['Review and stop a suspected injurious exposure with a safe alternative plan.', 'Retain diagnostic and treatment uncertainty rather than prescribing a universal AIN regimen.'],
  [('T11.O02',[1,2,3],'Evaluate a drug-related interstitial injury, stop/review the suspected exposure and discuss alternatives plus diagnostic/treatment limits.')])

# Stable alignment IDs are retained, including their historical _gap suffixes.
# A suffix is an identity, not a current status claim.
FACETS = {
    'urinary_infection_gap': ('UTI', ['RN12-CASE-UTI'], ['T02.O01','T17.O02'],
        'Recurrent symptomatic lower UTI investigation and stepwise prevention, with a reviewed teaching case.',
        ['Finite launch cells do not cover every acute/upper UTI, pregnancy, resistance or antimicrobial-dose pathway.']),
    'other_inherited_gap': ('ALPORT', ['RN12-CASE-ALPORT'], ['T02.O01','T02.O02'],
        'Alport-spectrum phenotype/testing and contextual variant interpretation. The T12 tag is secondary; ADPKD objectives are not used to claim Alport coverage.',
        ['Fabry, cystinosis, primary hyperoxaluria, inherited salt-wasting and full genetic/metabolic management remain broader-curriculum ambitions.']),
    'pd_infection_gap': ('PD', ['RN12-CASE-PD-INFECTION'], ['T17.O02','T20.O02','T22.O02'],
        'PD peritonitis recognition and separate exit-site/tunnel assessment with continuing-access review.',
        ['No complete organism/dose, refractory/relapsing infection or catheter-complication treatment algorithm.']),
    'hd_access_gap': ('HD', ['RN12-CASE-HD-ACCESS','RN12-CASE-HD-SESSION'], ['T17.O02','T20.O02','T22.O02'],
        'Ongoing HD access and unit care: clinical assessment, aneurysm/stenosis, trained aseptic catheter use and focused session teaching.',
        ['No complete HD prescription, all unit emergencies, water-system or procedure-competence curriculum.']),
    'transplant_aftercare_gap': ('BK', ['RN12-CASE-BK-AFTERCARE'], ['T02.O01','T17.O02','T19.O01','T27.O02'],
        'Recipient BK surveillance, medication-risk review and graft dysfunction uncertainty. Pre-transplant T21 objectives are not used as aftercare evidence.',
        ['No complete rejection regimen, all post-transplant infections, malignancy or long-term recipient-aftercare curriculum.']),
    'sexual_health_gap': ('SEX', ['RN12-CASE-SEXUAL-HEALTH'], ['T19.O01','T24.O02','T27.O02'],
        'A private informed contraception decision with dialysis and potassium/drug safety; supplementary US eligibility evidence is labelled.',
        ['Comprehensive fertility, pregnancy and sexual-dysfunction evaluation remain broader-curriculum ambitions.']),
    'transition_gap': ('TRANS', ['RN12-CASE-TRANSITION'], ['T24.O01','T24.O02','T27.O02'],
        'Developmentally supported child/adult transition, recipient medication continuity and re-engagement.',
        ['No complete pediatric disease/treatment or transplant-adherence intervention curriculum; no educational outcome claim.']),
    'end_of_life_gap': ('DYING', ['RN12-CASE-DYING'], ['T19.O01','T26.O01','T27.O02'],
        'An actual dialysis-withdrawal/possible-dying scenario with uncertainty, continuing support and individualized medication/route review.',
        ['No complete kidney-specific terminal symptom or drug-dose protocol; no single time-to-death prediction.']),
}

HYPER_SOURCE = 'G02-hyperkalemia-2026-07'
HYPER_QUESTIONS = ('RN-DIAL-004', 'RN-K-001', 'RN-K-002', 'RN-K-003', 'RN-K-004')
HYPER_CASE = 'RN-CASE-HYPERK'


def cited_revision(prior):
    """Advance citation versions only after the selected July passages were read.

    Stable families, objectives, stems, choices and answer values stay intact.
    The historical source snapshot and historical item versions stay in their
    original packs and in installed canonical history. No source-wide clearance.
    """
    questions, cases, evidence = [], [], []
    for kind in ('questions', 'cases'):
        for old in prior.bundle[kind]:
            item = deepcopy(old)
            if item['id'] not in (*HYPER_QUESTIONS, HYPER_CASE):
                (questions if kind == 'questions' else cases).append(item)
                continue
            item['version'] += 1
            if kind == 'questions':
                item['key_version'] = item['version']
            item['review'] = dict(ITEM_REVIEW)
            item['review']['method'] = ('July 2026 UKKA selected passage comparison on 2026-10-05; '
                'citation-only revision, unchanged answer/choices/objective meaning. No evidence-grade or source-wide currency claim.')
            for citation in item['sources']:
                if citation['source_id'] == 'G02-hyperkalemia-2023':
                    citation['source_id'] = HYPER_SOURCE
                    citation['locator'] = citation['locator'].replace('16.2;', '16.2a;').replace('17.1', '17.1.1-17.1.2')
            for section in item.get('stages', []):
                for citation in section['sources']:
                    if citation['source_id'] == 'G02-hyperkalemia-2023':
                        citation['source_id'] = HYPER_SOURCE
                        citation['locator'] = citation['locator'].replace('16.2 and', '16.2a and')
            key = (next(o['text'] for o in item['options'] if o['id'] == item['answer'])
                   if kind == 'questions' else None)
            evidence.append({'id': item['id'], 'version': item['version'],
                'kind': 'question' if kind == 'questions' else 'case', 'reviewed_on': DATE,
                'reviewer_kind': 'assistant', 'independent_human_review': False,
                'source_locators': item['sources'], 'key_text': key,
                'skill': 'interpretation' if kind == 'questions' else 'mixed_domain_reasoning',
                'checked_claim': 'Selected July 2026 sections 14.1, 16.2, 16.3, 17.1-17.2 and 18.1-18.4 support the existing cardiac protection, redistribution/removal, ECG limits and glucose/potassium monitoring claims. No doses or evidence grades were changed.',
                'citation_revision': {'previous_version': old['version'],
                    'previous_source_id': 'G02-hyperkalemia-2023',
                    'selected_source_id': HYPER_SOURCE, 'answer_choices_unchanged': True,
                    'source_currency_hold': 'Selected passages only; the full July/2023 delta and correction/retraction closure remain unproved.'}})
            (questions if kind == 'questions' else cases).append(item)
    return questions, cases, evidence


def programme():
    mapping = deepcopy(previous.programme())
    mapping['version'] = MAPPING_VERSION
    mapping['method'] = ('Assistant item/objective review of the new finite launch cells against the same pinned 2022 curriculum and undated hub-linked blueprint. '
        'Historical official evidence is inherited unchanged; no new official edition or review of Renulus items is inferred. Clinical source/key review is separately pinned.')
    rows = {r['id']: r for r in mapping['alignments']}
    for identity, (prefix, cases, objectives, note, gaps) in FACETS.items():
        row = rows[identity]
        row.update(status='partial', objective_ids=sorted(objectives),
            questions=previous.pins([q['id'] for q in NEW_QUESTIONS if q['id'].startswith('RN12-' + prefix + '-')]),
            cases=previous.pins(cases), scope_note=note, gaps=gaps)
    # Meaning-supported teaching links for the six formerly uncovered objectives.
    for identity, case_id in [
        ('ckd_classification','RN12-CASE-FRAILTY-MARKERS'),
        ('blood_pressure','RN12-CASE-FRAILTY-MARKERS'),
        ('nutrition','RN12-CASE-FRAILTY-MARKERS'),
        ('anemia','RN12-CASE-ANEMIA-GOALS'),
        ('tubular_interstitial','RN12-CASE-DRUG-AIN'),
    ]:
        rows[identity]['cases'].append({'id': case_id, 'version': 1})
    for row in mapping['alignments']:
        for pin in row['questions']:
            if pin['id'] in HYPER_QUESTIONS:
                pin['version'] = 2
        for pin in row['cases']:
            if pin['id'] == HYPER_CASE:
                pin['version'] = 2
    return mapping

def review_evidence(mapping, citation_evidence):
    evidence = previous.review_evidence(mapping)
    evidence.update(pack_version=VERSION,
        method='Assistant source/key, plausible-distractor, synthetic case-stage and objective-meaning review of 18 new questions and 12 cases, plus five citation-only question versions and one citation-only case version. Review does not establish educational efficacy, independent human review or source-wide currency.',
        inherited_review='155 selected prior questions and 25 prior cases remain unchanged. Five questions and one case advance to version 2 solely for the directly checked existing July 2026 hyperkalaemia citation; answer values, choices, families and objective links are unchanged. All 35 source snapshots and all historical release/review bytes are retained.',
        access_limits='Only public primary official/publisher texts and eligible public full-text mirrors were read. No restricted originals, private correspondence, profile or credentials; no source text is bundled. Direct PMC/SAGE/ISPD access errors and initial parallel PDF-extraction errors are retained separately from successful sequential PDF, mirror and public publisher reads. No blanket latest/correction clearance, official item review or independent human endorsement is claimed.',
        sources=deepcopy(NEW_SOURCES), items=deepcopy(ITEM_EVIDENCE) + citation_evidence)
    evidence['source_currency_holds'] = {
        'provenance': '2c383bf8:docs/implementation/finalise-source-currency.md (parent integration 9d8f14f8)',
        'checked_on': DATE,
        'limit': 'The report dispositions remain in force. This release is scoped authoring, not a new audit of the 35 inherited sources.',
        'unverified_correction_incidence': [
            {'source_ids': ['K13-2017', 'K13-2017-expansion'], 'notice_dois': ['10.1016/j.kisu.2017.10.001']},
            {'source_ids': ['K05-2024-amended', 'K05-2024-expansion'], 'notice_dois': ['10.1016/j.kint.2024.04.003', '10.1016/j.kint.2024.10.004']},
            {'source_ids': ['G01-hyponatremia-2014', 'G01-hyponatremia-2014-expansion'], 'notice_dois': ['10.1530/EJE-13-1020e'], 'hold': 'Known July 2014 erratum; corrected-byte/latest-final closure unproved.'},
            {'source_ids': ['L01-urine-eosinophils-2013'], 'notice_dois': ['10.2215/CJN.05270418'], 'hold': 'Known 2018 correction; publisher text and corrected-byte incorporation unproved.'},
        ],
        'hyperkalaemia': 'Historical 2023 record retained; selected claims now cite the existing July 2026 record. Full delta unproved; review due 2026-10-19, not overdue on 2026-10-05.',
    }
    evidence['launch_scope'] = {'facet_ids': list(FACETS), 'questions_per_facet_minimum': 2,
        'teaching_cases_per_facet_minimum': 1, 'focused_hd_case': {'id':'RN12-CASE-HD-SESSION','version':1},
        'required_objective_ids': ['T01.O02','T08.O03','T08.O04','T09.O02','T11.O02','T25.O01'],
        'independent_human_review': False, 'official_endorsement': False,
        'limit':'Finite owner-authorised launch additions plus unchanged adopted breadth minima; not full curriculum depth or a complete official examination.'}
    return evidence

def publish(path=RELEASE, mapping_path=MAPPING_PATH, review_path=REVIEW_PATH):
    prior = validate_pack(PRIOR)
    mapping = programme()
    topics = deepcopy(prior.bundle['topics'])
    for topic in topics:
        topic['version'] += 1
        topic['mapping']['mapping_version'] = MAPPING_VERSION
    questions, cases, citation_evidence = cited_revision(prior)
    result = base.publish_snapshot(Path(path), version=VERSION, topics=topics,
        sources=prior.bundle['sources'] + deepcopy(NEW_SOURCES),
        questions=questions + deepcopy(NEW_QUESTIONS),
        cases=cases + deepcopy(NEW_CASES),
        target_topics=prior.bundle['coverage']['target_topics'],
        minimum_questions=prior.bundle['coverage']['minimum_questions'],
        published_on=DATE, programme_mappings=[mapping])
    pack = validate_pack(path)
    validate_revision(pack, prior)
    previous.write_evidence(mapping_path, mapping)
    previous.write_evidence(review_path, review_evidence(mapping, citation_evidence))
    validate_review_evidence(pack, review_path, [prior])
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=RELEASE)
    parser.add_argument('--mapping-output', type=Path, default=MAPPING_PATH)
    parser.add_argument('--review-output', type=Path, default=REVIEW_PATH)
    args = parser.parse_args()
    print(json.dumps(publish(args.output, args.mapping_output, args.review_output), indent=2))
