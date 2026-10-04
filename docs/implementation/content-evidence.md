# M8 content delivery evidence

Owned lane: `build/content-delivery`, October 4, 2026; ticket #4, parent #1.
Only `content/`, `tools/content/`, `runtime/renulus/content/`, `tests/content/`
and this file are written. Shared foundation and main source register are read only.

## Integration contract (published before the pack)

`ContentRepository(db, pack_root)` consumes the shared canonical Database.
`connect()` returns a sqlite3 row connection; the repository closes its read
connections. `transaction()` is the shared atomic write context. The integrator
must apply unnumbered `runtime/renulus/content/schema.sql` once through the ledger.
No private/native state, learner cases, provider or generative model is used.

Methods: `list_topics()`, `list_cases()`, `get_case(id)`,
`list_questions(topic_id=None)`, `get_question_version(id, version)`,
`install_pack(path)`, `active_manifest()`, `withdraw_question(id, version, reason,
replacement_version=None)`, `withdraw_pack(id, version, reason)`,
`teaching_material()`. Backend question methods return full published keys; M4
owns commitment/exposure/feedback. `list_questions` selects only the active,
nonwithdrawn reviewed assessment pool; `get_question_version` preserves historical
keys and separately annotates withdrawals. Teaching export contains zero question
records, including practice and reserved evaluation records.

Installation validates the full immutable JSON snapshot, inserts and activates
atomically, and refuses changed payloads with existing IDs/versions, withdrawn
packs/items, unknown correction predecessors or corrections without withdrawal.
Same pack reinstallation is idempotent. Historical versions remain stored.
Module DDL has no numbered migration, service, engine index or source originals.

Shared dependency request: `jsonschema==4.26.0` (MIT), actual local Python 3.12
import verified. It supplies maintained JSON Schema 2020-12 validation instead of
an invented schema engine. The shared Python 3.14 environment still needs its
actual dependency proof; integrator owns lockfiles/build configuration.

The newer main `docs/SOURCES.md` was checked read only. Its changed ESC/EMA
rows do not change the original-pack teaching use boundary. No restricted
manual, ESENeph sample bank or source-text adaptation is imported.

## Remaining work

Original pack, primary medical source/key checks, validation CLI, router and
relevant tests are in progress. No completed pack, live model, installer,
complete curriculum or full ESENeph blueprint is claimed at this point.

## Assessment peer shape

`services.registry['content']` is populated by `create_router(services)`.
`list_question_summaries(topic_id=None, domain=None, track=None)` returns id,
version, family_id, family_version, key_version, topic_id, objective_ids,
difficulty, usage and review. Domain is currently the stable topic ID. Only
`general_nephrology` is supported as a track; unmapped examination tracks return
an empty selection. `list_questions(topic_id=None)` is the private full pool.

`get_question_version(id, version)` includes canonical id/version plus question_id,
family_id/family_version/key_version, options (id/text/rationale), answer,
correct_option_ids, rationale, explanation, source locators and source_records
(registered source, edition, URL, check state). It annotates withdrawn, withdrawal
(reason/replacement_version) and current_version separately from the immutable
payload. The snapshot carries source metadata after the original pack disappears.

HTTP prefix is `/content`; server adds `/api/v1`. GET manifest/topics/cases,
GET cases/{id}, GET questions (key-free summaries), GET questions/{id}/versions/{v}
(stem/options without answer or any rationales), POST packs/install (path inside
app pack root), POST questions/{id}/versions/{v}/withdraw. M4 alone returns
answer feedback after commitment. Content's HTTP question access does not itself
record assessment exposure; the desktop should enter questions through M4.
