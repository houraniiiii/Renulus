# Design C pass 1 — migration and data

October 10, 2026. Independent report-only worker: `dc-review-data`,
branch `codex/dc-review-data`. Baseline
`1b30a89687cfcc5fb13b1cf824bbc43c19f870ed` contains `528025ff`.
Only this file is reserved/changed. No source, spec, migration, manifest or
other worker's worktree was edited. All runtime state is under
`C:/Renulus/scratch/design-c/dc-review-data/`; synthetic records and originals,
no credentials, provider/model calls, helper engines or OS/computer input.

**Outcome:** the integration lead's uncommitted canonical foundation resolves the
reproduced typed deletion, known-schema recovery, downgrade-gate and restore
invalidation failures at the scopes checked below. The attachment tombstone
producer remains a concrete DC04 prerequisite. New table policies and unavailable
provenance behavior remain feature integration obligations. This report closes
no DC ticket and does not establish populated Design C upgrade or release acceptance.

## Material findings and dispositions

Paths/lines in the baseline findings refer to this report's worktree at the
baseline above. Canonical rechecks read `C:/Renulus/dev/repo` only; they are
uncommitted source evidence, not evidence for a release artifact.

| Finding | Exact source and failure example | Minimal action / disposition |
| --- | --- | --- |
| **R1 P1: membership can delete shared content** | `runtime/renulus/storage/backup.py:249–253,271`; `recovery_records.py:193–205`. Every reference propagates into every string component of a composite primary key. Deleting project P with membership PK(P,D) removes independent Library D. Both JSON merge and SQL source pruning reproduced this. | One installed table policy, full typed row identities and explicit parents. Remove a membership row without blocking either endpoint. **Canonical recheck passed:** composite `study_project_documents(project_id,revision_id)` preserves document/revision and its original in JSON, SQL pruning and ZIP1/ZIP2 export. |
| **R2 P1: tombstone namespaces collapse** | `backup.py:271`; `recovery_records.py:203` discard `entity_type`. A tombstone `(case,overlap)` deletes a Learn thread whose legal opaque ID is also `overlap`. | Map exact producer types to table identities; unknown types remain ledger data without matching unrelated namespaces. **Canonical JSON/SQL/ZIP1/ZIP2 recheck passed.** |
| **R3 P1: provenance becomes destructive ownership** | `runtime/renulus/memory/schema.sql:9–10,15–26` plus the R1 graph. A retained revision-2 memory fact with `source_id=deleted_thread` and its edited history disappear during restore. | Facts own their history/source-edge rows; a source chat does not own retained facts. Prune unavailable evidence links and expose unavailable provenance. **Canonical fact/history preservation passed** in JSON/SQL/ZIP1/ZIP2; source-availability UI remains M5/DC10 work. |
| **R4 P1: additive schema does not imply backup compatibility** | `backup.py:177–180,199–204`; `recovery_records.py:79–80`; `recovery_segmented.py:267–279`. Export a populated schema1 thread, then add `lifecycle DEFAULT 'active'`: original JSON, ZIP1 and ZIP2 all fail `backup_columns`. | Verify raw archive hashes/sizes first, validate immutable source inventory, then convert **registered** columns before target validation. Parent chose sidecars and an empty explicit default registry. **Canonical original-schema1 JSON/ZIP1/ZIP2 acceptance passed** with unchanged original IDs/fields. Arbitrary added columns remain correctly refused; the illustrative lifecycle column is not an authorized inferred default. |
| **R5 P1: removed attachment resurrects** | `runtime/renulus/cases/repository.py:295–304,338` and `cases/originals.py:65–69`. Save a synthetic PNG, export full ZIP2, remove attachment and explicitly Save, then restore older ZIP into the same profile: zero live attachments becomes one, with no attachment tombstone. | M1/DC04 must write exact `case_attachment` tombstone in the same transaction that removes saved attachment/parts, invalidate dependent work, and reject reattachment of that ID. **Open, assigned prerequisite by lead.** The storage policy cannot reconstruct a deletion that its producer never recorded. |
| **R6 P1: unchanged schema1 permits older writers** | `runtime/renulus/storage/database.py:9,22–37` and `server.py:89–103`. Apply an unknown additive migration; the old Database accepts the profile because `user_version` stays 1. | Integration owns schema2 and complete migration/checksum inventory before repository writes. **Canonical recheck passed:** full known inventory accepted, only an unknown future name rejected, original schema1 version unchanged on refusal, changed checksum and unsupported schema3 refused. Baseline transactional statement/ledger rollback controls also passed. |
| **R7 P1: restore left derived readiness stale** | `runtime/renulus/storage/recovery.py:290–292` only recorded rebuild-required; `memory/service.py:281–283` rebuilds on non-ready/no-engine state. Real JSON restore imported a fact but left ready/epoch7 unchanged. This proves stale canonical readiness, not an actual engine-result leak. | **Canonical recheck passed** after `storage/invalidation.py:20–29` was called inside merge: memory epoch7→8/dirty, local context epoch0→1, Library dirty marker, markers excluded from export, no memory capture queued. Feature jobs/caches must compare local context epoch before publication. |

Early material findings and the concrete policy mapping were sent to the lead
before report completion. The lead owns the shared fixes; this branch contains
no implementation patch.

## Concrete installed-policy mapping

Use one table registry for `backup.py`, `recovery_records.py`, both archive source
filters and `Recovery._restore`'s original promotion/removal checks. Identity is
`(table namespace, complete ordered primary-key tuple)`. A composite relation
row is one identity, not several entities. Never infer relations from `*_id`,
SQL defaults, ID prefixes or archive-supplied relation declarations.

| Actual record family | Owned descendants | Links / preservation rules |
| --- | --- | --- |
| Learn | `learn_threads → learn_messages, learn_runs` through `thread_id`; new `learn_conversations` sidecar keeps original thread identity. | Project membership is a link. Historical citations retain their pinned revision/locator. |
| Saved Cases | `case_sessions → case_attachments → case_attachment_parts` through `case_id` / `attachment_id`; new case sidecar retains original case ID. | Reuse existing attachment IDs/parts, never duplicate originals into new Knowledge tables. Unsaved/dirty in-memory snapshots have no migration row. Saved/temporary retention is independent of daily/teaching kind. |
| Library | `knowledge_documents → knowledge_revisions → knowledge_passages, knowledge_jobs, knowledge_cleanup`. | Exact existing delete producer type is `knowledge-document` (`knowledge/repository.py:712`). `active_revision/latest_revision` are pointers, not reverse ownership. `source_id` is publisher identity, not a Library-document parent. |
| Memory | `memory_facts → memory_history, memory_sources, memory_requests` via `record_id`. `learning_evidence → memory_jobs` via `evidence_id`. | `memory_facts.source_id` is retained provenance, never a destructive source-chat edge. `memory_sources.source_key=evidence:<id>` is an explicit link; prune it without deleting the fact. Preserve suppression markers preventing recapture. |
| Evidence | Dispatch `learning_evidence.entity_id` by `kind`: `study-interest/study-answer → learn_thread`, `assessment-answer → assessment_attempt`. | Current generated repository creates no learning-evidence row; a generated-answer mapping is a future producer contract, not existing evidence. General manual evidence has no inferred parent. |
| Legacy assessment | Session owns items and committed per-question answers; item owns its answer/exposure. Generated equivalents remain separate. | `question_id/question_version/key_version/family_id/family_version/topic_id` are historical content references. `assessment_commands.target` is a replay target requiring explicit policy, not a suffix-inferred edge. |
| Projects | Project owns project goals. Chat owns saved chat attachments; attachment owns original/preview. | `study_project_chats` and `study_project_documents` remove only their own row when either endpoint becomes unavailable. `chat_kind` dispatches learning vs case. |
| Published content / Updates | Preserve immutable historical versions. Updates own their review/library-change/literature rows through declared `entry_id`. | Full-version `content_pack_*` rows and `update_affected_versions(entry_id,kind,entity_id,version,pinned_source_id)` are links; never propagate deletion into item/source/topic identities. |

The proposed contracts were inspected in `dc02-contracts` at docs commit
`efcc782413556cc64eedd527569b18612c7c851b`, and the subsequently available
uncommitted `runtime/renulus/design_c_contracts.py` was read. They preserve
kind/retention/lifecycle, original identities, immutable test versions and partial
legacy denominators. Their validators and fixture adapter do not perform migrations.

**Feature prerequisite:** proposed `RelationColumn.on_missing='unavailable'`
(`design_c_contracts.py:260,263–265`) is different from deleting a link row.
The inspected canonical `relations.Binding.kind` is descriptive;
`row_parents:103–114` and SQL `build_blocked:199–216` block every declared
child. Do not add saved-version→attempt/report/job-result links to that pruning
policy without implementing preserve-unavailable behavior. A hard FK from an
attempt to a physically pruned version otherwise makes restore fail despite
keeping the attempt row. M4 should retain pinned immutable versions required by
attempts, or use a nullable live link with independently preserved attempt
snapshot/provenance. Goals, new ordinary-chat attachments, exposure rows and
exact tombstone aliases must enter the policy when their owners add actual tables.

## Preserved meanings, ownership and remaining evidence

The installed registry is module-owned (`services.registry`): Learn
`learn/api.py:34`; Cases `cases/api.py:28–29`; assessment and generated practice
`assessment/api.py:18,24`; Knowledge `knowledge/api.py:59–63`; Memory
`memory/api.py:13`; Study `study/api.py:26`. Module owners propose additive DDL;
the lead commits and sequences it. No worker should rewrite an applied schema
or claim a competing migration number. Proposed reservations are `learn-002`,
`cases-003`, `knowledge-003`, `study-002`, `assessment-003/004`; the lead's
inventory must cover exactly the merged scripts before any feature initializes.

Legacy `assessment_sessions.mode='reviewed'` is origin, not Study/Test execution
mode; `assessment_attempts` is one committed answer. Actual reviewed
Start(3)→Answer(1 correctly)→End retains **1/1 accuracy with 2 unscored blanks**,
not 1/3. Baseline JSON, ZIP1 and ZIP2 restore preserved exact session/item/answer/
exposure rows and score cohorts (16 assertions). Use this fixture for DC12's
adapter; do not regrade, reset exposure, infer deadlines or duplicate attempt IDs.
The changed Design C adapter/whole-attempt engine remains unproved.

Restore invalidation now has a bounded verified local generation; DC06/DC19 and
other async producers must capture `design_c.context_epoch` and recheck it in
the same transaction as publication, alongside input revisions, tombstones,
settings, permissions and active-Test policy. UI/search/tab caches must discard
stale results on the same transition. Keep this local operational epoch out of
backups; no restored job should automatically start provider work.

Still required: M1/DC04 attachment-removal tombstones and sentinel race checks;
feature-owned sidecar backfill and re-open evidence; explicit unavailable
provenance/FK handling; reader-original/media/rights additions; job/cache epoch
consumers; crash/restart during a real populated coordinated C upgrade and file
promotion; integrated DC20 old-profile and DC21 matching packaged/native checks.
The SQL rollback control simulated failure inside one migration, not process
termination during the whole multi-module upgrade. No temporary case was promoted
by these tests. Supported old editions, renamed/private content and rollback into
a separate supported profile remain integration acceptance, not this report's claim.

## Receipts

All paths below are external synthetic evidence under the worker's sole profile.
Read `results.json` in each directory; no runtime artifacts enter this commit.

| Directory under `C:/Renulus/scratch/design-c/dc-review-data/` | Evidence |
| --- | --- |
| `pass1-9a2652a22536` | Final baseline assertion harness: **11 expected failures, 3 passing controls**, exit 1; valid synthetic PNG attachment; six original material findings. |
| `canonical-recheck-d75e7ec072d1` | **20 passing assertions**: typed JSON, SQL pruning, ZIP1/ZIP2 source filtering; shared originals, namespace separation, retained fact/history. |
| `canonical-recheck-435c6f4ff618` | Original schema1 JSON/ZIP1/ZIP2 actual restore and schema2 accepted; first readiness test reproduced the subsequently fixed epoch/ready gap. |
| `canonical-recheck-b08e3fe90f00` | **6 passing assertions** with a complete correct known inventory, unknown future migration, unchanged schema on refusal, changed checksum and schema3. |
| `canonical-recheck-900993b8c823` | **8 passing assertions** after restore invalidation patch: dirty/epochs/export exclusion/no queued capture. |
| `pass1-38a00708f224` | **16 passing assertions**: actual legacy partial scoring and exact record/exposure round trips for all three inputs. |

Canonical checks were performed against the lead's uncommitted foundation; pin
its eventual commit and rerun affected checks after integration. The report's
own commit requires no implementation prerequisite and may be cherry-picked
independently. No push or feature-ticket status change is part of this handoff.

## Reproduce the baseline failures

Run the following block through `C:/Renulus/dev/python/Scripts/python.exe -`
from this baseline worktree, with `PYTHONPATH=<worktree>/runtime`,
`PYTHONDONTWRITEBYTECODE=1` and `TEMP/TMP` set to the owned synthetic root.
It creates only unique scratch profiles and uses actual repositories/recovery.
The composite link and lifecycle ALTER are deliberately representative future
DDL; they are not a claim that those features existed in the baseline. The
illustrative lifecycle test is a conversion requirement **only if its exact
default is registered**; canonical sidecar design intentionally leaves it refused.
The assertion runner checks product invariants against those actual operations;
its expected baseline exit is 1. Do not use it as an unmodified canonical test:
canonical typed-policy fixtures use the installed `study_project_documents`
binding, and future migration refusal requires the actual complete inventory.

```python
from pathlib import Path
from contextlib import closing
import base64, hashlib, json, sqlite3, uuid, zipfile, unittest, sys
from renulus.storage import AppPaths, Database
from renulus.services import Services
from renulus.storage.backup import export_records, apply_records, validate_records
from renulus.storage.recovery_records import installed_schema, prune_deleted, scratch, copy_snapshot
from renulus.storage.recovery_limits import SEGMENTED_LIMITS
from renulus.storage.recovery_archive import backup_to
from renulus.storage.recovery_segmented import backup_segmented_to
from renulus.storage.recovery import Recovery
from renulus.contracts import ApiError
from renulus.cases.repository import CaseRepository
from renulus.cases.models import StartCase
from renulus.cases.originals import accepted_original
repo = Path.cwd()
root = Path('C:/Renulus/scratch/design-c/dc-review-data') / ('pass1-' + uuid.uuid4().hex[:12])
root.mkdir()
now = '2026-10-10T12:00:00+00:00'
results = []
def record(name, expected, observed, scope):
    results.append(dict(name=name, expected=expected, observed=observed, reproduced=expected!=observed, scope=scope))
def service(name):
    paths = AppPaths.create(root/name, repo)
    s = Services(paths, Database(paths.database))
    for mod in ('learn','knowledge','cases','assessment','memory'):
        s.db.apply_migration(mod+'-001', (repo/'runtime/renulus'/mod/'schema.sql').read_text(encoding='utf-8'))
        for migration in sorted((repo/'runtime/renulus'/mod/'migrations').glob('*.sql')):
            s.db.apply_migration(mod+'-'+migration.stem, migration.read_text(encoding='utf-8'))
    return s
def thread(s, identifier='thread_synthetic'):
    s.db.execute('INSERT INTO learn_threads VALUES(?,?,?,?,?,?)', (identifier,'Synthetic learning','ckd','direct',now,now))
def zip_export(s, version, name):
    directory=s.paths.cache/name
    directory.mkdir()
    path=directory/'backup.zip'
    (backup_to if version==1 else backup_segmented_to)(s,path)
    return path
def zip_preview(s, archive):
    recovery=Recovery(s)
    identifier,directory=recovery.begin_preview()
    keep=False
    try:
        (directory/'input.zip').write_bytes(archive.read_bytes())
        value=recovery.complete_preview(identifier,directory)
        keep=True
        return recovery,value
    finally:
        recovery.end_upload(directory,keep=keep)
s = service('membership')
s.db.apply_migration('synthetic-project-links', '''CREATE TABLE learn_projects(id TEXT PRIMARY KEY);
CREATE TABLE learn_project_documents(project_id TEXT NOT NULL REFERENCES learn_projects(id),document_id TEXT NOT NULL REFERENCES knowledge_documents(id),PRIMARY KEY(project_id,document_id));''')
s.db.execute('INSERT INTO learn_projects VALUES(?)',('project_synthetic',))
s.db.execute('INSERT INTO knowledge_documents VALUES(?,?,?,?,?,?,?,?,?,?,?)', ('doc_synthetic','Synthetic shared source','synthetic-source','personal-library',None,0,None,None,None,now,now))
s.db.execute('INSERT INTO learn_project_documents VALUES(?,?)',('project_synthetic','doc_synthetic'))
s.db.mark_deleted('project','project_synthetic')
bundle=export_records(s)
with s.db.transaction() as conn:
    summary,blocked,_=apply_records(conn,bundle)
    record('R1_JSON_composite_membership','shared document survives', 'shared document survives' if conn.execute("SELECT 1 FROM knowledge_documents WHERE id='doc_synthetic'").fetchone() else 'shared document removed', 'real apply_records; representative new link DDL')
    record('R1_JSON_blocked_namespaces',['project_synthetic'],sorted(blocked),'real blocked_ids')
    conn.rollback()
with closing(s.db.connect()) as source:
    definitions=installed_schema(source,SEGMENTED_LIMITS)
    with closing(scratch(s.paths.cache/'prune.sqlite3',definitions,SEGMENTED_LIMITS)) as stage:
        copy_snapshot(source,stage,definitions,SEGMENTED_LIMITS)
        prune_deleted(stage,definitions,SEGMENTED_LIMITS)
        record('R1_SQL_composite_membership',1,stage.execute('SELECT COUNT(*) FROM knowledge_documents').fetchone()[0],'real prune_deleted, segmented source-filter path')
s = service('namespace')
thread(s,'overlap')
s.db.mark_deleted('case','overlap')
with s.db.transaction() as conn:
    apply_records(conn,export_records(s))
record('R2_cross_namespace',1,len(s.db.fetch_all('SELECT id FROM learn_threads')),'actual Learn schema + unrelated case tombstone')
s = service('retained-memory')
thread(s)
s.db.execute('INSERT INTO memory_facts VALUES(?,?,?,?,?,?,?,?,?,?,?)',('memory_synthetic','Synthetic independently edited lesson','a'*64,'lesson','ckd','study',2,'learn_thread','thread_synthetic',now,now))
s.db.execute('INSERT INTO memory_history VALUES(?,?,?,?,?)',('memory_synthetic',2,'Synthetic independently edited lesson','edited',now))
s.db.mark_deleted('learn_thread','thread_synthetic')
with s.db.transaction() as conn:
    apply_records(conn,export_records(s))
record('R3_retained_memory',1,len(s.db.fetch_all('SELECT id FROM memory_facts')),'actual memory_facts.source_id and memory_history')
s = service('old-backups')
thread(s)
old_json=export_records(s)
zips={v:zip_export(s,v,'zip'+str(v)) for v in (1,2)}
s.db.apply_migration('synthetic-learn-002',"ALTER TABLE learn_threads ADD COLUMN lifecycle TEXT NOT NULL DEFAULT 'active';")
for kind in ('json','zip1','zip2'):
    try:
        if kind=='json':
            with closing(s.db.connect()) as conn: validate_records(conn,old_json)
        else: zip_preview(s,zips[int(kind[-1])])
        observed='accepted'
    except ApiError as e: observed=e.code
    record('R4_old_'+kind+'_after_add_column','accepted',observed,'actual validators; known additive lifecycle default')
s = service('removed-attachment')
case=CaseRepository(s)
view=case.start(StartCase(text='SYNTHETIC CKD CASE'))
attachment=accepted_original('synthetic.png','Synthetic original','image/png',base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aK1sAAAAASUVORK5CYII='))
view=case.attach(view['id'],view['revision'],attachment)
view=case.save(view['id'],view['revision'])
old=zip_export(s,2,'older')
view=case.remove_attachment(view['id'],attachment['id'],view['revision'])
view=case.save(view['id'],view['revision'])
record('R5_attachment_tombstone',True,s.db.is_deleted('case_attachment',attachment['id']),'actual remove_attachment -> save_originals')
recovery,checked=zip_preview(s,old)
recovery.restore_preview(checked['preview_token'],checked['exported_at'],True)
record('R5_attachment_resurrection',0,len(s.db.fetch_all('SELECT id FROM case_attachments')),'actual segmented preview+restore into same profile')
s=service('downgrade')
s.db.apply_migration('synthetic-design-c-future','CREATE TABLE learn_future_records(id TEXT PRIMARY KEY);')
observed='accepted'
try: Database(s.paths.database)
except RuntimeError: observed='refused'
record('R6_unknown_applied_migration','refused',observed,'actual Database constructor; representative future ledger name')
s=service('controls')
try: s.db.apply_migration('synthetic-interrupted','CREATE TABLE learn_rollback_probe(id TEXT PRIMARY KEY); INSERT INTO missing_table VALUES(1);')
except sqlite3.DatabaseError: pass
record('C1_atomic_failure',False,bool(s.db.fetch_one("SELECT name FROM sqlite_master WHERE name='learn_rollback_probe'")),'positive control: DDL rollback')
record('C2_no_failed_ledger',False,bool(s.db.fetch_one("SELECT name FROM migration_ledger WHERE name='synthetic-interrupted'")),'positive control: ledger rollback')
s.db.execute('PRAGMA user_version=2')
observed='accepted'
try: Database(s.paths.database)
except RuntimeError: observed='refused'
record('C3_schema2_refused','refused',observed,'positive control: old binary with genuinely bumped version')
receipt=dict(baseline='1b30a89687cfcc5fb13b1cf824bbc43c19f870ed',root=str(root),results=results)
(root/'results.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2))
suite=unittest.TestSuite()
for result in results:
    def verify(result=result):
        unittest.TestCase().assertEqual(result['observed'],result['expected'],result['name'])
    suite.addTest(unittest.FunctionTestCase(verify,description=result['name']))
outcome=unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(0 if outcome.wasSuccessful() else 1)
```

## October 10 follow-up — connected imports and DC20 scope

The pass-1 text and its illustrative repro above remain historical evidence.
Later leases authorized collection, generation/nightly and import feature work.
Those source paths are now frozen after handoff. The active DC20 reservation is
exactly this report and `tests/integration/test_design_c_populated_upgrade.py`.
All new profiles, archived old source and receipts stay beneath
`C:/Renulus/scratch/design-c/dc-review-data/`. No fake migration DDL, live
provider, owner profile, credentials, native input, push or ticket closure.

### DC17 hidden receipt and independent boundary fixes

The app-scoped hidden journey used the actual Tests-mounted ImportPanel and a
private pasted synthetic original: personally review Q1, edit/resolve/review Q2,
remove Q3 from the saved set, explicitly publish two personal questions, open
the exact version, start Test and save both answers. A normal app restart kept
both answers, the edited wording and help restrictions. A neutral report during
Test retained native private import provenance. Explicit submission produced
2/2 personal, zero blanks/excluded. Reopening the import kept the original Q2
wording and removed Q3, alongside the edited candidate. The narrow hidden view
was also checked at 1000×720 / 125%. No normalization or generation call ran.

`imports/hidden-final.json` contains read-only SQLite assertions, identities,
original SHA and five capture paths. The controller receipt is
`c/s-7e1a4429/out/receipt.json`: normal restart and final close, no forced or
remaining processes and no controller fault. Source build SHA is
`c4b3e337fa58ee3e2754ffbf2d485cc74d0421db6a7d339ed36f3a5cc223d615`.
This is hidden app evidence, not native installation or a packaged release.

Two subsequent independent P1 findings were reproduced and fixed in separate
bounded commits. C4 `13c14729`, integrated `a2a5f2d4`, checks current retained
source/display/integrity authority before import Save replay, including a changed
key/hash. `imports/c4-red.xml` retains three reproduced failures;
`imports/c4-final2.xml` passed 35 with zero skips. C1 `f5d660aa`, integrated
`1b12c19f`, retains the trusted native import or fictional envelope in private
`question-report-snapshot/2`; old projections remain explicitly incomplete.
Actual producer → attempt → report → typed deletion → Recovery JSON checks
passed 21 (`imports/c1-run1.xml`), and two legacy checks passed
(`imports/c1-legacy.xml`). Neither changed DDL or exposed private provenance
through the neutral receipt. Pass-2 findings remain preserved in their owners'
reports; these receipts do not close a feature ticket.

### DC20 inventory and first actual upgrade slice

The inventory identified already-proven individual behavior in contract,
migration/import005, attachment, generation/nightly and import/report owner
suites. Those checks are not duplicated as independent low-level guards here.
The missing seam is a populated old profile upgraded by the actual coordinated
app, followed by current producer writes and coordinated recovery/deletion.

The new harness archives committed `1b30a89687cfcc5fb13b1cf824bbc43c19f870ed`
runtime, its committed Hermes source, content and helper manifest. It verifies
the captured schema1 records/inventory against the committed fixture manifest,
restores them through the old production Recovery, and uses real old Learn,
Library and Case-original producers. A subsequent slice also adds/edits an old
manual learner-memory fact through its owner. No historical DDL is invented.
Old ZIP2 restoration into separate schema1 profiles rebases originals rather
than copying a SQLite profile with stale absolute paths.

The first five checks passed on source through `08d9272f` (`dc20-4.xml`):
populated schema1 → coordinated schema2 startup/reopen; deterministic legacy
backfill creates two versions once; old runtime refuses the upgraded profile;
real process exit 73 while executing committed assessment003; restart completes
that script; actual old JSON, ZIP1 and ZIP2 restore exact historical records and
the promised media. Case bytes use canonical SQLite parts; Library originals
use promoted files. Records-only JSON intentionally carries no original bytes.

The interruption is **per migration script**, not whole-profile rollback:
assessment003 tables and ledger entry roll back, earlier committed scripts and
the schema2 stamp persist, and a current restart resumes. Old runtime refusal
after that stamp is the supported downgrade behavior. The trace marker records
the actual `CREATE INDEX assessment_tests_recent` statement reached immediately
before `os._exit(73)`; integrity and historical rows are checked after restart.

Retained initial receipts distinguish harness mistakes from product defects:
`dc20-1.xml` omitted required archived Hermes files; `dc20-2.xml` omitted the
synthetic USERPROFILE; `dc20-3.xml` incorrectly assumed file-backed Case originals.
The latter run already passed upgrade/reopen and real interruption. No source
fix was made for those harness errors.

The first combined producer setup exposed an assembly prerequisite at
`08d9272f`: committed Notes owner existed, but `create_app` did not mount its
router/register `notes`, so `Services.get('notes')` returned 503. Reported early;
`dc20-5.xml` retains the three setup errors. The lead published the actual
`knowledge.note_api` mount in `a4439597`. The normal merge of `4316fde0` consumed
that mount, Notes `7116e427`/`820d1906` and Progress `77e139d9`. The completed
harness uses `services.get('notes')` from the actual assembled app.

### DC20 completed populated acceptance — October 10, 2026

The final receipt `C:/Renulus/scratch/design-c/dc-review-data/dc20-9.xml` records
**eight passed, zero failures/errors/skips**, in 225.07 seconds. The tested
production source is the normal shared baseline through `4316fde0`; lane HEAD
before this completion commit is `cf9b93b10b9c238bbe01176bf60d6ba27ac3ef8d`.
No material recovery failure remains in this bounded suite. Later canonical
commits are not implicitly covered by this receipt. The original pass-1 findings
and their reproduced failures above remain intact.

| Combined scenario | Actual evidence | Result |
| --- | --- | --- |
| Populated schema1 upgrade and reopen | Archived committed old runtime restores the captured fixture, writes Learn/Library/Case originals and two memory revisions; current `create_app` applies real migrations, preserves historical rows and IDs, backfills two legacy versions once, then reopens without duplicates. Old runtime refuses schema2. | 1 passed |
| Interrupted coordinated upgrade | Child process exits 73 at the committed assessment003 index statement. Failed-script tables/ledger roll back, SQLite integrity passes, earlier scripts/schema2 stamp remain, and current restart completes with preserved history. | 1 passed |
| Old JSON/ZIP1/ZIP2 into current app | Original schema1 exports from the old runtime preserve captured Learn/Case/assessment/Knowledge/memory/evidence rows. ZIP originals retain their respective file/SQLite-parts representation; JSON retains records without original bytes. Restore invalidates local context and Library readiness without memory work. | 3 passed |
| Current producers, restore, reopen and deletion in JSON/ZIP1/ZIP2 | A genuinely upgraded profile produces Project/Goal, two Notes revisions, saved Chat/PNG/draft, edited and personally resolved import, reviewed-bank version, generated version, whole attempts and native private reports. Older restore honors owner tombstones; post-deletion exports restore into fresh profiles with retained independent history and without removed owners/media. | 3 passed |

The current chain uses real registered repositories and migrations. Generation
routes through the actual selected ProviderManager to one installed synthetic
transport batch: Codex `gpt-6.1-sol`, five accepted questions, one call total.
Its in-memory synthetic token is absent from exports. External socket connects
are rejected; exact loopback addresses are allowed for Windows asyncio's
self-pipe. Child environments strip account/provider variables and use only
lane-owned profile/cache/temp paths. No live provider or credential was used.

The imported personal attempt retains one correct answer, one unanswered and
denominator two; the reviewed attempt retains two correct out of two. Actual
Study Progress retains three reviewed answers (one captured old plus two new),
with personal questions excluded. Submitted result JSON, attempt snapshots,
immutable versions and private question-report snapshots survive all three
restores. Deleting the imported live version clears its submitted attempt's
live pointer while preserving its historical result and report provenance.

Project deletion removes memberships and Goal while preserving independent
Chat/Notes owners. Chat deletion removes owned attachment metadata/originals.
Import/version deletion and Case remove-attachment plus Save resist older
archive resurrection. ZIP Notes deletion also resists older archives. A final
export after those deletions, restored into a fresh profile, checks both ZIP
source filters and JSON filtering: deleted owners/media stay absent, the
independent old Library original survives ZIP, and memory/history, reports,
attempt results and Study Progress remain. Foreign-key checks pass.

Restore advances local context and memory index epochs, leaves memory readiness
non-ready and sets Library restore-dirty. Local `design_c.context_epoch`,
`knowledge.restore_dirty` and `nightly.state` are absent from exported preferences.
Reopening creates no duplicate legacy versions or generation/import tasks;
memory jobs remain empty. This suite uses completed producer jobs, so it does
not add a second proof of the separate active-job restore-interruption guards.

`dc20-6.xml` retains the strict attachment admission failure from an invalid
minimal PNG CRC; the fixture was corrected to a valid synthetic PNG.
`dc20-7.xml` retains the harness's overly strict socket guard blocking the
Windows asyncio self-pipe; the guard now permits exact loopback only. Neither
required a production change. `dc20-8.xml` passed the three combined scenarios
before the final fresh-profile source-filter checks. `dc20-9.xml` is the final
complete result; earlier receipts remain available.

Reproduce from this worktree with the installed contributor Python, a synthetic
profile/cache/temp environment under the lane scratch root, and offline helper
flags. The harness itself creates uniquely named profiles and archives the
committed old source; it requires that commit and the committed fixture manifest.

```powershell
C:/Renulus/dev/python/Scripts/python.exe -m pytest tests/integration/test_design_c_populated_upgrade.py -p no:cacheprovider -q --basetemp=C:/Renulus/scratch/design-c/dc-review-data/dc20-pytest9 --junitxml=C:/Renulus/scratch/design-c/dc-review-data/dc20-9.xml
```

Remaining acceptance is explicit. The historical runtime runs with installed
Python/dependencies; this is not a historical packaged executable or matching C
Windows installation. Library/Notes extraction remains queued here: original
and revision preservation is proved, successful extraction/index rebuild is
not. This whole populated harness does not claim mounted HTTP Notes rights or
Study help/context/stale-draft behavior. Poincare's disjoint Notes test/report
lease owns that acceptance, and received the actual passing seams and resolved
mount prerequisite. Worker/native/helper and final matching-source integration
remain separately scoped. No source/schema changes or feature-ticket closure
are part of this two-file checkpoint.

### Pass 3 — source preflight before cutover, October 10, 2026

This report-only review reads committed
`eb20e0cffa55de4b2d27f17e459a3b2f8c4d30aa` through `git show`, together with
Zeno's Windows preparation review. The integrated DC20 test bytes retain their
eight-pass receipt above; that suite was not rerun. No package, installation,
app/provider/helper execution, launcher mutation or owner-profile read occurred.
Only this report changes. This is source preflight, not an installed pass.

Two actionable findings were sent to the parent before this checkpoint:

| Finding | Exact committed source and reproduction | Minimal action before execution |
| --- | --- | --- |
| P3-D1: synthetic environment does not confine inherited home paths | `apps/desktop/scripts/verify-installed-product.mjs:123-137` copies `USERPROFILE`, `APPDATA` and `LOCALAPPDATA`; `launch` calls it with `process.env` at line 316. Loading the complete committed modules in memory and supplying three synthetic sibling-home paths returns all three unchanged outside the selected evidence directory. `electron/profile.ts:19-22` forwards them to the backend. Explicit app profile, TEMP and known helper caches are confined, so this is a reproduced acceptance-boundary gap, not an observed owner-state write. | Rebase all three home directories beneath the fresh evidence root, or require and assert a parent-sanitized environment before the verifier runs. Create those owned directories before launch. Add a guard assertion for inherited outside-home values; the existing environment test at `test-verify-installed-product.mjs:83-97` supplies none of these three fields. Treat isolation as unresolved until that narrow boundary is checked. |
| P3-D2: named delivery child cannot pass artifact validation | `delivery_paths.py:36-56,67-74` and `electron-builder.config.cjs:9-21` admit `C:/Renulus/scratch/design-c/delivery/deliveries/pass3/installed-aaaaaaaa/...`; `verify-installed-product.mjs:86-91` rejects it because its first component is `deliveries`. The actual Python guard accepts the never-created path, while the actual JS guard rejects it. | Use the exact base `C:/Renulus/scratch/design-c/delivery` for this cutover, whose installed/matching/proofs paths pass. If the parent selects a named child, narrowly align the verifier's public-artifact grammar before running; preserve the profile/reparse restrictions. This is conditional on the selected root, not a base-root manufacture blocker. |

The complete committed verifier and evidence-root modules were evaluated with
Node's in-memory module loader, then only exported pure guards were called. No
runtime imports or real journey ran. Synthetic environment values remained
beneath this lane's scratch family and were never opened. The positive/negative
controls also verified: exact-base artifact accepted; profile artifact refused;
app profile confined; provider/developer flags stripped; missing installed gates
refused by the aggregate; eight reader gates retained. The module byte hashes
were `18910d7fb64d7284cbc9fac92d01a8e303f38d7da26f6b780af9c65c5c10cf40`
(verifier) and `f5ae9128b01995178d377a71c0cdae28af8b560d5d1a47a26674cc9e1075ff95`
(evidence root). The Python guard hash was
`1daa2fa6b494a33349d1dfd37f81b31c146fb1a185cc671a73fc4ca85470c50e`; its
accepted named target remained absent. Initial audit scaffolding had a quoting
error and an AST-selector error; both were corrected without production changes.

Zeno's W1-W7 retain their historical scope. Relocation is now admitted by the
Python/PowerShell guards, and `eb20e0cf` adds the matching builder root. The
updated verifier uses hidden C readiness/journeys instead of obsolete Flow
navigation; its `completeCoreReceipt` explicitly leaves unexecuted readers,
upgrade/recovery, deletion, ingestion close and native Save gates not-run and
returns incomplete. `prove_offline_helpers.py:94-98` now records actual UTC/date.
These resolve the corresponding source defects; none is a fresh installed or
CPU proof. The old restage wrapper still hardcodes its old source/interpreter
defaults (`restage-delivery.ps1:8,107`); the parent should use the explicit current
Python/direct staging interface documented by Zeno rather than assume those
compatibility paths are usable. `test-installer.ps1:78-95` still requires
`-InstallOnly` to avoid the old native journey.

The source/package contract is coherent at this revision. Actual Git/AST checks
enumerated the builder's admitted snapshot: 5,840 source blobs, no symlink or
non-blob entries, and all 23 runtime SQL files, including Learn002, Cases003,
Study002, Knowledge003 and Assessment003/004/005. The admitted tree includes
the actual new attempts, collection, generation, import and Notes owners.
`stage-backend.py:39-57,66-85,124-151` snapshots committed public source and
refreshes only a generated payload; `stage-delivery.py:243-256` verifies and
copies the admitted public base before source refresh. No application profile
or credentials are snapshot roots. Comparing `f1c49444` with this revision found
no change in Python/desktop manifests and locks or the helper contract. This
supports source-only reuse of a verified payload; it does not validate any
particular local payload.

Before packaging, `stage-delivery.py:275-291` compares backend/renderer/native
revision, refuses an unstaged adoption patch and verifies packaged inventory.
The installed verifier at lines 106-120 and 180-214 compares actual EXE/ASAR/
installer/inventory hashes, each listed file, and every admitted Git source
blob. The final parent freeze must include the executed drivers; their byte
guard at lines 151-168 permits only declared PowerShell checkout line endings.
No actual package inventory or installed executable was opened in this review.
Matching package/install receipts and final-source blob comparison therefore
remain execution gates, not source findings that can be marked passed here.

Rollback preserves an executable and a compatible profile separately.
`storage/database.py:23-41,85-106` stamps schema2 and commits each migration
script independently; DC20's real interruption proved failed-script rollback,
not a whole-profile rollback. Before the first upgrade, the parent must retain
a consistent complete synthetic schema1 snapshot, originals and prior selection,
then rehearse restoring that snapshot before launching the old executable.
An open-WAL file copy or schema2 export is not that snapshot. Preserve later C
writes separately rather than merge them into old schema.
`scripts/prepare_delivery_profile.py:29-42,164-190` intentionally filters to
content/Library and cannot preserve learner/connection state for rollback.
`runtime/protected.py:61-66` binds DPAPI entropy to the resolved profile path;
normal-profile moves or retained-account acceptance remain parent-owned.
`start-renulus.ps1:58-65` CheckOnly does not verify hashes/startup and may leave
profile selection to the packaged fallback if no explicit profile is supplied.

The eight-pass DC20 source proof closes its populated-record/media/deletion
matrix at `4316fde0`; it does not establish final installed interpreter/helper
behavior. Source changes between that baseline and this audit affect delivery
drivers/helper receipt dating and Memory owners. Russell owns restore-to-ordinary
Memory inference acceptance; Poincare owns mounted Notes/help and PDF selected
position. Neither is duplicated here. The remaining matching installed work is
real isolated-runtime/source identity, legacy upgrade/reopen, complete original
recovery and effective local-index rebuild, hidden lifecycle/readers, plus the
separately scoped native/physical and retained-account checks. Parent composes
those receipts and controls cutover. This report closes no DC20/DC21 ticket.

After the audit, Poincare reported disjoint Notes checkpoint
`679c419fbfedca840be9bd5de6ae9e949271d69e`: twelve mounted rights/current-project/
whole-Study context checks and two narrow ZIP deletion/recreation checks passed,
with no Notes product failure. This is the peer's separate source receipt, not
an independent rerun, an `eb20e0cf` installed observation or broad DC20 duplication.
