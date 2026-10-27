// SPDX-License-Identifier: MIT
// Mirrors the records-only policy in runtime/renulus/storage/backup.py.
import type { DatabaseSync } from 'node:sqlite';
import { reject } from './contracts.ts';
import type { CanonicalExport, RecordRow } from './contracts.ts';
import { one, quote, rows } from './schema.ts';

const PREFIXES = ['content_', 'learn_', 'case_', 'cases_', 'assessment_', 'memory_', 'study_', 'knowledge_', 'library_', 'update_'];
const COMMON = new Set(['learning_evidence', 'deletion_ledger', 'preferences', 'conversation_commands']);
const SAFE_PREFERENCES = ['study.goals', 'memory.enabled', 'learn.teaching_style', 'home.preferences', 'nightly.preferences'];
export const DELETION_NOTICE = 'This backup carries only deletion markers known at its export date. On a new installation it cannot know later deletions. Restoring merges records and preserves newer deletion markers available in this profile. Derived indexes must be rebuilt using installed offline helpers.';
const CATALOGUE_OMISSION = 'Acquisition catalogue is input metadata tied to external collection paths; retained library metadata remains in knowledge_documents and knowledge_revisions.';
const EXTRACTION_OMISSION = 'Structured extraction documents are rebuildable from retained originals; canonical passage text, headings and physical source locators are retained.';
const CASE_ORIGINAL_OMISSION = 'Records-only export retains case attachment metadata. Original bytes require a full backup including originals.';
export function eligibleTable(name: string): boolean {
  return /^[a-z][a-z0-9_]*$/.test(name) && (COMMON.has(name) || PREFIXES.some(prefix => name.startsWith(prefix))) &&
    name !== 'knowledge_catalogue' && !/(?:^|_)(?:credentials?|secrets?|connections?|provider_settings|index(?:es)?)(?:_|$)/.test(name);
}
function exists(db: DatabaseSync, name: string): boolean {
  return !!one(db, "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", name);
}
function portable(row: RecordRow): RecordRow {
  for (const [key, value] of Object.entries(row)) {
    if (!(value === null || typeof value === 'string' || typeof value === 'number' && Number.isFinite(value))) reject('backup_records');
    if (key.endsWith('_path')) row[key] = null;
  }
  return row;
}
export function page(db: DatabaseSync, name: string, offset: number, limit: number): { rows: RecordRow[]; nextOffset: number | null } {
  if (!eligibleTable(name) || !exists(db, name)) reject('backup_table');
  if (name === 'case_attachment_parts') return { rows: [], nextOffset: null };
  let projection = '*';
  const columns = rows(db, `PRAGMA table_info(${quote(name)})`);
  if (name === 'knowledge_revisions') projection = columns.map(column => column.name === 'extraction_json' ? 'NULL AS extraction_json' : quote(String(column.name))).join(',');
  const parameters: (string | number)[] = [];
  let where = '';
  if (name === 'preferences') {
    where = ' WHERE key IN (' + SAFE_PREFERENCES.map(() => '?').join(',') + ')';
    parameters.push(...SAFE_PREFERENCES);
  }
  const pk = columns.filter(column => Number(column.pk) > 0).sort((a, b) => Number(a.pk) - Number(b.pk));
  const order = name === 'knowledge_source_status_events' ? 'rowid' : pk.length ? pk.map(column => quote(String(column.name))).join(',') : 'rowid';
  const result = rows(db, `SELECT ${projection} FROM ${quote(name)}${where} ORDER BY ${order} LIMIT ? OFFSET ?`, ...parameters, limit + 1, offset);
  const hasMore = result.length > limit;
  if (hasMore) result.pop();
  const portableRows = result.map(portable);
  if (Buffer.byteLength(JSON.stringify(portableRows), 'utf8') > 16 * 1024 * 1024) reject('backup_limit');
  return { rows: portableRows, nextOffset: hasMore ? offset + limit : null };
}
export function exportRecords(db: DatabaseSync): CanonicalExport {
  const records: Record<string, RecordRow[]> = {};
  let count = 0, bytes = 0;
  for (const { name } of rows(db, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")) {
    if (typeof name !== 'string' || !eligibleTable(name)) continue;
    records[name] = [];
    let offset: number | null = 0;
    while (offset !== null) {
      const result = page(db, name, offset, 100);
      for (const row of result.rows) {
        count++; bytes += Buffer.byteLength(JSON.stringify(row), 'utf8') + 1;
        if (count > 100000 || bytes > 16 * 1024 * 1024) reject('backup_limit');
        records[name].push(row);
      }
      offset = result.nextOffset;
    }
  }
  const omissions: CanonicalExport['omissions'] = { knowledge_catalogue: {
    records: exists(db, 'knowledge_catalogue') ? Number(one(db, 'SELECT COUNT(*) AS n FROM knowledge_catalogue')?.n) : 0,
    reason: CATALOGUE_OMISSION,
  } };
  if (exists(db, 'knowledge_revisions')) omissions.knowledge_extractions = {
    records: Number(one(db, 'SELECT COUNT(*) AS n FROM knowledge_revisions WHERE extraction_json IS NOT NULL')?.n), reason: EXTRACTION_OMISSION,
  };
  if (exists(db, 'case_attachments')) omissions.case_originals = {
    records: Number(one(db, 'SELECT COUNT(*) AS n FROM case_attachments')?.n), reason: CASE_ORIGINAL_OMISSION,
  };
  return { format: 'renulus-canonical-export', format_version: 1, schema_version: 2, exported_at: utcNow(),
    data_kind: 'records-only', records, artifacts: {}, limits: DELETION_NOTICE, omissions };
}
export function utcNow(): string { return new Date().toISOString().replace('Z', '+00:00'); }
