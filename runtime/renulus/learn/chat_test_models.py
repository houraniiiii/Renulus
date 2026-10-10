# SPDX-License-Identifier: MIT
"""Only explicit volatile test intents cross the Chat API."""
from typing import Annotated, Literal

from pydantic import Field

from renulus.design_c_contracts import Contract, Identifier, Revision, TestVersionIdentity

RequestId = Annotated[str, Field(min_length=8, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')]
TestCount = Literal[5, 10, 20]


class ChatTestRequest(Contract):
    expected_revision: Revision
    request_id: RequestId
    count: TestCount = 5
    instruction: str = Field(default='', max_length=2000)


class QuickPracticeDraftRequest(Contract):
    intent: Literal['quick_practice']
    text: str = Field(min_length=1, max_length=32000)
    request_id: RequestId
    count: Literal[5] = 5


class UntimedStudy(Contract):
    kind: Literal['untimed'] = 'untimed'


class StudyStart(Contract):
    version: TestVersionIdentity
    mode: Literal['study'] = 'study'
    timing: UntimedStudy
    idempotency_key: RequestId


class PublishedChatTest(Contract):
    test_id: Identifier
    version_id: Identifier
    item_count: TestCount


class ChatTestResult(PublishedChatTest):
    study_start: StudyStart


class ChatTestRun(Contract):
    run_id: Identifier
    state: Literal['queued', 'running', 'published', 'failed', 'cancelled']
