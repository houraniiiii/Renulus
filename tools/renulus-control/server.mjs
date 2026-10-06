import { pathToFileURL } from 'node:url';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { RenulusController, parseCli, redact } from './controller.mjs';

const short = z.string().max(512);
export const locatorSchema = z.union([
  z.object({ role: z.enum(['button', 'link', 'textbox', 'searchbox', 'combobox', 'option', 'checkbox', 'radio', 'switch', 'heading', 'navigation', 'tab', 'tabpanel', 'listbox', 'menuitem', 'spinbutton', 'status', 'dialog', 'article', 'group', 'main', 'paragraph', 'row', 'cell', 'img']), name: short }).strict(),
  z.object({ css: short.min(1) }).strict(),
]);
const empty = z.object({}).strict();
const action = z.object({ locator: locatorSchema }).strict();
export const toolDefinitions = [
  ['renulus_start', 'Launch the fixed background Renulus app with its own fresh synthetic profile and managed backend; wait for loopback Flow navigation. No endpoint attachment. Maximum 360 seconds.', empty],
  ['renulus_snapshot', 'Return a bounded ARIA snapshot of the owned Flow page. Use exact role/name or pure CSS locators from this page.', empty],
  ['renulus_click', 'Click exactly one app element through Playwright. Returns action completion; use renulus_wait for asynchronous UI transitions.', action],
  ['renulus_fill', 'Fill exactly one app input with synthetic text. Credential and native file inputs are blocked.', action.extend({ value: z.string().max(4096) })],
  ['renulus_press', 'Press a bounded editing/navigation key on exactly one app element. No OS shortcuts, clipboard, global focus or keyboard APIs.', action.extend({ key: z.enum(['Enter', 'Space', 'Escape', 'Tab', 'Shift+Tab', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Backspace', 'Delete', 'Home', 'End', 'PageUp', 'PageDown', 'Control+A']) })],
  ['renulus_select', 'Select an option in one app select element by exactly one option value or label.', action.extend({ value: short.optional(), label: short.optional() }).refine(args => (args.value !== undefined) !== (args.label !== undefined), 'Supply exactly one of value or label.')],
  ['renulus_wait', 'Wait for a unique app locator to become visible, hidden, attached or detached. Default 5 seconds; maximum 12 seconds. No generic sleeps.', action.extend({ state: z.enum(['visible', 'hidden', 'attached', 'detached']).default('visible'), timeoutMs: z.number().int().min(1).max(12000).default(5000) })],
  ['renulus_screenshot', 'Wait for fonts and two animation frames (at most 5 seconds), then use the owned BrowserWindow.capturePage with stayHidden:true. Return PNG and an external output path; verify hidden state afterwards.', empty],
  ['renulus_errors', 'Read bounded, redacted app/controller logs and background event counts. No account/token access.', z.object({ limit: z.number().int().min(1).max(200).default(100) }).strict()],
  ['renulus_restart', 'Normally close the owned app/backend, then start again with the same owned synthetic profile. Launch readiness is bounded by 360 seconds.', empty],
  ['renulus_close', 'Normally close the owned app and wait for verified main/backend exit, up to 45 seconds. Surviving children or essential forced cleanup are reported as failures.', empty],
];

export function createServer(controller) {
  const server = new McpServer({ name: 'renulus-development-control', version: '0.1.0' }, { maxToolInputElements: 32, instructions: 'Development only. Owns only its launched Renulus app and fresh synthetic session. Use renulus_wait before screenshotting an async transition. Normal app routes reach product subscription/source/retention gates. No personal profiles, credential transport, arbitrary code, external browser/native dialog or OS input.' });
  for (const [name, description, inputSchema] of toolDefinitions) {
    server.registerTool(name, { description, inputSchema, annotations: { readOnlyHint: ['renulus_snapshot', 'renulus_errors', 'renulus_wait'].includes(name), destructiveHint: false, openWorldHint: false } }, async (args, extra) => {
      try {
        const result = await controller.run(name, args, { signal: extra.signal });
        if (name === 'renulus_screenshot') {
          const { data, ...metadata } = result;
          return { content: [{ type: 'text', text: JSON.stringify(metadata) }, { type: 'image', mimeType: 'image/png', data }] };
        }
        return { content: [{ type: 'text', text: JSON.stringify(result) }] };
      } catch (error) {
        return { isError: true, content: [{ type: 'text', text: JSON.stringify({ code: error.code ?? 'controller_error', message: redact(error.message, controller.filled ?? []) }) }] };
      }
    });
  }
  return server;
}

// SDK 1.32.1 stdio does not subscribe to EOF itself. These hooks deliberately
// cover EOF, transport disconnect, output failure, SIGTERM and SIGINT.
export function bindLifecycle(server, controller, { input = process.stdin, output = process.stdout, signals = process, diagnostic = message => process.stderr.write(message + '\n') } = {}) {
  let shutdown;
  const stop = reason => {
    if (shutdown) return shutdown;
    shutdown = Promise.resolve().then(async () => {
      try { await controller.shutdown(reason); }
      catch (error) { signals.exitCode = 1; diagnostic(String(redact('Owned cleanup failed: ' + error.message, controller.filled ?? []))); }
      finally { await server.close().catch(() => {}); dispose(); }
    });
    return shutdown;
  };
  const eof = () => { void stop('stdio-eof'); };
  const closed = () => { void stop('stdio-close'); };
  const failed = () => { void stop('stdio-error'); };
  const terminated = () => { void stop('SIGTERM'); };
  const interrupted = () => { void stop('SIGINT'); };
  const dispose = () => {
    input.off('end', eof); input.off('close', closed); input.off('error', failed); output.off('error', failed);
    signals.off('SIGTERM', terminated); signals.off('SIGINT', interrupted);
  };
  input.once('end', eof); input.once('close', closed); input.once('error', failed); output.once('error', failed);
  signals.once('SIGTERM', terminated); signals.once('SIGINT', interrupted);
  server.server.onclose = () => { void stop('mcp-disconnect'); };
  server.server.onerror = error => { diagnostic(String(redact('MCP transport error: ' + error.message, controller.filled ?? []))); void stop('mcp-error'); };
  return { stop, dispose };
}

export async function main(argv = process.argv.slice(2)) {
  const config = parseCli(argv);
  const controller = new RenulusController(config);
  const server = createServer(controller);
  const lifecycle = bindLifecycle(server, controller);
  await server.connect(new StdioServerTransport(process.stdin, process.stdout, { maxBufferSize: 64_000 }));
  if (process.stdin.readableEnded || process.stdin.destroyed) await lifecycle.stop('stdio-eof');
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(error => { process.stderr.write(String(redact(error.message)) + '\n'); process.exitCode = 1; });
}
