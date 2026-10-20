"""HANDLE-based NTFS stream metadata, never stream read/delete authority.

Enumeration is a point-in-time observation, not a cross-stream mutation fence.
Directory streams are included. Named-stream allocation is NTFS-reported and may
be conservative for sparse/compressed streams; default-stream accounting uses
filesystem._info's physical allocation. No stream is opened by name.
"""
from __future__ import annotations

from dataclasses import dataclass
from . import filesystem as fs


@dataclass(frozen=True)
class StreamInfo:
    name: str
    logical_bytes: int
    allocated_bytes: int


def enumerate_streams(handle):
    return tuple(StreamInfo(*item) for item in fs._stream_metadata(handle))


def total_data_allocation(handle):
    """Default physical allocation plus conservative named-stream allocation."""
    info = fs._info(handle)
    streams = enumerate_streams(handle)
    named = [item for item in streams if item.name != '::$DATA']
    return {'streams': streams,
            'logical_bytes': (0 if info.directory else info.logical_bytes) + sum(item.logical_bytes for item in named),
            'allocated_bytes': (0 if info.directory else info.allocated_bytes) + sum(item.allocated_bytes for item in named)}


def refuse_named_streams(handle):
    streams = enumerate_streams(handle)
    if (fs._info(handle).directory and streams or any(item.name != '::$DATA' for item in streams)):
        raise fs.FilesystemError('named_stream_hold', 'Named data streams are unreviewed; preserve every stream unchanged')
    return streams
