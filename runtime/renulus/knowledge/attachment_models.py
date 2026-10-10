# SPDX-License-Identifier: MIT
"""Ordinary chat upload commands; clients never choose retention or disk paths."""
from pathlib import PurePosixPath

from pydantic import Field, model_validator

from ..design_c_contracts import Contract, ConversationIdentity, Revision
from .models import Rights, SourceMetadata


class AttachmentCommand(Contract):
    conversation: ConversationIdentity
    expected_conversation_revision: Revision
    expected_policy_revision: int = Field(ge=1, strict=True)
    expected_context_epoch: int = Field(ge=0, strict=True)
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class AttachmentUpload(AttachmentCommand):
    filename: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    rights: Rights
    metadata: SourceMetadata

    @model_validator(mode="after")
    def literal_filename(self):
        if (PurePosixPath(self.filename).name != self.filename
                or any(char in self.filename for char in "\\:/")
                or any(ord(char) < 32 for char in self.filename)
                or self.filename in {".", ".."}):
            raise ValueError("Use a file name without folders or control characters")
        if not self.title.strip():
            raise ValueError("Use a nonempty title")
        return self


class UploadIdentity(Contract):
    command: AttachmentUpload
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bytes: int = Field(gt=0)
    media_type: str


class AttachmentRemoval(AttachmentCommand):
    expected_attachment_revision: Revision
