# SPDX-License-Identifier: MIT
"""Projects own goals and membership rows, never chats or Library originals."""
import json

from renulus.contracts import ApiError, durable_id
from renulus.storage.database import utc_now
from renulus.storage.invalidation import bump_context_epoch, context_epoch_in
from renulus.learn.conversation_repository import command, require_assistance


class ProjectRepository:
    def __init__(self, services):
        self.services, self.db = services, services.db

    @property
    def conversations(self):
        return self.services.get('conversations')

    def _get(self, conn, identifier):
        row = conn.execute("SELECT * FROM study_projects WHERE id=? AND lifecycle!='deleted' AND NOT EXISTS "
            "(SELECT 1 FROM deletion_ledger WHERE entity_type='project' AND entity_id=study_projects.id)", (identifier,)).fetchone()
        if not row:
            raise ApiError('project_missing', 'This project is no longer available', 404)
        return dict(row)

    def _expected(self, row, revision):
        if row['revision'] != revision:
            raise ApiError('project_revision_conflict', 'Reload the project before saving', 409, True)

    def _touch(self, conn, identifier):
        conn.execute('UPDATE study_projects SET revision=revision+1,updated_at=? WHERE id=?', (utc_now(), identifier))

    def create(self, request, key=None):
        with self.db.transaction() as conn:
            def create():
                identifier, now = durable_id('project'), utc_now()
                conn.execute('INSERT INTO study_projects VALUES(?,?,?,1,?,?)', (identifier, request.title, 'active', now, now))
                bump_context_epoch(conn)
                return self._get(conn, identifier)
            return command(conn, 'study_project_commands', key, 'create', 'project', 'new', request, create)

    def list(self, limit=50, cursor=None, lifecycle='active'):
        if not 1 <= limit <= 100:
            raise ApiError('invalid_page', 'Use a page size between 1 and 100', 422)
        with self.db.transaction() as conn:
            require_assistance(conn)
            scope = ['projects', lifecycle]
            page = self.conversations._uncursor(cursor, scope) if cursor else {}
            boundary = page.get('boundary') or utc_now()
            where, args = 'lifecycle=? AND updated_at<=?', [lifecycle, boundary]
            if page.get('after'):
                where += ' AND (updated_at,id)<(?,?)'
                args.extend(page['after'])
            rows = [dict(row) for row in conn.execute('SELECT * FROM study_projects WHERE ' + where +
                " AND NOT EXISTS(SELECT 1 FROM deletion_ledger WHERE entity_type='project' AND entity_id=study_projects.id) "
                'ORDER BY updated_at DESC,id DESC LIMIT ?', (*args, limit+1))]
            next_cursor = self.conversations._cursor({'scope': scope, 'boundary': boundary,
                'after': [rows[limit-1]['updated_at'], rows[limit-1]['id']]}) if len(rows)>limit else None
            return {'items': rows[:limit], 'next_cursor': next_cursor}

    def get(self, identifier):
        chats = self.conversations
        with chats._lock, chats.cases._lock, self.db.transaction() as conn:
            require_assistance(conn)
            result = self._get(conn, identifier)
            result['chats'] = []
            for row in conn.execute('SELECT * FROM study_project_chats WHERE project_id=? ORDER BY position,id', (identifier,)):
                try:
                    summary = chats._saved(conn, row['chat_kind'], row['chat_id'])[0]
                except ApiError as error:
                    if error.status == 404:
                        continue
                    raise
                result['chats'].append({**summary, 'membership_id': row['id'], 'position': row['position']})
            result['documents'] = [dict(row) for row in conn.execute(
                'SELECT m.*,d.title,r.status FROM study_project_documents m JOIN knowledge_revisions r ON r.id=m.revision_id '
                'JOIN knowledge_documents d ON d.id=r.document_id WHERE m.project_id=? ORDER BY m.position,m.id', (identifier,))]
            result['goals'] = []
            for row in conn.execute('SELECT * FROM study_project_goals WHERE project_id=? ORDER BY created_at,id', (identifier,)):
                goal = dict(row)
                goal['progress'] = json.loads(goal.pop('progress_json'))
                result['goals'].append(goal)
            return result

    def change(self, identifier, request, operation, key=None):
        with self.db.transaction() as conn:
            def change():
                project = self._get(conn, identifier)
                self._expected(project, request.expected_revision)
                if operation == 'rename':
                    conn.execute('UPDATE study_projects SET title=? WHERE id=?', (request.title, identifier))
                else:
                    conn.execute('UPDATE study_projects SET lifecycle=? WHERE id=?',
                        ('archived' if operation=='archive' else 'active', identifier))
                self._touch(conn, identifier)
                bump_context_epoch(conn)
                return self._get(conn, identifier)
            return command(conn, 'study_project_commands', key, operation, 'project', identifier, request, change)

    def delete(self, identifier, request, key=None):
        with self.db.transaction() as conn:
            def remove():
                self._expected(self._get(conn, identifier), request.expected_revision)
                for table, entity in (('study_project_chats','project_chat'), ('study_project_documents','project_document'),
                                       ('study_project_goals','goal')):
                    for row in conn.execute(f'SELECT id FROM {table} WHERE project_id=?', (identifier,)):
                        self.db.mark_deleted(entity, row['id'], conn)
                conn.execute('DELETE FROM study_projects WHERE id=?', (identifier,))
                self.db.mark_deleted('project', identifier, conn)
                bump_context_epoch(conn)
                return {'id': identifier, 'deleted': True}
            return command(conn, 'study_project_commands', key, 'delete', 'project', identifier, request, remove)

    def move_chat_in(self, conn, kind, identifier, project_id):
        require_assistance(conn)
        chat = self.conversations._saved(conn, kind, identifier)[0]
        if project_id:
            project = self._get(conn, project_id)
            if project['lifecycle'] != 'active':
                raise ApiError('project_archived', 'Restore the project before adding work', 409)
        existing = conn.execute('SELECT * FROM study_project_chats WHERE chat_kind=? AND chat_id=?', (kind, identifier)).fetchone()
        if existing and existing['project_id'] == project_id:
            return chat
        if existing:
            self.db.mark_deleted('project_chat', existing['id'], conn)
            conn.execute('DELETE FROM study_project_chats WHERE id=?', (existing['id'],))
            self._touch(conn, existing['project_id'])
        if project_id:
            position = conn.execute('SELECT COALESCE(MAX(position)+1,0) FROM study_project_chats WHERE project_id=?', (project_id,)).fetchone()[0]
            conn.execute('INSERT INTO study_project_chats VALUES(?,?,?,?,?,1,?)',
                (durable_id('project_chat'), project_id, kind, identifier, position, utc_now()))
            self._touch(conn, project_id)
        bump_context_epoch(conn)
        return self.conversations._saved(conn, kind, identifier)[0]

    def document(self, identifier, request, operation, key=None):
        with self.db.transaction() as conn:
            def change():
                self._expected(self._get(conn, identifier), request.expected_revision)
                existing = conn.execute('SELECT * FROM study_project_documents WHERE project_id=? AND revision_id=?',
                    (identifier, request.revision_id)).fetchone()
                if operation == 'link':
                    row = conn.execute('SELECT r.*,d.scope_kind,d.deleted_at,d.active_revision FROM knowledge_revisions r '
                        'JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=?', (request.revision_id,)).fetchone()
                    if not row or row['deleted_at'] or row['scope_kind']!='personal-library' or row['status']!='ready' or row['active_revision']!=row['id']:
                        raise ApiError('document_unavailable', 'Link a ready document from your Library', 409)
                    if not existing:
                        conn.execute('INSERT INTO study_project_documents VALUES(?,?,?,?,1,?)',
                            (durable_id('project_document'), identifier, request.revision_id, request.position, utc_now()))
                    else:
                        conn.execute('UPDATE study_project_documents SET position=?,revision=revision+1 WHERE id=?', (request.position, existing['id']))
                elif existing:
                    self.db.mark_deleted('project_document', existing['id'], conn)
                    conn.execute('DELETE FROM study_project_documents WHERE id=?', (existing['id'],))
                self._touch(conn, identifier)
                bump_context_epoch(conn)
                return self._get(conn, identifier)
            return command(conn, 'study_project_commands', key, operation, 'project', identifier, request, change)

    def context_in(self, conn, kind, identifier):
        """Resolve links afresh. Producer captures this epoch and checks at publish."""
        require_assistance(conn)
        row = conn.execute('SELECT project_id FROM study_project_chats WHERE chat_kind=? AND chat_id=?', (kind, identifier)).fetchone()
        revisions = []
        if row:
            for source in conn.execute("SELECT r.*,d.reserved FROM study_project_documents m JOIN study_projects p ON p.id=m.project_id "
                "JOIN knowledge_revisions r ON r.id=m.revision_id JOIN knowledge_documents d ON d.id=r.document_id "
                "WHERE m.project_id=? AND p.lifecycle='active' AND d.deleted_at IS NULL AND d.reserved=0 AND d.scope_kind='personal-library' "
                "AND d.active_revision=r.id AND r.status='ready' ORDER BY m.position,m.id", (row['project_id'],)):
                knowledge = self.services.registry.get('knowledge')
                if knowledge and knowledge._eligible(json.loads(source['metadata_json']), json.loads(source['rights_json']), None, False):
                    revisions.append(source['id'])
        return {'project_id': row['project_id'] if row else None, 'revision_ids': revisions, 'context_epoch': context_epoch_in(conn)}
