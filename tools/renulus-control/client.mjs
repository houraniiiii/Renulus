import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createInterface } from 'node:readline';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { parseCli, redact } from './controller.mjs';

// A local interactive client also works when a Codex chat cached an older MCP
// server. Each input line is {"name":"renulus_snapshot","arguments":{}}.
// The server retains its fixed configuration, strict schemas and owned profile.
const argv = process.argv.slice(2);
if (argv.includes('--help')) {
  process.stdout.write('node client.mjs --repo ABSOLUTE_REPO --python ABSOLUTE_PYTHON [--state-root ABSOLUTE_DIR] [--helper-assets ABSOLUTE_DIR]\nSend one JSON tool request per line. Screenshots are saved by the server; image bytes are not printed. EOF closes the owned session.\n');
} else {
  const config = parseCli(argv);
  const transport = new StdioClientTransport({ command: process.execPath, args: [path.join(path.dirname(fileURLToPath(import.meta.url)), 'server.mjs'), ...argv], cwd: config.repo, stderr: 'pipe' });
  const client = new Client({ name: 'renulus-local-development', version: '0.1.0' }, { capabilities: {} });
  const input = createInterface({ input: process.stdin, crlfDelay: Infinity });
  transport.stderr?.on('data', chunk => process.stderr.write(String(redact(chunk.toString())).slice(0, 4096)));
  try {
    await client.connect(transport);
    const { tools } = await client.listTools();
    const names = new Set(tools.map(tool => tool.name));
    process.stdout.write(JSON.stringify({ connected: true, tools: [...names] }) + '\n');
    for await (const line of input) {
      if (!line.trim()) continue;
      try {
        if (line.length > 16_000) throw new Error('A request line must be at most 16000 characters.');
        const request = JSON.parse(line);
        if (!request || !names.has(request.name) || Object.keys(request).some(key => !['name', 'arguments'].includes(key))) throw new Error('Supply an available Renulus tool name and its arguments.');
        const result = await client.callTool({ name: request.name, arguments: request.arguments ?? {} }, undefined, { timeout: 420_000 });
        const text = result.content.find(item => item.type === 'text')?.text ?? '{}';
        process.stdout.write(JSON.stringify({ name: request.name, isError: result.isError ?? false, output: JSON.parse(text) }) + '\n');
      } catch (error) {
        process.stdout.write(JSON.stringify({ isError: true, output: { code: 'client_request_failed', message: redact(error.message) } }) + '\n');
      }
    }
  } finally {
    input.close();
    await client.close();
  }
}
