// SPDX-License-Identifier: MIT
import { JsonSchema, Schema, SchemaRepresentation } from "effect";
import type { LaunchConfig, WorkerFrame } from "../../../contracts/worker.ts";
import document from "../../../contracts/worker.schema.json" with { type: "json" };

// Pydantic is the source model; Effect consumes its generated 2020-12 schema.
// Fail startup if the pin cannot represent a constraint rather than weakening it.
const frame = SchemaRepresentation.fromJsonSchemaDocument(JsonSchema.fromSchemaDraft2020_12(document), { patterns: "apply" });
const launch = SchemaRepresentation.fromJsonSchemaDocument(JsonSchema.fromSchemaDraft2020_12({
  $defs: document.$defs, $ref: "#/$defs/LaunchConfig",
}), { patterns: "apply" });
// JSON-only representations contain no service-dependent declarations/revivers.
const decode = Schema.decodeUnknownSync(frame as Schema.Decoder<unknown>, { onExcessProperty: "error" });
const decodeLaunch = Schema.decodeUnknownSync(launch as Schema.Decoder<unknown>, { onExcessProperty: "error" });

export function decodeWorkerFrame(value: unknown): WorkerFrame { return decode(value) as WorkerFrame; }
export function decodeWorkerLaunch(value: unknown): LaunchConfig { return decodeLaunch(value) as LaunchConfig; }

export function canonicalJson(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "boolean" || typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number" && Number.isFinite(value) && Number.isSafeInteger(value)) return String(value);
  if (Array.isArray(value)) return "[" + value.map(canonicalJson).join(",") + "]";
  if (typeof value === "object" && Object.getPrototypeOf(value) === Object.prototype)
    return "{" + Object.keys(value).sort().map(key => JSON.stringify(key) + ":" + canonicalJson((value as Record<string, unknown>)[key])).join(",") + "}";
  throw new Error("worker_invalid_json");
}
