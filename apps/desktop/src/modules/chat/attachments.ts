import { api } from '../../platform/api';
import { studyHelpHeaders, type ContentReference, type ConversationIdentity, type ConversationSummary, type StudyHelpContext } from '../../platform/designC';
import { importOptionsHeader } from '../library/file-formats';
import type { Rights } from '../library/types';

export interface AttachmentIntent {file:File;request_id:string}
export interface Attachment {
  id:string;title:string;filename:string;revision:number;reference:ContentReference;
  conversation_revision:number;retention:'saved'|'temporary';
  access?:{allowed:boolean;reason?:string};
}
export interface AttachmentInventory {
  conversation:ConversationIdentity;conversation_revision:number;policy_revision:number;context_epoch:number;items:Attachment[];
}
export interface AttachmentCommand {
  conversation:ConversationIdentity;expected_conversation_revision:number;expected_policy_revision:number;
  expected_context_epoch:number;idempotency_key:string;filename:string;title:string;rights:Rights;
  metadata:{source_id:string;source_owner:string;access_class:string;edition:string|null};
}
export function attachmentInventory(chat:ConversationSummary,signal?:AbortSignal,studyHelpContext?:StudyHelpContext):Promise<AttachmentInventory>{
  return api('/attachments/'+chat.kind+'/'+encodeURIComponent(chat.identity.id),{signal,headers:studyHelpHeaders(studyHelpContext)});
}
export function uploadAttachment(file:File,command:AttachmentCommand,signal?:AbortSignal,studyHelpContext?:StudyHelpContext):Promise<Attachment>{
  return api('/attachments',{method:'POST',body:file,signal,headers:{'x-renulus-attachment-options':importOptionsHeader(command),...studyHelpHeaders(studyHelpContext)}});
}
