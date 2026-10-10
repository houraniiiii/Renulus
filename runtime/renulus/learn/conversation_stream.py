# SPDX-License-Identifier: MIT
"""Saved command receipts wrap the original Learn/Case producers atomically."""
import asyncio
from contextlib import aclosing
from copy import deepcopy
import json

from renulus.contracts import ApiError, ContextScope, Event, Scope, durable_id
from renulus.storage.database import utc_now
from renulus.storage.invalidation import context_epoch_in
from renulus.storage.assessment_policy import policy_snapshot
from renulus.cases.models import DiscussCase
from renulus.cases.streaming import discuss, sse
from .conversation_repository import command, require_assistance


class ConversationStreams:
    def __init__(self, repository):
        self.repo = repository
        self.active = {}
        self.tasks = {}
        # Remote work cannot resume after process loss; drafts and pins survive.
        with repository.db.transaction() as conn:
            for row in conn.execute(
                    "SELECT idempotency_key,result_json FROM conversation_commands WHERE operation='send'"):
                receipt=json.loads(row['result_json'])
                if receipt.get('state')=='running':
                    receipt.update(state='interrupted',error={'code':'response_interrupted',
                        'message':'The response did not finish. Your draft is retained.','retryable':True})
                    conn.execute('UPDATE conversation_commands SET result_json=? WHERE idempotency_key=?',
                        (json.dumps(receipt),row['idempotency_key']))
        repository.services.on_shutdown.append(self.close)

    def launch(self, entry):
        if entry is not None and entry['saved'] and not entry.get('launched'):
            entry['launched']=True
            entry['queue']=asyncio.Queue(maxsize=64)
            entry['subscribed']=True
            self.tasks[entry['run'].id]=asyncio.create_task(self._drain(entry))

    async def _drain(self, entry):
        try:
            async for encoded in self._produce(entry):
                if entry['subscribed']:
                    queue=entry['queue']
                    # A slow renderer never holds publication or grows a durable log.
                    if queue.full():
                        queue.get_nowait()
                    queue.put_nowait(encoded)
        finally:
            if entry['queue'].full():
                entry['queue'].get_nowait()
            entry['queue'].put_nowait(None)
            self.tasks.pop(entry['run'].id,None)

    async def close(self):
        tasks=list(self.tasks.values())
        for entry in self.active.values():
            entry['shutdown']=True
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks,return_exceptions=True)

    def _receipts(self, conn, kind, identifier, *, run_id=None, limit=101, after=None):
        target_type=self.repo._owner(kind)[3]
        if (kind,identifier) in self.repo._temporary:
            receipts=[(key,result['conversation']['created_at'],result) for key,(_,result) in self.repo._temporary_commands.items()
                if result.get('run_id') and result.get('conversation',{}).get('identity')=={'type':target_type,'id':identifier}
                and (run_id is None or result['run_id']==run_id)]
            return [row for row in sorted(receipts,reverse=True,key=lambda row:row[:2])
                if after is None or (row[1],row[0])<tuple(after)][:limit]
        clauses,parameters=[],[target_type,identifier]
        if run_id is not None:
            clauses.append("json_extract(result_json,'$.run_id')=?")
            parameters.append(run_id)
        if after is not None:
            clauses.append('(created_at,idempotency_key)<(?,?)')
            parameters.extend(after)
        where=' AND '+' AND '.join(clauses) if clauses else ''
        parameters.append(limit)
        return [(row['idempotency_key'],row['created_at'],json.loads(row['result_json'])) for row in conn.execute(
            "SELECT idempotency_key,created_at,result_json FROM conversation_commands WHERE operation='send' AND target_type=? AND target_id=?"
            +where+' ORDER BY created_at DESC,idempotency_key DESC LIMIT ?',parameters)]

    def status(self, kind, identifier, run_id):
        with self.repo._lock,self.repo.db.transaction() as conn:
            entry=self.active.get(run_id)
            receipt=entry['receipt'] if entry and (entry['kind'],entry['id'])==(kind,identifier) else next(
                (value for _,_,value in self._receipts(conn,kind,identifier,run_id=run_id,limit=1)),None)
            if not receipt:
                raise ApiError('conversation_run_missing','This response is no longer available in this chat',404)
            result={'run_id':run_id,'state':receipt['state']}
            if policy_snapshot(conn)['assistance_allowed']:
                summary,_=self.repo._get(conn,kind,identifier)
                result['conversation']=summary
                if receipt.get('error'):
                    result['error']=receipt['error']
                if entry:
                    result['partial_text']=entry.get('output','')
            return result

    def list(self, kind, identifier, limit=20, cursor=None):
        scope=['runs',kind,identifier]
        after=self.repo._uncursor(cursor,scope)['after'] if cursor else None
        with self.repo._lock,self.repo.db.transaction() as conn:
            receipts=self._receipts(conn,kind,identifier,limit=limit+1,after=after)
            page=receipts[:limit]
            return {'items':[{'run_id':r['run_id'],'state':r['state']} for _,_,r in page],
                'next_cursor':self.repo._cursor({'scope':scope,'after':[page[-1][1],page[-1][0]]}) if len(receipts)>limit else None}

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
        if entry['saved']:
            self.launch(entry)
            try:
                while True:
                    event=await entry['queue'].get()
                    if event is None:
                        break
                    yield event
            finally:
                entry['subscribed']=False
            return
        async with aclosing(self._produce(entry)) as producer:
            async for event in producer:
                yield event

    async def _produce(self, entry):
        repo=self.repo
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
                        self._finish(conn,entry,'interrupted' if entry.get('shutdown') else 'cancelled',{'code':'response_interrupted',
                            'message':'The response did not finish. Your draft is retained.','retryable':True})
                except Exception:
                    pass
            self.active.pop(run.id,None)

    async def cancel(self, kind, identifier, run_id):
        entry=self.active.get(run_id)
        if not entry or (entry['kind'],entry['id'])!=(kind,identifier):
            result=self.status(kind,identifier,run_id)
            return {'run_id':run_id,'state':result['state']}
        if kind=='learning':
            await self.repo.learn.cancel(run_id)
        else:
            self.repo.cases.cancel(run_id)
            from renulus.cases.streaming import cancel_provider
            await cancel_provider(self.repo.cases,run_id)
        task=self.tasks.get(run_id)
        if task:
            try:
                await asyncio.wait_for(asyncio.shield(task),timeout=3)
            except asyncio.TimeoutError:
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)
        return {'run_id':run_id,'state':entry['receipt']['state']}
