# SPDX-License-Identifier: MIT
"""Parent mounts this router once under /api/v1 after shared generation."""
from typing import Literal

from fastapi import APIRouter, Depends, Response

from .chat_test_models import ChatTestRequest, QuickPracticeDraftRequest
from .chat_test_service import ChatTestService


def create_router(services):
    service = ChatTestService(services)
    services.registry['chat_tests'] = service

    def no_store(response: Response):
        response.headers['Cache-Control'] = 'no-store'

    router = APIRouter(prefix='/conversations', tags=['chat-tests'], dependencies=[Depends(no_store)])

    @router.post('/test-drafts', status_code=202)
    async def quick_practice(body: QuickPracticeDraftRequest):
        return service.start_draft(body)

    @router.post('/{kind}/{identifier}/tests', status_code=202)
    async def chat_test(kind: Literal['learning', 'case'], identifier: str, body: ChatTestRequest):
        return service.start_chat(kind, identifier, body)

    @router.get('/test-drafts/runs/{run_id}')
    async def status(run_id: str):
        return service.status(run_id)

    @router.get('/test-drafts/runs/{run_id}/result')
    async def result(run_id: str):
        return service.result(run_id)

    @router.post('/test-drafts/runs/{run_id}/cancel')
    async def cancel(run_id: str):
        return await service.cancel(run_id)

    return router
