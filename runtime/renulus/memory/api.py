"""Feature router; the integration owner applies schema/migrations centrally."""
import asyncio

from fastapi import APIRouter, Query

from .models import Capture, EditFact, ManualFact, Search
from .service import MemoryService


def create_router(services):
    service = services.registry.get('memory')
    if service is None:
        service = services.registry['memory'] = MemoryService(services)
        services.on_startup.append(service.start)
        services.on_shutdown.append(service.close)
    router = APIRouter(prefix='/memory', tags=['memory'])

    @router.get('/status')
    def status():
        return service.status()

    @router.get('/facts')
    def list_facts():
        return {'records': service.repository.list()}

    @router.post('/facts', status_code=201)
    def add_fact(body: ManualFact):
        return service.add(body)

    @router.get('/facts/{identifier}')
    def get_fact(identifier: str):
        return service.repository.get(identifier)

    @router.patch('/facts/{identifier}')
    def edit_fact(identifier: str, body: EditFact):
        return service.edit(identifier, body.text, body.expected_revision)

    @router.delete('/facts/{identifier}')
    def delete_fact(identifier: str, expected_revision: int = Query(ge=1)):
        return service.delete(identifier, expected_revision)

    @router.get('/facts/{identifier}/history')
    def history(identifier: str):
        return {'history': service.repository.history(identifier)}

    @router.delete('/facts/{identifier}/history')
    def remove_history(identifier: str):
        return service.purge_history(identifier)

    @router.post('/captures', status_code=202)
    def capture(body: Capture):
        return service.enqueue(body.evidence_id, body.scope)

    @router.get('/jobs')
    def jobs():
        return {'jobs': service.repository.jobs()}

    @router.post('/jobs/{identifier}/cancel')
    async def cancel(identifier: str):
        return await service.cancel(identifier)

    @router.post('/retry')
    async def retry():
        return await service.process_pending(retry=True)

    @router.post('/reindex')
    async def reindex():
        return await asyncio.to_thread(service.reindex)

    @router.post('/search')
    def search(body: Search):
        return service.retrieve(body.query, scope=body.scope, limit=body.limit, budget_chars=body.budget_chars)

    return router
