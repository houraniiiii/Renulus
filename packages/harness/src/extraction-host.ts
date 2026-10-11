// SPDX-License-Identifier: MIT
import type { DomainBinding } from './domain-ipc.ts';

export interface ExtractionInput {
  readonly configuration_id: string;
  readonly binding: DomainBinding;
  readonly system: string;
  readonly user: string;
}
export interface ExtractionResult {
  readonly text: string;
  readonly receipt: Readonly<{ dispatch_id: string; permit_id: string }>;
}
export interface ExtractionFailure {
  readonly code: string;
  readonly status: number;
  readonly retryable: boolean;
}
export type ExtractionReply = ExtractionResult | { readonly failure: ExtractionFailure };
interface NativeOwner {
  status(): Promise<{ state: string; configurationId?: string }>;
  close(input?: { timeoutMs?: number }): Promise<{ state: string; outcome: string }>;
  settled(): Promise<void>;
  inspect(): Promise<unknown>;
}
interface Invocation {
  readonly controller: AbortController;
  readonly task: Promise<ExtractionReply>;
  settled: boolean;
}
const identifier = (value: unknown): value is string => typeof value === 'string' &&
  value.length <= 256 && /^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(value);

/** Stateless inference owns the same store lifetime without creating a transcript. */
export function withStatelessExtractions<T extends NativeOwner>(host: T,
  generate: (binding: DomainBinding, input: Readonly<{ system: string; user: string }>, signal: AbortSignal) => Promise<ExtractionReply>,
  bounds: Readonly<{ maxOperations: number; maxInputChars: number }>) {
  if (!Number.isSafeInteger(bounds.maxOperations) || bounds.maxOperations < 1 ||
      !Number.isSafeInteger(bounds.maxInputChars) || bounds.maxInputChars < 1) throw new Error('invalid_extraction_bounds');
  const operations = new Map<string, Invocation>();
  let closing: Promise<void> | undefined;
  let sealed = false;
  const beginClose = () => {
    sealed = true;
    for (const operation of operations.values()) operation.controller.abort();
    return closing ??= (async () => {
      await Promise.allSettled([...operations.values()].map(operation => operation.task));
      await host.close({ timeoutMs: 0 });
      await host.settled();
    })();
  };
  return { ...host,
    extract(input: ExtractionInput): Promise<ExtractionReply> {
      try {
        if (sealed) throw new Error('harness_closing');
        if (!input || Object.keys(input).sort().join(',') !== 'binding,configuration_id,system,user' ||
            !input.binding || Object.keys(input.binding).sort().join(',') !== 'attempt_id,cancellation_id,input_id,operation_id,session_id' ||
            !Object.values(input.binding).every(identifier) || !identifier(input.configuration_id) ||
            input.binding.operation_id !== input.binding.cancellation_id ||
            typeof input.system !== 'string' || !input.system.trim() ||
            typeof input.user !== 'string' || !input.user.trim() ||
            input.system.length + input.user.length > bounds.maxInputChars) throw new Error('invalid_payload');
        const key = input.binding.operation_id;
        if (operations.has(key)) throw new Error('memory_extraction_identity_conflict');
        if (operations.size >= bounds.maxOperations) throw new Error('memory_extraction_capacity');
        const binding = Object.freeze({ ...input.binding });
        const configurationId = input.configuration_id;
        const text = Object.freeze({ system: input.system, user: input.user });
        const controller = new AbortController();
        // Register synchronously; close must also own work queued before its first await.
        const operation: Invocation = { controller, settled: false, task: Promise.resolve().then(async () => {
          const status = await host.status();
          if (sealed || controller.signal.aborted) throw new Error('harness_closing');
          if (status.state !== 'ready' || status.configurationId !== configurationId) throw new Error('configuration_mismatch');
          try {
            const result = await generate(binding, text, controller.signal);
            if (controller.signal.aborted || sealed) return { failure: { code: 'memory_capture_cancelled', status: 409, retryable: false } };
            if ('failure' in result) {
              if (!result.failure || Object.keys(result.failure).sort().join(',') !== 'code,retryable,status' ||
                  !identifier(result.failure.code) || !Number.isSafeInteger(result.failure.status) ||
                  result.failure.status < 100 || result.failure.status > 599 || typeof result.failure.retryable !== 'boolean')
                throw new Error('memory_extraction_failed');
              return Object.freeze({ failure: Object.freeze({ ...result.failure }) });
            }
            if (typeof result?.text !== 'string' ||
                !result.text.trim() || result.text.length > 16000 || !result.receipt ||
                Object.keys(result.receipt).sort().join(',') !== 'dispatch_id,permit_id' ||
                !Object.values(result.receipt).every(identifier)) throw new Error('memory_extraction_failed');
            return Object.freeze({ text: result.text, receipt: Object.freeze({ ...result.receipt }) });
          } catch { return { failure: controller.signal.aborted || sealed
            ? { code: 'memory_capture_cancelled', status: 409, retryable: false }
            : { code: 'memory_extraction_failed', status: 503, retryable: true } }; }
        }).finally(() => { operation.settled = true; }) };
        operations.set(key, operation);
        void operation.task.catch(() => {});
        return operation.task;
      } catch (error) { return Promise.reject(error); }
    },
    extractionStatus(operationId: string) {
      const operation = operations.get(operationId);
      return { state: !operation ? 'unavailable' : operation.settled ? 'settled' : 'active' };
    },
    async cancelExtraction(operationId: string) {
      const operation = operations.get(operationId);
      if (!operation) return { state: 'unavailable' };
      operation.controller.abort();
      await Promise.allSettled([operation.task]);
      return { state: 'settled' };
    },
    releaseExtraction(operationId: string) {
      const operation = operations.get(operationId);
      if (operation && !operation.settled) throw new Error('memory_extraction_active');
      operations.delete(operationId);
      return { released: true };
    },
    inspect() {
      if (sealed || [...operations.values()].some(operation => !operation.settled)) throw new Error('harness_policy_blocked');
      return host.inspect() as ReturnType<T['inspect']>;
    },
    async close(input: { timeoutMs?: number } = {}) {
      const timeout = input.timeoutMs ?? 5000;
      if (!Number.isFinite(timeout) || timeout < 0) throw new Error('invalid_close_timeout');
      const task = beginClose();
      let timer: ReturnType<typeof setTimeout> | undefined;
      try {
        const done = await Promise.race([task.then(() => true), new Promise<boolean>(resolve => {
          timer = setTimeout(() => resolve(false), timeout);
        })]);
        return done ? { state: 'closed', outcome: 'cancelled_settled' }
          : { state: 'blocked', outcome: 'uncertain_after_disconnect' };
      } finally { if (timer) clearTimeout(timer); }
    },
    settled() { return beginClose(); },
  };
}
