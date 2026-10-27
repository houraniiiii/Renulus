// SPDX-License-Identifier: MIT
import { randomBytes } from "node:crypto";
import { DomainClient, type DomainBinding, type DomainIdentity, type DomainLimits,
  type DomainOutcome } from "../../../harness/src/domain-ipc.ts";

export interface NativeDomainRequest {
  readonly binding: Readonly<DomainBinding>;
  readonly command: string;
  readonly payload: Readonly<Record<string, unknown>>;
  readonly signal: AbortSignal;
}
export type NativeDomainReply = Pick<DomainOutcome, "outcome" | "result" | "error">;

/** Same native callback client and identity checks, within the one Node process.
 * Only the trusted domain/dispatch owner supplies the handler. There is no tool
 * discovery, arbitrary method invocation or second scheduler at this seam.
 */
export function createNativeDomainAdapter(options: {
  identity: Pick<DomainIdentity, "profile_id" | "store_id" | "generation">;
  handle: (request: NativeDomainRequest) => Promise<NativeDomainReply>;
  limits?: DomainLimits;
}) {
  const identity: DomainIdentity = { ...options.identity, protocol: "renulus-harness/1", token: randomBytes(32).toString("hex") };
  const active = new Map<string, { controller: AbortController; settled: Promise<void> }>();
  let client: DomainClient;
  client = new DomainClient(identity, async bytes => {
    const frame = JSON.parse(bytes.toString("utf8")) as Record<string, unknown>;
    if (frame.kind === "domain_cancel") {
      active.get(String(frame.callback_id))?.controller.abort();
      return;
    }
    if (frame.kind !== "domain_request") throw new Error("native_domain_frame_invalid");
    const { kind: _kind, command, payload, ...anchor } = frame;
    const binding = Object.freeze({ operation_id: String(frame.operation_id), attempt_id: String(frame.attempt_id),
      session_id: String(frame.session_id), input_id: String(frame.input_id), cancellation_id: String(frame.cancellation_id) });
    const controller = new AbortController();
    const callbackId = String(frame.callback_id);
    const settled = Promise.resolve().then(async () => {
      let reply: NativeDomainReply;
      try {
        reply = await options.handle({ binding, command: String(command),
          payload: Object.freeze(payload as Record<string, unknown>), signal: controller.signal });
        if (reply.outcome === "accepted_pending" || (reply.result === undefined) === (reply.error === undefined))
          throw new Error("domain_handler_invalid_terminal");
      } catch {
        // A thrown adapter error does not prove that an effect was never sent.
        reply = { outcome: "uncertain_after_disconnect",
          error: { code: "domain_operation_uncertain", status: 503, retryable: false } };
      }
      client.receive({ ...anchor, kind: "domain_result", ...reply });
      if (!client.result(callbackId)) client.receive({ ...anchor, kind: "domain_result", outcome: "uncertain_after_disconnect",
        error: { code: "domain_invalid_terminal", status: 503, retryable: false } });
    }).finally(() => { active.delete(callbackId); });
    active.set(callbackId, { controller, settled });
  }, options.limits);
  let close: Promise<void> | undefined;
  return { domain: client,
    close: () => close ??= (async () => {
      client.seal();
      await Promise.all([...active.values()].map(entry => entry.settled));
      await client.settled();
    })(),
  };
}
