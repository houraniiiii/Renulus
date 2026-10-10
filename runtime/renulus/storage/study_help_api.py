# SPDX-License-Identifier: MIT
"""Prepare one public question only after recorded Study exposure."""
from fastapi import APIRouter

from .study_help import StudyHelpContext, require_context_in


def create_router(services):
    router = APIRouter(prefix='/study', tags=['study-help'])

    @router.post('/help-context')
    def prepare(body: StudyHelpContext):
        with services.db.transaction() as conn:
            require_context_in(services, conn, body)
            owner = services.get('whole_attempts')
            row = owner._row(conn, body.attempt_id)
            version = owner._version(row)
            item = next(item for item in version.items if item.item_id == body.item_id)
            text = item.stem + chr(10) * 2 + chr(10).join(option.id + '. ' + option.text for option in item.options)
            return {'context': body.model_dump(mode='json'), 'seed_text': text}

    return router
