# SPDX-License-Identifier: MIT
"""Saved command receipts wrap the original Learn/Case producers atomically."""
import asyncio
from contextlib import aclosing
from copy import deepcopy
import json

from renulus.contracts import ApiError, ContextScope, Event, Scope, durable_id
from renulus.storage.database import utc_now
from renulus.storage.invalidation import context_epoch_in
from renulus.cases.models import DiscussCase
from renulus.cases.streaming import discuss, sse
from .conversation_repository import command, require_assistance


class ConversationStreams:
    def __init__(self, repository):
        self.repo = repository
        self.active = {}

    def _touch(self, conn, entry, *, clear=False):
        repo = self.repo
        if entry['saved']:
            _, sidecar, column, _ = repo._owner(entry['kind'])
            fields = ",draft_text='',draft_refs_json='[]',draft_revision=draft_revision+1" if clear else ''
            conn.execute(f'UPDATE {sidecar} SET revision=revision+1,updated_at=?{fields} WHERE {column}=?',
                         (utc_now(),entry['id']))
            return repo._saved(conn,entry['kind'],entry['id'])[0]
        row = repo._temporary.get((entry['kind'],entry['id']))
        if not row:
            raise ApiError('conversation_missing','This conversation is no longer available',404)
        row['summary']['revision'] += 1
        row['summary']['updated_at'] = utc_now()
        if clear:
            row['draft_text'],row['draft_refs_json'] = '', '[]'
            row['draft_revision'] += 1
        return deepcopy(row['summary'])

    def _guard(self, conn, entry):
        require_assistance(conn, entry['policy'])
        if context_epoch_in(conn)!=entry['epoch']:
            raise ApiError('dependency_changed','The learning context changed. Retry this request.',409,True)
        self.repo._get(conn,entry['kind'],entry['id'])

    def _finish(self, conn, entry, state, error=None):
        if state=='completed':
            self._guard(conn,entry)
        summary = self._touch(conn,entry,clear=state=='completed')
        receipt = {'run_id':entry['run'].id,'state':state,'conversation':summary}
        if error:
            receipt['error'] = error
        if entry['saved']:
            conn.execute('UPDATE conversation_commands SET result_json=? WHERE idempotency_key=?',
                         (json.dumps(receipt),entry['key']))
        else:
            digest,_ = self.repo._temporary_commands[entry['key']]
            self.repo._temporary_commands[entry['key']] = (digest,deepcopy(receipt))
        entry['receipt'] = receipt
        return receipt

    def begin(self, kind, identifier, request, key=None):
        repo = self.repo
        key = key or request.request_id
        if key!=request.request_id or not 8<=len(key)<=128:
            raise ApiError('invalid_idempotency_key','Use the same request ID and request key between 8 and 128 characters',422)
        entry = None
        before = None
        with repo._lock, repo.cases._lock:
            try:
                with repo.db.transaction() as conn:
                    policy = require_assistance(conn)
                    summary,row = repo._get(conn,kind,identifier)
                    saved = summary['retention']=='saved'
                    def start():
                        nonlocal entry,before
                        repo._expected(summary,request.expected_revision)
                        if summary['lifecycle']!='active':
                            raise ApiError('conversation_archived','Restore the conversation before sending',409)
                        if any(e['kind']==kind and e['id']==identifier for e in self.active.values()):
                            raise ApiError('conversation_busy','Stop or finish the current response first',409,True)
                        if saved:
                            repo.validate_refs(conn,request.content_refs)
                        elif request.content_refs:
                            raise ApiError('temporary_content_unavailable','Use temporary case inputs in their original case flow',409)
                        scope = ContextScope(kind=Scope.STUDY,entity_id=identifier) if saved and kind=='learning' else ContextScope(kind=Scope.UNCLASSIFIED)
                        if kind=='learning':
                            _,run = repo.learn.prepare(request.text,scope,identifier if saved else None,
                                request.topic_id,request.teaching_style,'conversation:'+key,conn=conn)
                            messages = None
                            if not saved:
                                run.context = [{'role':m['role'],'content':m['content']} for m in row['messages']]
                                row['messages'].append({'id':durable_id('message'),'run_id':run.id,'role':'user','content':request.text,'created_at':utc_now(),'content_refs':[]})
                            else:
                                conn.execute("UPDATE learn_messages SET citations_json=? WHERE run_id=? AND role='user'",
                                    (json.dumps([{'content_ref':r.model_dump(mode='json')} for r in request.content_refs]),run.id))
                        else:
                            owner = repo.cases.get(identifier)
                            before = deepcopy(repo.cases._sessions[identifier])
                            run,messages = repo.cases.begin_discussion(identifier,DiscussCase(revision=owner['revision'],message=request.text,request_id=request.request_id))
                            run.model = request.model
                            run.policy_revision,run.context_epoch = policy,context_epoch_in(conn)
                            user = repo.cases._sessions[identifier].messages[-1]
                            user.update(run_id=run.id,content_refs=[r.model_dump(mode='json') for r in request.content_refs])
                            if saved:
                                repo.cases.save(identifier,run.revision,conn=conn,allow_active=True)
                        entry = {'kind':kind,'id':identifier,'key':key,'saved':saved,'run':run,'messages':messages,
                            'request':request,'policy':policy,'epoch':context_epoch_in(conn)}
                        if saved:
                            projects = repo.services.registry.get('projects')
                            project = projects.context_in(conn,kind,identifier) if projects else None
                            entry['project'] = project
                            if kind=='learning' and project and project['project_id']:
                                run.revision_ids = project['revision_ids']
                            _,sidecar,column,_ = repo._owner(kind)
                            conn.execute(f'UPDATE {sidecar} SET draft_text=?,draft_refs_json=? WHERE {column}=?',
                                (request.text,json.dumps([r.model_dump(mode='json') for r in request.content_refs]),identifier))
                        else:
                            row['draft_text']=request.text
                        receipt = {'run_id':run.id,'state':'running','conversation':self._touch(conn,entry)}
                        entry['receipt']=receipt
                        if kind=='case':
                            entry['checkpoint']=deepcopy(repo.cases._sessions[identifier])
                        self.active[run.id]=entry
                        if kind=='learning' and saved:
                            run.publication = lambda canonical: self._finish(canonical,entry,'completed')
                        return receipt
                    if saved:
                        receipt=command(conn,'conversation_commands',key,'send',summary['identity']['type'],identifier,request,start)
                    else:
                        receipt=repo._volatile_command(key,'send',kind,identifier,request,start)
            except BaseException:
                if before is not None:
                    repo.cases._sessions[identifier]=before
                if entry:
                    self.active.pop(entry['run'].id,None)
                    repo.learn.active.pop(entry['run'].id,None)
                    repo.cases._runs.pop(entry['run'].id,None)
                raise
        if entry is None and receipt['run_id'] in self.active:
            raise ApiError('conversation_busy','This response is already running',409,True)
        return entry,receipt

    async def events(self, entry, receipt):
        repo = self.repo
        if entry is None:
            state=receipt['state']
            if state=='running':
                state='interrupted'
            payload={**receipt,'replayed':True}
            if state!='completed':
                payload.update(receipt.get('error') or {'code':'response_interrupted','message':'The response did not finish. Your draft is retained.','retryable':True})
            yield sse(Event(run_id=receipt['run_id'],sequence=1,type='completed' if state=='completed' else 'error',payload=payload))
            return
        run,request=entry['run'],entry['request']
        terminal=False
        stream=repo.learn.answer(run,request.text,request.teaching_style,request.topic_id,request.model,freshness=request.freshness) if entry['kind']=='learning' else discuss(repo.cases,run,entry['messages'])
        try:
            async with aclosing(stream):
                async for event in stream:
                    if event.type=='answer.delta':
                        event=event.model_copy(update={'type':'delta'})
                    if event.type=='failed':
                        event=event.model_copy(update={'type':'error','payload':event.payload.get('error',{})})
                    if event.type in ('completed','error','cancelled'):
                        terminal=True
                        with repo._lock,repo.cases._lock:
                            try:
                                with repo.db.transaction() as conn:
                                    if event.type=='completed' and entry['kind']=='case':
                                        self._guard(conn,entry)
                                        session=repo.cases._sessions[entry['id']]
                                        session.messages[-1]['run_id']=run.id
                                        if entry['saved']:
                                            repo.cases.save(entry['id'],session.revision,conn=conn)
                                    if not (event.type=='completed' and entry['saved'] and entry['kind']=='learning'):
                                        if event.type=='completed' and entry['kind']=='learning':
                                            self._guard(conn,entry)
                                            repo._temporary[(entry['kind'],entry['id'])]['messages'].append({
                                                'id':durable_id('message'),'run_id':run.id,'role':'assistant','content':entry.get('output',''),
                                                'created_at':utc_now(),'content_refs':[]})
                                        self._finish(conn,entry,event.type,event.payload if event.type=='error' else None)
                            except Exception as error:
                                if entry['kind']=='case' and entry['id'] in repo.cases._sessions:
                                    repo.cases._sessions[entry['id']]=entry['checkpoint']
                                    repo.cases._sessions[entry['id']].active_run_id=None
                                    run.events.clear()
                                    run.status='failed'
                                code=error.code if isinstance(error,ApiError) else 'conversation_save_failed'
                                message=error.message if isinstance(error,ApiError) else 'The answer could not be saved. Your draft is retained.'
                                event=event.model_copy(update={'type':'error','payload':{'code':code,'message':message,'retryable':True}})
                                try:
                                    with repo.db.transaction() as conn:
                                        self._finish(conn,entry,'error',event.payload)
                                except Exception:
                                    pass  # A deleted owner cannot be recreated by a late receipt.
                        event=event.model_copy(update={'payload':{**event.payload,'conversation':entry['receipt']['conversation']}})
                    else:
                        with repo.db.transaction() as conn:
                            self._guard(conn,entry)
                        if event.type=='delta':
                            entry['output']=entry.get('output','')+event.payload.get('text','')
                        event=event.model_copy(update={'payload':{**event.payload,'conversation':entry['receipt']['conversation']}})
                    yield sse(event)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            code=error.code if isinstance(error,ApiError) else 'conversation_failed'
            message=error.message if isinstance(error,ApiError) else 'The response could not finish. Your draft is retained.'
            yield sse(Event(run_id=run.id,sequence=1000000,type='error',payload={'code':code,'message':message,'retryable':True}))
        finally:
            if not terminal:
                if entry['kind']=='learning':
                    await repo.learn.cancel(run.id)
                else:
                    repo.cases.cancel(run.id)
                    from renulus.cases.streaming import cancel_provider
                    await cancel_provider(repo.cases,run.id)
                try:
                    with repo._lock,repo.cases._lock,repo.db.transaction() as conn:
                        self._finish(conn,entry,'cancelled',{'code':'response_interrupted',
                            'message':'The response did not finish. Your draft is retained.','retryable':True})
                except Exception:
                    pass
            self.active.pop(run.id,None)

    async def cancel(self, kind, identifier, run_id):
        entry=self.active.get(run_id)
        if not entry or (entry['kind'],entry['id'])!=(kind,identifier):
            raise ApiError('conversation_run_missing','This response is no longer active in this chat',404)
        if kind=='learning':
            return await self.repo.learn.cancel(run_id)
        result=self.repo.cases.cancel(run_id)
        from renulus.cases.streaming import cancel_provider
        await cancel_provider(self.repo.cases,run_id)
        return result
