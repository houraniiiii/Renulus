# SPDX-License-Identifier: MIT
from typing import Literal
from fastapi import APIRouter, Depends, Header, Query, Response
from renulus.learn.conversation_models import Mutation, Rename
from .project_models import NewProject, DocumentLink, GoalInput, GoalEdit, GoalDelete
from .project_repository import ProjectRepository


def create_router(services):
    repository = ProjectRepository(services)
    services.registry['projects'] = repository
    def no_store(response: Response):
        response.headers['Cache-Control'] = 'no-store'
    router = APIRouter(prefix='/study/projects', tags=['projects'], dependencies=[Depends(no_store)])

    @router.post('', status_code=201)
    def create(body: NewProject, idempotency_key: str | None = Header(default=None)):
        return repository.create(body, idempotency_key)

    @router.get('')
    def list_projects(limit: int = Query(default=50, ge=1, le=100), cursor: str | None = Query(default=None, max_length=2048),
                      lifecycle: Literal['active','archived']='active'):
        return repository.list(limit, cursor, lifecycle)

    @router.get('/{identifier}')
    def get(identifier: str):
        return repository.get(identifier)

    @router.patch('/{identifier}')
    def rename(identifier: str, body: Rename, idempotency_key: str | None = Header(default=None)):
        return repository.change(identifier, body, 'rename', idempotency_key)

    @router.post('/{identifier}/archive')
    def archive(identifier: str, body: Mutation, idempotency_key: str | None = Header(default=None)):
        return repository.change(identifier, body, 'archive', idempotency_key)

    @router.post('/{identifier}/restore')
    def restore(identifier: str, body: Mutation, idempotency_key: str | None = Header(default=None)):
        return repository.change(identifier, body, 'restore', idempotency_key)

    @router.delete('/{identifier}')
    def delete(identifier: str, expected_revision: int = Query(ge=1), idempotency_key: str | None = Header(default=None)):
        return repository.delete(identifier, Mutation(expected_revision=expected_revision), idempotency_key)

    @router.put('/{identifier}/documents')
    def link(identifier: str, body: DocumentLink, idempotency_key: str | None = Header(default=None)):
        return repository.document(identifier, body, 'link', idempotency_key)

    @router.delete('/{identifier}/documents/{revision_id}')
    def unlink(identifier: str, revision_id: str, expected_revision: int = Query(ge=1), idempotency_key: str | None = Header(default=None)):
        return repository.document(identifier, DocumentLink(expected_revision=expected_revision,revision_id=revision_id), 'unlink', idempotency_key)

    @router.post('/{identifier}/goals',status_code=201)
    def create_goal(identifier: str, body: GoalInput, idempotency_key: str | None = Header(default=None)):
        return repository.goal(identifier,body,'create-goal',key=idempotency_key)

    @router.put('/{identifier}/goals/{goal_id}')
    def edit_goal(identifier: str, goal_id: str, body: GoalEdit, idempotency_key: str | None = Header(default=None)):
        return repository.goal(identifier,body,'edit-goal',goal_id,idempotency_key)

    @router.delete('/{identifier}/goals/{goal_id}')
    def delete_goal(identifier: str, goal_id: str, expected_revision: int = Query(ge=1), goal_revision: int = Query(ge=1),
                    idempotency_key: str | None = Header(default=None)):
        return repository.goal(identifier,GoalDelete(expected_revision=expected_revision,goal_revision=goal_revision),'delete-goal',goal_id,idempotency_key)

    return router
