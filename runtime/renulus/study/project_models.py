# SPDX-License-Identifier: MIT
from datetime import date

from pydantic import Field
from renulus.design_c_contracts import Contract, Identifier, GoalState
from renulus.learn.conversation_models import Mutation, Rename


class NewProject(Contract):
    title: str = Field(min_length=1, max_length=120)


class DocumentLink(Mutation):
    revision_id: Identifier
    position: int = Field(default=0, ge=0, le=10000)


class GoalInput(GoalState):
    expected_revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=240)
    topic_id: Identifier | None = None
    target_date: date | None = None


class GoalEdit(GoalInput):
    goal_revision: int = Field(ge=1)


class GoalDelete(Mutation):
    goal_revision: int = Field(ge=1)
