# SPDX-License-Identifier: MIT
"""Scalar Study receipts are validated by their canonical assessment owner."""
import json
from typing import Literal

from pydantic import Field, ValidationError

from renulus.contracts import ApiError
from renulus.design_c_contracts import Contract, Identifier


class StudyHelpContext(Contract):
    attempt_id: Identifier
    item_id: Identifier
    version_id: Identifier
    draft_revision: int = Field(ge=0, strict=True)
    policy_revision: int = Field(ge=1, strict=True)
    kind: Literal['hint', 'sources', 'notes', 'chat']


def parse_context(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 2048:
        raise ApiError('invalid_study_context', 'Open help from the current Study question.', 422)
    try:
        def unique(pairs):
            result = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError('Duplicate context field')
                result[key] = item
            return result
        return StudyHelpContext.model_validate(json.loads(value, object_pairs_hook=unique))
    except (ValueError, ValidationError, TypeError):
        raise ApiError('invalid_study_context', 'Open help from the current Study question.', 422) from None


def require_context_in(services, conn, context):
    owner = services.registry.get('whole_attempts')
    if owner is None:
        raise ApiError('study_help_unavailable', 'Study help is not ready in this app.', 503, True)
    return owner.require_help_context_in(conn, context.model_dump(mode='json'))
