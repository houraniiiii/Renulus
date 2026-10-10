# SPDX-License-Identifier: MIT
"""Explicit schema-1 recovery conversion; never guess renamed columns or scopes.

The source inventory is the canonical schema shipped before Design C. New
features use sidecars. Any later added legacy column must receive an explicit
default here, after reviewing its effect on old records. Archive callers verify
the original member's hash and size before invoking these conversions.
"""
import json
from pathlib import Path

from ..contracts import ApiError

READABLE_SCHEMAS = (1, 2)
LEGACY_SCHEMA = json.loads(Path(__file__).with_name("legacy_schema_1.json").read_text(encoding="utf-8"))
# Additions are exact (table, column) mappings; an empty registry deliberately
# refuses unknown changes instead of filling arbitrary SQL defaults.
LEGACY_COLUMN_DEFAULTS = {}


def readable_schema(version):
    return type(version) is int and version in READABLE_SCHEMAS


def convert_legacy_row(name, row, installed_info, source_schema):
    if source_schema != 1:
        return row
    legacy = LEGACY_SCHEMA.get(name)
    if legacy is None or not isinstance(row, dict) or set(row) != {c["name"] for c in legacy}:
        raise ApiError("backup_columns", "The schema-1 record does not match its supported original columns")
    result = dict(row)
    installed = {c["name"] for c in installed_info}
    if set(row) - installed:
        raise ApiError("backup_columns", "A historical record needs an explicitly supported conversion")
    for column in installed - set(row):
        key = (name, column)
        if key not in LEGACY_COLUMN_DEFAULTS:
            raise ApiError("backup_columns", "A historical record needs an explicitly supported column conversion")
        result[column] = LEGACY_COLUMN_DEFAULTS[key]
    return result


def convert_legacy_records(conn, records, source_schema):
    if source_schema != 1:
        return records
    result = {}
    for name, rows in records.items():
        # Only names in the immutable source inventory can reach PRAGMA.
        if name not in LEGACY_SCHEMA or not isinstance(rows, list):
            raise ApiError("backup_table", "The schema-1 export contains an unsupported original table")
        info = list(conn.execute(f'PRAGMA table_info("{name}")'))
        result[name] = [convert_legacy_row(name, row, info, source_schema) for row in rows]
    return result
