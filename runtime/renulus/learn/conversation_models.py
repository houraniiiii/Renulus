# SPDX-License-Identifier: MIT
"""New chat intent never supplies retention or runtime context scope."""
import base64
import binascii
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from renulus.design_c_contracts import (Contract, CreateConversation, Identifier,
    Revision, ContentReference)


class NewConversation(CreateConversation):
    topic_id: Identifier | None = None
    teaching_style: Literal["direct", "guided"] = "direct"
    text: str = Field(default="", max_length=50000)
    teaching_case_id: Identifier | None = None

    @model_validator(mode="after")
    def correct_owner(self):
        if self.kind == "learning" and (self.text or self.teaching_case_id):
            raise ValueError("Case material belongs to the Case owner")
        if self.teaching_case_id and self.text:
            raise ValueError("Teaching material is pinned from its installed content ID")
        return self


class Mutation(Contract):
    expected_revision: Revision


class Rename(Mutation):
    title: str = Field(min_length=1, max_length=120)


class ProjectMove(Mutation):
    project_id: Identifier | None = None


class CaseMutation(Mutation):
    case_revision: Revision


class CaseHandoffRequest(CaseMutation):
    target: Literal['explain', 'generated-practice']
    question: str = Field(default='', max_length=12000)


class CaseContextEdit(CaseMutation):
    text: str = Field(min_length=1, max_length=50000)


class CasePreviewApply(CaseMutation):
    text: str = Field(min_length=1, max_length=50000)


class CaseAttachmentRemove(CaseMutation):
    attachment_id: Identifier


class CasePreviewKeep(CaseMutation):
    preview_id: Identifier


class CasePreviewText(CasePreviewApply):
    preview_id: Identifier


class InlineLearningImage(Contract):
    type: Literal['image']
    media_type: Literal['image/png', 'image/jpeg', 'image/webp']
    data: str = Field(min_length=1, max_length=11184812)

    @model_validator(mode='after')
    def canonical_bytes(self):
        try:
            decoded = base64.b64decode(self.data, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError('Use canonical inline image base64') from None
        if not decoded or len(decoded) > 8 * 1024 * 1024 or (
                base64.b64encode(decoded).decode('ascii') != self.data):
            raise ValueError('Use a nonempty inline image up to 8 MiB')
        return self


class Send(Mutation):
    text: str = Field(min_length=1, max_length=16000)
    request_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    teaching_style: Literal["direct", "guided"] = "direct"
    topic_id: Identifier | None = None
    model: str | None = Field(default=None, max_length=128)
    freshness: bool | None = None
    content_refs: tuple[ContentReference, ...] = Field(default=(), max_length=20)
    images: tuple[InlineLearningImage, ...] = Field(default=(), max_length=4)
    image_preview_id: Identifier | None = None
    case_revision: Revision | None = None

    @model_serializer(mode='wrap')
    def preserve_text_command_hash(self, serialize):
        result = serialize(self)
        if not self.images:
            result.pop('images', None)
        if self.image_preview_id is None:
            result.pop('image_preview_id', None)
            result.pop('case_revision', None)
        return result

    @model_validator(mode='after')
    def explicit_image(self):
        if sum(len(base64.b64decode(image.data, validate=True)) for image in self.images) > 16 * 1024 * 1024:
            raise ValueError('Inline images must total at most 16 MiB')
        if self.images and self.image_preview_id is not None:
            raise ValueError('Use inline learning images or the original Case preview')
        if (self.image_preview_id is None) != (self.case_revision is None):
            raise ValueError('Image discussion requires both the preview and Case revision')
        if self.image_preview_id and (not self.model or len(self.text) > 11800 or self.content_refs):
            raise ValueError('Select an image model and a question up to 11800 characters without other source references')
        return self
