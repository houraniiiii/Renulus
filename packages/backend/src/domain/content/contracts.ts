// SPDX-License-Identifier: MIT
import type { ObjectValue } from '../assessment/contracts.ts';
/** Validated by the existing content.validation pure engine before this local transaction. */
export interface ContentPackPlan { manifest:ObjectValue; bundle:{topics:ObjectValue[];cases:ObjectValue[];questions:ObjectValue[];sources:ObjectValue[]};sha256:string }
export type ContentCommand =
  | {type:'content.active'} | {type:'content.topics'} | {type:'content.sources'}
  | {type:'content.topic';topicId:string} | {type:'content.case';caseId:string;version:number|null}
  | {type:'content.install';plan:ContentPackPlan}
  | {type:'content.pack.withdraw';packId:string;version:string;reason:string}
  | {type:'content.withdraw';questionId:string;version:number;reason:string;replacementVersion:number|null};
export type ContentResults = {[K in ContentCommand['type']]:ObjectValue};
