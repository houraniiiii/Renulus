# SPDX-License-Identifier: MIT
"""Design C context actions keep the original Case owner and Save boundary."""
from copy import deepcopy
import sqlite3

from renulus.cases.models import EditCase, HandoffCase
from renulus.contracts import ApiError
from renulus.storage.database import utc_now
from renulus.storage.invalidation import bump_context_epoch, context_epoch_in

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

    def handoff(self, identifier, request):
        repository, cases = self.conversations, self.cases
        with repository._lock, cases._lock, self.db.transaction() as conn:
            policy = require_assistance(conn)
            epoch = context_epoch_in(conn)
            summary, _ = repository._get(conn, 'case', identifier)
            repository._expected(summary, request.expected_revision)
            if summary['lifecycle'] != 'active':
                raise ApiError('conversation_archived', 'Restore this conversation before starting a handoff', 409)
            if request.target == 'explain' and not request.question.strip():
                raise ApiError('case_question_required', 'Enter a learning question to explain', 422)
            def publish(append):
                # The original producer holds the conversation lock before the
                # Case lock. No provider work happens under these locks.
                session = cases._load(identifier)
                before = deepcopy(session.__dict__)
                metadata = metadata_before = None
                try:
                    with cases.defer_context_invalidation(), self.db.transaction() as snapshot:
                        require_assistance(snapshot, policy)
                        if context_epoch_in(snapshot) != epoch:
                            raise ApiError('dependency_changed', 'The learning context changed. Start another handoff.', 409, True)
                        current, metadata = repository._get(snapshot, 'case', identifier)
                        repository._expected(current, request.expected_revision)
                        if current['retention'] == 'temporary':
                            metadata_before = deepcopy(metadata)
                        append()
                        if current['retention'] == 'saved':
                            cases.save(identifier, session.revision, conn=snapshot)
                            snapshot.execute('UPDATE case_conversations SET revision=revision+1,updated_at=? WHERE case_id=?',
                                (utc_now(), identifier))
                            bump_context_epoch(snapshot)
                        else:
                            metadata['summary'].update(revision=current['revision'] + 1, updated_at=session.updated_at)
                        result = cases._view(session)
                    return result
                except BaseException as error:
                    session.__dict__.clear()
                    session.__dict__.update(before)
                    if metadata_before is not None:
                        metadata.clear()
                        metadata.update(metadata_before)
                    if isinstance(error, sqlite3.Error):
                        raise ApiError('case_save_failed', 'The Case handoff could not be saved. Start another handoff to retry.', 503, True) from None
                    raise
            ticket = cases.handoff(identifier, HandoffCase(revision=request.case_revision,
                target=request.target, question=request.question), publication=publish)
            ticket.pop('case_text')
            return {**ticket, 'conversation': summary['identity'], 'retention': summary['retention']}

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
