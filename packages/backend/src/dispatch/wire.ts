// SPDX-License-Identifier: MIT
/** Compare the pre-filter native manifest with the actual native HTTP bytes. No serializer here. */
import { createHash } from 'node:crypto';
import { reject } from '../storage/contracts.ts';
import { canonical } from '../storage/schema.ts';
import type { Route } from './contracts.ts';
export interface SerializedRequest { method: 'POST'; url: string; headers: Readonly<Record<string, string>>; body_base64: string }
export interface NativeManifest {
  version: 1; system: string;
  messages: { role: 'user' | 'assistant' | 'tool'; content: NativePart[] }[];
  tools: { name: string; description: string; parameters_json: string }[];
}
export type NativePart = { type: 'text'; text: string } |
  { type: 'image'; media_type: string; sha256: string; bytes: number; detail: null | 'auto' | 'low' | 'high' } |
  { type: 'tool-call'; id: string; name: string; arguments_json: string } |
  { type: 'tool-result'; id: string; output_text: string };
const denied = (): never => reject('deployment_manifest_mismatch');
// JSON.parse alone silently drops duplicate keys. Bound depth and work and reject ambiguous JSON.
export function parseJson(raw: string): unknown {
  let i = 0, nodes = 0;
  function whitespace() { while (/[\x20\t\r\n]/.test(raw[i] ?? 'x')) i++; }
  function value(depth: number): unknown {
    if (depth > 100 || ++nodes > 100000) return denied(); whitespace();
    if (raw[i] === '"') {
      const start = i++;
      while (i < raw.length) { if (raw[i++] === '\\') { i++; continue; } if (raw[i - 1] === '"') {
        const s = JSON.parse(raw.slice(start, i));
        if (/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(s)) return denied();
        return s;
      } } return denied();
    }
    if (raw[i] === '{') {
      i++; whitespace(); const result: Record<string, unknown> = Object.create(null), keys = new Set<string>();
      if (raw[i] === '}') { i++; return result; }
      for (;;) {
        whitespace(); if (raw[i] !== '"') return denied(); const key = value(depth + 1);
        if (typeof key !== 'string' || keys.has(key)) return denied(); keys.add(key);
        whitespace(); if (raw[i++] !== ':') return denied(); result[key] = value(depth + 1); whitespace();
        if (raw[i] === '}') { i++; return result; } if (raw[i++] !== ',') return denied();
      }
    }
    if (raw[i] === '[') {
      i++; whitespace(); const result: unknown[] = []; if (raw[i] === ']') { i++; return result; }
      for (;;) { result.push(value(depth + 1)); whitespace(); if (raw[i] === ']') { i++; return result; } if (raw[i++] !== ',') return denied(); }
    }
    const token = /^(?:true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/.exec(raw.slice(i))?.[0];
    if (!token) return denied(); i += token.length; const parsed = JSON.parse(token);
    if (typeof parsed === 'number' && (!Number.isFinite(parsed) || Number.isInteger(parsed) && !Number.isSafeInteger(parsed))) return denied(); return parsed;
  }
  try { const result = value(0); whitespace(); if (i !== raw.length) return denied(); return result; } catch { return denied(); }
}
type Obj = Record<string, any>; // Dynamic protocol JSON is checked by fields() before use.
function object(v: unknown): Obj { if (!v || typeof v !== 'object' || Array.isArray(v)) return denied(); return v as Obj; }
function fields(v: unknown, required: string[], optional: string[] = []): Obj {
  const o = object(v); if (!required.every(k => Object.hasOwn(o, k)) || Object.keys(o).some(k => !required.includes(k) && !optional.includes(k))) return denied(); return o;
}
function array(v: unknown): any[] { if (!Array.isArray(v)) return denied(); return v; }
function str(v: unknown): string { if (typeof v !== 'string') return denied(); return v; }
function joinParts(parts: unknown[][]) {
  const result: unknown[][] = [];
  for (const p of parts) { const last = result.at(-1); if (p[0] === 'text' && last?.[0] === 'text') last[1] = String(last[1]) + p[1]; else result.push(p); } return result;
}
function image(url: unknown, detail: unknown): unknown[] {
  const m = /^data:(image\/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)$/.exec(str(url));
  if (!m || ![null, 'auto', 'low', 'high'].includes(detail as null)) return denied();
  const bytes = base64(m[2], 8 * 1024 * 1024);
  return ['image', m[1], createHash('sha256').update(bytes).digest('hex'), bytes.length, detail];
}
export function base64(value: unknown, limit: number): Buffer {
  if (typeof value !== 'string' || value.length > 4 * Math.ceil(limit / 3) || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)) return denied();
  const result = Buffer.from(value, 'base64'); if (!result.length || result.length > limit || result.toString('base64') !== value) return denied(); return result;
}
function wireParts(v: unknown, role: string, responses: boolean): unknown[][] {
  if (typeof v === 'string') return [['text', v]];
  return joinParts(array(v).map(part => {
    const p = object(part), textType = responses ? role === 'user' ? 'input_text' : 'output_text' : 'text';
    if (p.type === textType) { fields(p, ['type', 'text'], responses && role === 'assistant' ? ['annotations'] : []);
      if (p.annotations !== undefined && canonical(p.annotations) !== '[]') return denied(); return ['text', str(p.text)]; }
    if (role === 'user' && p.type === (responses ? 'input_image' : 'image_url')) {
      fields(p, ['type', 'image_url'], responses ? ['detail'] : []);
      const img = responses ? p : fields(p.image_url, ['url'], ['detail']);
      return image(responses ? img.image_url : img.url, img.detail ?? null);
    } return denied();
  }));
}
function expected(manifest: NativeManifest, responses: boolean) {
  fields(manifest, ['version', 'system', 'messages', 'tools']); if (manifest.version !== 1) return denied(); str(manifest.system);
  if (manifest.messages.length > 200 || manifest.tools.length > 128) return denied();
  const events: unknown[] = [], calls = new Set<string>(), results = new Set<string>(), pending = new Set<string>(), features = new Set(['text']);
  for (const m of array(manifest.messages)) {
    fields(m, ['role', 'content']); if (!['user', 'assistant', 'tool'].includes(m.role) || pending.size && m.role !== 'tool') return denied();
    let plain: unknown[][] = []; const tools: unknown[] = [];
    for (const p of array(m.content)) {
      if (p.type === 'text' && m.role !== 'tool') { fields(p, ['type', 'text']); plain.push(['text', str(p.text)]); }
      else if (p.type === 'image' && m.role === 'user') {
        fields(p, ['type', 'media_type', 'sha256', 'bytes', 'detail']); features.add('image');
        if (!/^image\/(png|jpeg|webp)$/.test(p.media_type) || !/^[a-f0-9]{64}$/.test(p.sha256) || !Number.isSafeInteger(p.bytes) || p.bytes < 1 || p.bytes > 8 * 1024 * 1024 || ![null, 'auto', 'low', 'high'].includes(p.detail)) return denied();
        plain.push(['image', p.media_type, p.sha256, p.bytes, p.detail]);
      } else if (p.type === 'tool-call' && m.role === 'assistant') {
        fields(p, ['type', 'id', 'name', 'arguments_json']); features.add('tools');
        if (!str(p.id) || !str(p.name) || calls.has(p.id)) return denied(); calls.add(p.id); pending.add(p.id);
        const call = ['call', p.id, p.name, canonical(parseJson(str(p.arguments_json)))];
        if (responses) { if (plain.length) { events.push(['message', m.role, joinParts(plain)]); plain = []; } events.push(call); } else tools.push(call);
      } else if (p.type === 'tool-result' && m.role === 'tool') {
        fields(p, ['type', 'id', 'output_text']); features.add('tools');
        if (!calls.has(p.id) || results.has(p.id)) return denied(); results.add(p.id); pending.delete(p.id);
        events.push(['result', p.id, str(p.output_text)]);
      } else return denied();
    }
    if (plain.length || m.role === 'user') events.push(['message', m.role, joinParts(plain)]); events.push(...tools);
  }
  if (pending.size || calls.size !== results.size) return denied();
  const names = new Set<string>();
  const schemas = array(manifest.tools).map(t => {
    fields(t, ['name', 'description', 'parameters_json']); features.add('tools');
    if (!str(t.name) || names.has(t.name)) return denied(); names.add(t.name);
    const schema = object(parseJson(str(t.parameters_json))); return [t.name, str(t.description), canonical(schema)];
  });
  return { value: [manifest.system, events, schemas], features: [...features] };
}
function observed(payload: Obj, responses: boolean) {
  fields(payload, ['model', 'stream'], ['tools', 'tool_choice', 'temperature', 'top_p', 'frequency_penalty', 'presence_penalty', 'store',
    'stream_options', 'parallel_tool_calls', 'top_logprobs', 'reasoning', ...(responses ? ['input', 'instructions', 'max_output_tokens', 'text', 'truncation',
      'safety_identifier', 'prompt_cache_key', 'include', 'max_tool_calls', 'service_tier'] : ['messages', 'max_completion_tokens', 'seed', 'stop', 'response_format', 'reasoning_effort', 'logprobs'])]);
  if (payload.store === true || payload.truncation !== undefined && payload.truncation !== 'disabled') return denied();
  const events: unknown[] = []; let system = responses ? str(payload.instructions ?? '') : '';
  for (const [index, value] of array(payload[responses ? 'input' : 'messages']).entries()) {
    const m = object(value), role = m.role;
    if (responses && m.type === 'function_call') { fields(m, ['type', 'call_id', 'name', 'arguments'], ['id', 'status']); events.push(['call', str(m.call_id), str(m.name), canonical(parseJson(str(m.arguments)))]); }
    else if (responses && m.type === 'function_call_output') { fields(m, ['type', 'call_id', 'output'], ['id', 'status']); events.push(['result', str(m.call_id), str(m.output)]); }
    else if (!responses && role === 'tool') { fields(m, ['role', 'tool_call_id', 'content']); const p = wireParts(m.content, role, false);
      if (p.length !== 1 || p[0][0] !== 'text') return denied(); events.push(['result', str(m.tool_call_id), p[0][1]]); }
    else if (!responses && role === 'system' && index === 0) { fields(m, ['role', 'content']); const p = wireParts(m.content, role, false);
      if (p.length !== 1 || p[0][0] !== 'text') return denied(); system = str(p[0][1]); }
    else if (['user', 'assistant'].includes(role) && (!responses || m.type === undefined || m.type === 'message')) {
      fields(m, ['role', 'content'], responses ? ['type', 'id', 'status'] : ['tool_calls', ...(role === 'assistant' ? ['reasoning_content'] : [])]);
      if (m.reasoning_content !== undefined && m.reasoning_content !== '') return denied();
      const parts = m.content === null && role === 'assistant' ? [] : wireParts(m.content, role, responses);
      if (parts.length || role === 'user') events.push(['message', role, parts]);
      if (!responses) for (const call of array(m.tool_calls ?? [])) {
        if (role !== 'assistant') return denied(); fields(call, ['id', 'type', 'function']); const f = fields(call.function, ['name', 'arguments']);
        if (call.type !== 'function') return denied(); events.push(['call', str(call.id), str(f.name), canonical(parseJson(str(f.arguments)))]);
      }
    } else return denied();
  }
  const schemas = array(payload.tools ?? []).map(t => {
    fields(t, responses ? ['type', 'name', 'description', 'parameters'] : ['type', 'function'], responses ? ['strict'] : []);
    if (t.type !== 'function') return denied(); const f = responses ? t : fields(t.function, ['name', 'description', 'parameters'], ['strict']);
    if (f.strict !== undefined && f.strict !== null && f.strict !== false) return denied();
    return [str(f.name), str(f.description), canonical(object(f.parameters))];
  });
  return [system, events, schemas];
}
export function verifyWire(serialized: SerializedRequest, manifest: NativeManifest, route: Route, maxBytes: number, maxOutput: number) {
  fields(serialized, ['method', 'url', 'headers', 'body_base64']);
  if (serialized.method !== 'POST' || serialized.url !== route.endpoint) reject('deployment_request_invalid');
  const allowedHeaders = new Set(['content-type', 'content-length', 'accept', 'user-agent', 'x-opencode-session']);
  const names = new Set<string>();
  for (const [name, value] of Object.entries(object(serialized.headers))) {
    const lower = name.toLowerCase();
    if (!allowedHeaders.has(lower) || names.has(lower) || typeof value !== 'string' || value.length > 256 || /[\r\n]/.test(value)) reject('deployment_request_invalid'); names.add(lower);
  }
  const body = base64(serialized.body_base64, maxBytes);
  for (const [name, value] of Object.entries(serialized.headers)) {
    if (name.toLowerCase() === 'content-length' && value !== String(body.length) ||
        name.toLowerCase() === 'content-type' && value !== 'application/json') reject('deployment_request_invalid');
  }
  const payload = object(parseJson(new TextDecoder('utf-8', { fatal: true }).decode(body)));
  if (payload.model !== route.wire_model_id || payload.stream !== true) reject('deployment_request_invalid');
  const responses = route.protocol === 'openai-responses', output = payload[responses ? 'max_output_tokens' : 'max_completion_tokens'];
  if (!Number.isSafeInteger(output) || output < 1 || output > maxOutput) reject('deployment_output_exceeds_limit');
  const e = expected(manifest, responses);
  if (canonical(e.value) !== canonical(observed(payload, responses))) return denied();
  return { body, body_sha256: createHash('sha256').update(body).digest('hex'), body_bytes: body.length,
    output_tokens: output as number, features: e.features, input_manifest_sha256: createHash('sha256').update(canonical(manifest)).digest('hex') };
}
