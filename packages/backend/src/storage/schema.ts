// SPDX-License-Identifier: MIT
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import type { DatabaseSync } from 'node:sqlite';
import { reject } from './contracts.ts';
import type { MigrationInventory, RecordRow, StoragePreview } from './contracts.ts';

export function canonical(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value !== null && typeof value === 'object') return '{' + Object.keys(value).sort().map(
    key => JSON.stringify(key) + ':' + canonical((value as Record<string, unknown>)[key])).join(',') + '}';
  return JSON.stringify(value);
}
export function digest(value: string): string { return createHash('sha256').update(value).digest('hex'); }
export function quote(name: string): string {
  if (!/^[a-z][a-z0-9_]*$/.test(name)) reject('storage_schema_identifier');
  return '"' + name + '"';
}

/** Same inventory construction as server.create_app; never executes source SQL. */
export function loadMigrationInventory(repositoryRoot: string): MigrationInventory {
  const root = join(repositoryRoot, 'runtime', 'renulus');
  const inventory: MigrationInventory = {
    'storage-recovery-001': digest(readFileSync(join(root, 'storage', 'recovery_schema.sql'), 'utf8')),
  };
  for (const module of ['runtime', 'content', 'knowledge', 'retrieval', 'learn', 'cases', 'assessment', 'memory', 'study', 'updates']) {
    const directory = join(root, module);
    const schema = join(directory, 'schema.sql');
    if (existsSync(schema)) inventory[module + '-001'] = digest(readFileSync(schema, 'utf8'));
    const migrations = join(directory, 'migrations');
    if (existsSync(migrations)) for (const name of readdirSync(migrations).filter(name => name.endsWith('.sql')).sort()) {
      inventory[module + '-' + name.slice(0, -4)] = digest(readFileSync(join(migrations, name), 'utf8'));
    }
  }
  return inventory;
}

export function rows(db: DatabaseSync, sql: string, ...parameters: (string | number)[]): RecordRow[] {
  // Unsafe 64-bit integers throw rather than silently lose canonical identity/value precision.
  return db.prepare(sql).all(...parameters).map(row => ({ ...row })) as RecordRow[];
}
export function one(db: DatabaseSync, sql: string, ...parameters: (string | number)[]): RecordRow | undefined {
  return rows(db, sql, ...parameters)[0];
}

export function inventory(db: DatabaseSync, expected: MigrationInventory, expectedSchemaHash?: string): StoragePreview {
  const schemaVersion = Number(one(db, 'PRAGMA user_version')?.user_version);
  const issues: string[] = [];
  if (schemaVersion !== 2) issues.push('storage_schema_unsupported');
  const objects = rows(db, "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name");
  const tables = objects.filter(row => row.type === 'table').map(object => {
    const name = String(object.name), table = quote(name);
    const indexes = rows(db, `PRAGMA index_list(${table})`).map(definition => ({
      definition, columns: rows(db, `PRAGMA index_xinfo("${String(definition.name).replaceAll('"', '""')}")`),
    }));
    return { name, columns: rows(db, `PRAGMA table_xinfo(${table})`), foreignKeys: rows(db, `PRAGMA foreign_key_list(${table})`),
      indexes, rowCount: Number(one(db, `SELECT COUNT(*) AS count FROM ${table}`)?.count) };
  });
  const schemaHash = digest(canonical({ objects, tables: tables.map(({ rowCount: _count, ...table }) => table) }));
  if (expectedSchemaHash !== undefined && schemaHash !== expectedSchemaHash) issues.push('storage_schema_inventory_changed');
  const migrations = objects.some(row => row.name === 'migration_ledger') ?
    rows(db, 'SELECT name,checksum FROM migration_ledger ORDER BY name') as Array<{ name: string; checksum: string }> : [];
  if (!objects.some(row => row.name === 'migration_ledger')) issues.push('storage_migration_ledger_missing');
  for (const row of migrations) {
    if (!Object.hasOwn(expected, row.name)) issues.push('storage_migration_unknown:' + row.name);
    else if (expected[row.name] !== row.checksum) issues.push('storage_migration_changed:' + row.name);
  }
  const applied = new Set(migrations.map(row => row.name));
  const pendingMigrations = Object.keys(expected).filter(name => !applied.has(name)).sort();
  // BF00 cannot migrate a partially installed target while admitting normal commands.
  if (pendingMigrations.length) issues.push('storage_migrations_pending');
  const foreignKeyViolations = rows(db, 'PRAGMA foreign_key_check');
  const integrityCheck = rows(db, 'PRAGMA quick_check').map(row => String(row.quick_check));
  if (foreignKeyViolations.length) issues.push('storage_foreign_key_violation');
  if (integrityCheck.length !== 1 || integrityCheck[0] !== 'ok') issues.push('storage_integrity_failed');
  return { schemaVersion, schemaHash, migrations, pendingMigrations, tables, foreignKeyViolations, integrityCheck,
    compatible: issues.length === 0, issues };
}
