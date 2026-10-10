import { api } from '../../platform/api';
import { stream } from '../../platform/stream';
import { studyHelpHeaders, type ContentReference, type ConversationSummary, type StudyHelpContext } from '../../platform/designC';

export interface SendIntent { text: string; request_id: string }
export interface RunEvent {
  run_id: string; sequence: number; type: string;
  payload: { text?: string; message?: string; code?: string; retryable?: boolean;
    conversation?: ConversationSummary; [key: string]: unknown };
}
export interface ConversationRun {
  run_id: string; state: string; conversation?: ConversationSummary; partial_text?: string;
  error?: {code: string; message: string; retryable: boolean};
}
export const conversationPath = (chat: Pick<ConversationSummary, 'kind' | 'identity'>) =>
  '/conversations/' + chat.kind + '/' + encodeURIComponent(chat.identity.id);

export function createConversation(
  input: {kind?: 'learning' | 'case'; title?: string; temporary?: boolean; project_id?: string | null; teaching_case_id?: string},
  signal?: AbortSignal,
  idempotencyKey: string = crypto.randomUUID(),
  studyHelpContext?: StudyHelpContext,
): Promise<ConversationSummary> {
  return api('/conversations', {method: 'POST', body: input, signal,
    headers: {'Idempotency-Key': idempotencyKey,...studyHelpHeaders(studyHelpContext)}});
}

export interface ChatTestRun {run_id:string;state:'queued'|'running'|'published'|'failed'|'cancelled'}
export interface ChatTestResult {
  test_id:string;version_id:string;item_count:5|10|20;
  study_start:{version:{type:'saved_test_version';id:string};mode:'study';timing:{kind:'untimed'};idempotency_key:string};
}
const chatTestRunPath=(runId:string)=>'/conversations/test-drafts/runs/'+encodeURIComponent(runId);
export function startQuickPractice(input:{text:string;request_id:string;count?:5},signal?:AbortSignal):Promise<ChatTestRun>{
  return api('/conversations/test-drafts',{method:'POST',body:{intent:'quick_practice',...input,count:5},signal});
}
export function startChatTest(conversation:ConversationSummary,input:{expected_revision:number;request_id:string;count:5|10|20;instruction?:string},signal?:AbortSignal,studyHelpContext?:StudyHelpContext):Promise<ChatTestRun>{
  return api(conversationPath(conversation)+'/tests',{method:'POST',body:input,signal,headers:studyHelpHeaders(studyHelpContext)});
}
export function readChatTestRun(runId:string,signal?:AbortSignal):Promise<ChatTestRun>{
  return api(chatTestRunPath(runId),{signal});
}
export function readChatTestResult(runId:string,signal?:AbortSignal,studyHelpContext?:StudyHelpContext):Promise<ChatTestResult>{
  return api(chatTestRunPath(runId)+'/result',{signal,headers:studyHelpHeaders(studyHelpContext)});
}
export function cancelChatTestRun(runId:string,signal?:AbortSignal):Promise<ChatTestRun>{
  return api(chatTestRunPath(runId)+'/cancel',{method:'POST',signal});
}

export async function sendConversation(
  conversation: ConversationSummary,
  input: {text: string; request_id: string; expected_revision: number;
    teaching_style?: 'direct' | 'guided'; topic_id?: string | null; model?: string | null;
    freshness?: boolean; content_refs?: ContentReference[]},
  onEvent: (event: RunEvent) => void,
  signal?: AbortSignal,
  studyHelpContext?: StudyHelpContext,
): Promise<void> {
  for await (const event of stream<RunEvent>(conversationPath(conversation) + '/messages', {
    method: 'POST', body: input, signal, headers: {'Idempotency-Key': input.request_id,...studyHelpHeaders(studyHelpContext)},
  })) onEvent(event.data);
}
