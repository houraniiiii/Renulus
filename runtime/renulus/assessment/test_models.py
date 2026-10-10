# SPDX-License-Identifier: MIT
"""Collection commands; origins, quality and publication remain server-owned."""
from typing import Annotated, Literal

from pydantic import Field

from renulus.design_c_contracts import Identifier, QuestionSnapshot, Revision
from .contracts import Command, Selector

Title = Annotated[str, Field(min_length=1, max_length=120)]


class CreateReviewedTestRequest(Command):
    title: Title = "Reviewed practice"
    count: Annotated[int, Field(ge=1, le=50, strict=True)] = 5
    selector: Selector = Field(default_factory=Selector)


class RenameTestRequest(Command):
    expected_revision: Revision
    title: Title


class TestLifecycleRequest(Command):
    expected_revision: Revision


class EditTestVersionRequest(Command):
    expected_revision: Revision
    base_version_id: Identifier
    items: tuple[QuestionSnapshot, ...] = Field(min_length=1, max_length=50)


class QuestionReportRequest(Command):
    item_id: Identifier
    report_text: Annotated[str, Field(min_length=1, max_length=2000)]


Origin = Literal["reviewed_bank", "generated", "imported", "nightly"]
LegacyKind = Literal["reviewed", "generated"]
