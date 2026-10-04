# M8 original content delivery

October 4, 2026. Owned branch/worktree: build/content-delivery / Renulus-wt-content.
Ticket #4, parent #1. Shared foundation fffa82c was explicitly authorized and
cherry-picked as 20704fb. All authored changes are confined to content/,
tools/content/, runtime/renulus/content/, tests/content/ and this evidence file.
Main and other lanes are read only. The initial schema.sql from 3e06577 is
unchanged; the shared integrator owns its migration ledger.

## Delivered original pack

renulus-foundations 1.0.0 installs and activates through the real shared SQLite
Database and module router. It contains 27 stable topics, 56 original objectives,
14 synthetic cases with three stages each, and 52 original single-best-answer
questions with keys, option-specific rationales and medical source locators.
Original content is scoped CC BY 4.0; code is MIT.

The pack bundle SHA-256 is
8b63d8bd02402a03d68f84c21159700e1cc5806b72ffad6f0fca2baa28f0485e.
Each of its five payload files has a manifest checksum. The original authoring
source reproduces the same bytes and refuses to overwrite a differing published
snapshot. Corrections require new item/pack versions and preserve old attempt
evidence.

Questions span CKD and anemia, AKI, dialysis, transplantation, glomerular disease,
potassium/acidosis, hyponatremia, CKD-MBD, hypertension, diabetic CKD, ADPKD,
medicine stewardship, nutrition, supportive care, evidence interpretation,
vasculitis and lupus kidney involvement. coverage.json records actual links,
review states and gaps. Five topics have no items: T11 tubular/interstitial,
T13 stones/obstruction, T15 TMA/complement, T18 onconephrology/paraproteins and
T23 extracorporeal therapies/apheresis. Nineteen of 56 objectives are explicitly
uncovered. A secondary topic tag does not automatically cover its objectives.

The original pack is R01. Only reference topic IDs/labels are adopted;
descriptions/objectives are newly authored. No E01 manual, E02 collection,
official exam item, patient data, primary PDF, source prose, figure, table or
algorithm is copied into Git. Local manual/catalogue metadata is not counted
as this pack's published coverage. ESENeph mapping and a complete curriculum
are explicitly absent.

## Medical source/key checks

Every question and case records assistant_reviewed, the assistant reviewer,
date/method, source_key_checked=true and independent_human_review=false. The
assistant checked the intended single key, distractors, synthetic scenarios
and primary recommendation/section locators. This is not an independent
clinician review, efficacy study or clinical-accuracy certification. Validation
checks declared review and key invariants; it cannot infer medical truth from
a boolean.

Thirteen registered source families support the content: K01, K02, K03, K05,
K06, K08, K09, K10, K11, K13, K16, G01 and G02. sources.json records exact
final editions, public URLs, checked dates, scope, rights and check notes.
They remain dated evidence baselines, with no permanent current-guidance label.
Source terms remain independent of the original-content licence.

The pass used public KDIGO finals and precise indexed official recommendations,
UKKA's 2023 hyperkalemia guidance, the official European hyponatremia field
version and its July 2014 erratum. It corrected transplant recommendation
locators, tolvaptan interruption references and CKD frailty/nutrition references
before publication. The muscle-mass GFR scenario was qualified to avoid treating
combined markers as universally optimal in an otherwise healthy person.

K08 is limited to remaining 2021 chapters 1, 3, 5 and 6; replaced IgAN, pediatric
nephrotic, ANCA and lupus scope is excluded. The combined GD PDF had web parser
failures; exact final recommendations were checked through official indexed
final material and KDIGO's topic page. This does not claim a successful full-file
extraction or imported GD corpus. AKI 2012 and diabetes 2022 are labelled finals,
not replaced by 2026 drafts. Transplant teaching concerns candidate assessment,
not a current recipient immunosuppression regimen. UKKA review due October 2026
and the dated 2014 hyponatremia baseline remain visible.

The newer main docs/SOURCES.md was read without modification. CLI validation
used it explicitly. The runtime ships a derived ID-only allowlist with the
register's date/hash, so unknown IDs fail installation. It is not a competing
source/acquisition catalogue or permission grant. Register snapshot SHA-256:
1ee37fb21760a95462839c518f4fc5195fa032e12223d4256642c8fad60533e3.

## Stable peer APIs

create_router(services) returns APIRouter(prefix='/content'); the server adds
/api/v1. It registers services.registry['content']. ContentRepository(db,
pack_root) uses and closes shared connect() read connections, and uses shared
transaction() for every mutation. There is no alternate database, server,
engine index, provider or model route.

- list_topics(): id/version/label/objectives, plus title/name aliases for Study.
- list_cases(), get_case(id): authored synthetic teaching cases and stages.
- list_questions(topic_id=None): trusted backend active, nonwithdrawn reviewed
  assessment pool, including full private keys.
- list_question_summaries(topic_id=None, domain=None, track=None): key-free
  id/version/family_id/family_version/key_version, topic/objective IDs,
  difficulty, usage and review. Domain currently means topic ID; only
  general_nephrology is supported. ESENeph selection returns empty.
- get_question_version(id, version): immutable payload plus question_id,
  correct_option_ids, explanation, current_version, withdrawn and withdrawal
  (reason/replacement_version). Pinned source_records include registered ID,
  title, URL, edition and dated check evidence.
- list_sources(), get_source(source_id): active public source metadata.
- references_for_source(source_id, include_historical=False): metadata-only
  item/version/topic/locator relations for an exact citation ID or register
  family such as K01. Updates can flag active or historical content.
- install_pack(path), active_manifest(), withdraw_question(id, version, reason,
  replacement_version=None), withdraw_pack(id, version, reason).
- teaching_material(): objectives and authored cases only; never assessment,
  practice or held-out evaluation questions.

M4 pins the full private lookup snapshot and owns answer commitment, scoring,
exposure and feedback. HTTP question representations omit answer, all rationales
and correct_option_ids. Held-out evaluation questions are not exposed. There
are no bank hints or automatic bank-context generation. Historical feedback
should use pinned source_records; active source metadata can change.

HTTP: GET manifest/topics/cases/sources/questions; GET cases/{id}; GET
sources/{id} and sources/{id}/references; GET questions/{id}/versions/{v}; POST
packs/install; POST questions/{id}/versions/{v}/withdraw. Install paths stay
inside the app pack root. User/temporary-case creation or saving is not an
operation of this module. No user case is silently converted into a pack.

## Activation, versions and backups

Validation reuses jsonschema 4.26.0 (MIT), JSON Schema 2020-12 and explicit
source/key/objective/review/correction/coverage checks. It rejects file tampering,
unsafe paths, duplicate JSON keys/identities/choices, unknown source families or
locators, unsupported schema, bad key versions, drafts, fabricated human-review
claims and fabricated coverage. Held-out evaluation cannot inflate bank coverage.

Installation uses one BEGIN IMMEDIATE transaction. Immutable snapshots are
inserted before the active pointer changes. Same-version changes fail. Changed
published keys/choices require a correction, installed predecessor and atomic
withdrawal. Family IDs survive correction. Failed activation leaves the old
pack intact and removes staged inserts. Withdrawals are permanent, preserve
historical keys and prevent reactivation. A withdrawn default pack stays
inactive after restart.

exports.py publishes EXPORT_SCHEMA_VERSION=1, EXPORT_DESCRIPTION and the exact
public-content table allowlist: content_packs, content_topics,
content_case_versions, content_question_versions, content_pack_topics,
content_pack_cases, content_pack_questions, content_active_pack,
content_question_withdrawals, content_pack_withdrawals. These contain original
packs and public citation metadata, never user-case, attempt, conversation,
credential or primary-document tables. The integrator owns backup/restore;
reconcile newer withdrawals before activating restored snapshots.

## Observed checks

The real pack passes tools/content/validate_pack.py against the newer main
register. The shared FastAPI server auto-installs it into isolated SQLite and
serves its actual topics, cases, questions and source metadata. No inference
or credentials are used.

Tests cover schema/key/source/coverage failures, numeric clinical key
regressions, tampering, traversal, duplicate keys, review claims, real
activation/idempotency/restart, corrections and pinned old keys, blocked
reactivation, interrupted activation rollback, source relations, export-table
completeness, reserved-question separation, HTTP key omission and synthetic
no-case-save sentinels.

    python tools/content/validate_pack.py content/packs/renulus-foundations/1.0.0 --source-register C:/Users/karol/Documents/t3-workspaces/Renulus/docs/SOURCES.md
    python -m pytest tests/content tests/integration/test_foundation.py -q

The initial full CPython 3.12.10 run passed 42 tests. After adding runtime
register-ID and held-out-coverage checks, shared CPython 3.14.4 passed 44 tests:
39 content and 5 foundation. Actual shared versions: jsonschema 4.26.0,
FastAPI 0.142.2, pytest 9.1.1. One Starlette httpx TestClient deprecation warning;
no failures or skips. This proves the content path in that environment, not a
model connection, desktop journey or native installation.

## Remaining integration

Apply unchanged content-001 DDL through the shared ledger. Integrate 3e06577,
c615d6a and the original-pack handoff commit containing this report. The shared
jsonschema dependency is installed and verified; its lockfile is integrator-owned.
M4 should exercise actual scoring/exposure with this bank; M3 consume staged
cases; M6 present gaps/unavailable tracks; M7 use source-reference relations.
These combined UI journeys are not claimed by isolated content tests.

Package content/packs and the module's source_register_ids.json. The installed
asset layout may set services.registry['content_pack_root'] before router
creation. Install later eligible revisions explicitly rather than undoing a
withdrawal. Remaining objectives and formal examination mapping need further
content work. No full ESENeph blueprint, live model, native installer or
independently reviewed clinical bank is claimed.
