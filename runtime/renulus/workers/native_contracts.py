"""Host-authenticated Knowledge I/O. No command can name a filesystem path."""
from typing import Annotated, Literal, Union
from pydantic import Field
from .contract_base import Model, Id, Digest, Size, PathString, OutputGrant


class NativePaths(Model):
    # Immutable launch authority, never a model/tool input.
    originals_root: PathString
    budget_root: PathString
    grants_root: PathString
    grant_token_sha256: Digest


class NativeIntent(Model):
    intent_id: Id
    reservation_id: Id
    revision_id: Id
    bytes: Annotated[int, Field(ge=1, le=64 * 1024 * 1024)]
    sha256: Digest
    stamp: Annotated[str, Field(min_length=1, max_length=256)]
    media_type: Annotated[str, Field(min_length=1, max_length=160)]


class NativePin(Model):
    revision_id: Id
    original_handle: Id
    bytes: Annotated[int, Field(ge=1, le=64 * 1024 * 1024)]
    sha256: Digest
    media_type: Annotated[str, Field(min_length=1, max_length=160)]


class NativePosition(Model):
    page: Annotated[int, Field(ge=1, le=300)] = 1
    sheet: Annotated[str, Field(max_length=120)] | None = None
    first_row: Annotated[int, Field(ge=1, le=100000)] = 1
    row_limit: Annotated[int, Field(ge=1, le=200)] = 100


class NativeReserve(Model):
    action: Literal['reserve']
    intent: NativeIntent
    output: OutputGrant


class NativeSelection(Model):
    action: Literal['read_selection']
    handle: Id
    intent: NativeIntent
    output: OutputGrant


class NativeBody(Model):
    artifact_handle: Id
    artifact_revision: Annotated[int, Field(ge=1, le=9007199254740991)]
    offset: Size
    length: Size


class NativePublish(NativeBody):
    action: Literal['publish']
    intent: NativeIntent
    output: OutputGrant


class NativeSettle(Model):
    action: Literal['settle']
    intent: NativeIntent
    state: Literal['prepared', 'original', 'ready', 'failed']
    output: OutputGrant


class NativeRead(Model):
    action: Literal['read']
    pin: NativePin
    output: OutputGrant


class NativePayload(NativeBody):
    action: Literal['payload']
    pin: NativePin
    position: NativePosition
    output: OutputGrant


class NativeAsset(NativeBody):
    action: Literal['asset']
    pin: NativePin
    position: NativePosition
    asset_id: Annotated[str, Field(min_length=1, max_length=160)]
    output: OutputGrant


class NativeHandoff(Model):
    action: Literal['handoff']
    pin: NativePin
    operation: Literal['open', 'save']
    destination_handle: Id | None
    output: OutputGrant


class NativeMeasure(Model):
    action: Literal['measure']
    output: OutputGrant


class NativeRetire(Model):
    action: Literal['retire']
    candidate_id: Id
    output: OutputGrant


NativeInput = Annotated[Union[NativeReserve, NativeSelection, NativePublish, NativeSettle,
    NativeRead, NativePayload, NativeAsset, NativeHandoff, NativeMeasure, NativeRetire], Field(discriminator='action')]
