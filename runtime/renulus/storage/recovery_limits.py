# SPDX-License-Identifier: MIT
"""Finite format-2 disk, row and metadata budgets, independent of legacy limits."""
from dataclasses import asdict, dataclass

MIB = 1024 * 1024
GIB = 1024 * MIB


@dataclass(frozen=True)
class SegmentedLimits:
    row_bytes: int = 16 * MIB
    segment_bytes: int = 32 * MIB
    canonical_bytes: int = 2 * GIB
    records: int = 1_000_000
    segments: int = 4096
    tables: int = 128
    identifier_bytes: int = 1024
    original_bytes: int = 64 * MIB
    total_original_bytes: int = 8 * GIB
    originals: int = 20_000
    expanded_bytes: int = 8 * GIB
    archive_bytes: int = 8 * GIB
    manifest_bytes: int = 8 * MIB
    directory_bytes: int = 16 * MIB
    graph_edges: int = 8_000_000
    scratch_database_bytes: int = 8 * GIB
    workspace_bytes: int = 32 * GIB

    def public(self):
        return asdict(self)


SEGMENTED_LIMITS = SegmentedLimits()
