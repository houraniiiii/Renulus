# SPDX-License-Identifier: MIT
"""Design C context actions keep the original Case owner and Save boundary."""
from copy import deepcopy
import sqlite3

from renulus.cases.models import EditCase
from renulus.contracts import ApiError
from renulus.storage.database import utc_now
from renulus.storage.invalidation import bump_context_epoch

from .conversation_repository import command, require_assistance


class ConversationCases:
    def __init__(self, conversations):
        self.conversations = conversations
        self.cases = conversations.cases
        self.db = conversations.db

    def context(self, identifier):
        with self.conversations._lock, self.cases._lock, self.db.transaction() as conn:
            require_assistance(conn)
            self.conversations._get(conn, 'case', identifier)
            view = self.cases.get(identifier)
            view.pop('messages')
            return view

    def change(self, identifier, request, operation, key=None):
        repository, cases = self.conversations, self.cases
        session = before = metadata = metadata_before = preview = None
        preview_state = None
        with repository._lock, cases._lock:
            try:
                # Deferred callbacks run only after the outer transaction commits.
                with cases.defer_context_invalidation(), self.db.transaction() as conn:
                    require_assistance(conn)
                    temporary = repository._temporary.get(('case', identifier))

                    def mutate():
                        nonlocal session, before, metadata, metadata_before, preview, preview_state
                        summary, metadata = repository._get(conn, 'case', identifier)
                        repository._expected(summary, request.expected_revision)
                        if summary['lifecycle'] != 'active':
                            raise ApiError('conversation_archived', 'Restore this conversation to change its context', 409)
                        session = cases._load(identifier)
                        cases._check_revision(session, request.case_revision)
                        cases._check_idle(session)
                        before = deepcopy(session.__dict__)
                        if temporary:
                            metadata_before = deepcopy(metadata)
                        if operation == 'context-edit':
                            cases.edit(identifier, EditCase(revision=request.case_revision, text=request.text))
                        elif operation == 'teaching-reveal':
                            cases.reveal(identifier, request.case_revision)
                        elif operation == 'attachment-remove':
                            cases.remove_attachment(identifier, request.attachment_id, request.case_revision)
                        else:
                            previews = repository.services.get('case_previews')
                            preview = previews.jobs.get(request.preview_id)
                            if preview is None or preview.case_id != identifier:
                                raise ApiError('case_preview_not_found', 'Prepare an attachment for this case', 404)
                            preview_state = preview.state
                            if operation == 'preview-apply':
                                previews.apply(request.preview_id, request.case_revision, request.text)
                            elif operation == 'preview-keep':
                                previews.keep(request.preview_id, request.case_revision)
                            else:
                                raise ValueError('Unknown Case action')
                        if temporary:
                            metadata['summary'].update(revision=summary['revision'] + 1, updated_at=session.updated_at)
                            updated = deepcopy(metadata['summary'])
                        else:
                            cases.save(identifier, session.revision, conn=conn)
                            conn.execute('UPDATE case_conversations SET revision=revision+1,updated_at=? WHERE case_id=?',
                                (utc_now(), identifier))
                            bump_context_epoch(conn)
                            updated = repository._saved(conn, 'case', identifier)[0]
                        # Never copy Case text, original bytes or full history into a ledger.
                        return {'conversation': updated, 'case_revision': session.revision}

                    if temporary:
                        return repository._volatile_command(key, operation, 'case', identifier, request, mutate)
                    return command(conn, 'conversation_commands', key, operation, 'case', identifier, request, mutate)
            except BaseException as error:
                if session is not None and before is not None:
                    session.__dict__.clear()
                    session.__dict__.update(before)
                if metadata_before is not None:
                    metadata.clear()
                    metadata.update(metadata_before)
                if preview is not None and preview_state is not None:
                    preview.state = preview_state
                if isinstance(error, sqlite3.Error):
                    raise ApiError('case_save_failed', 'The Case could not be saved. Your context and attachment preview are kept.', 503, True) from None
                raise
