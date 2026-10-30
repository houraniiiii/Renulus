// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { createHmac } from "node:crypto";
import http from "node:http";
import { copyFile, mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { openCompatibilityFacade } from "../src/http/compatibility.ts";
import { openCompatibilityApplication } from "../src/host/application.ts";
import { openPythonDomain } from "../src/host/python-domain.ts";

const token = "synthetic-facade-session-only";
const headers = { "x-renulus-token": token };
const source = fileURLToPath(new URL("../../..", import.meta.url));
const python = process.env.RENULUS_BACKEND_TEST_PYTHON;

async function fixture(server, control) {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-bf00-domain-fixture-"));
  await mkdir(path.join(root, "runtime/renulus/runtime"), { recursive: true });
  // Use the real adapter/lineage/Services, with only the application factory
  // replaced by a synthetic app. No second domain or shutdown implementation.
  await writeFile(path.join(root, "runtime/renulus/__init__.py"),
    `__version__ = "0.1.0"\n__path__.append(${JSON.stringify(path.join(source, "runtime/renulus"))})\n`);
  await writeFile(path.join(root, "runtime/renulus/runtime/__init__.py"), "");
  const entry = path.join(root, "runtime/renulus/runtime/domain_process.py");
  if (control) await writeFile(entry, control);
  else await copyFile(path.join(source, "runtime/renulus/runtime/domain_process.py"), entry);
  await copyFile(path.join(source, "runtime/renulus/runtime/domain_peer.py"),
    path.join(root, "runtime/renulus/runtime/domain_peer.py"));
  await writeFile(path.join(root, "runtime/renulus/server.py"), server);
  const profile = path.join(root, "profile");
  await mkdir(profile);
  return { sourceRoot: root, profile, python, token, desktopHarness: false };
}

const syntheticApp = `
import asyncio,os,sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request
from renulus.services import Services
def create_app(profile,token,source_root):
    assert 'RENULUS_SESSION_TOKEN' not in os.environ
    assert token not in ' '.join(sys.argv)
    services=Services(None,None)
    root=Path(profile)
    async def finish():
        if (root/'refuse-settlement').exists() and not (root/'allow-settlement').exists():
            raise RuntimeError('synthetic cleanup refused')
        if (root/'delay-exit').exists():
            (root/'shutdown-finished').write_text('settled')
    services.on_shutdown.append(finish)
    @asynccontextmanager
    async def lifespan(app):
        (root/'startup-entered').write_text('entered')
        while (root/'delay-startup').exists() and not (root/'allow-startup').exists():
            await asyncio.sleep(.02)
        yield
        await services.finish_shutdown()
        while (root/'delay-exit').exists() and not (root/'allow-exit').exists():
            await asyncio.sleep(.02)
        (root/'lifespan-closed').write_text('closed')
    app=FastAPI(lifespan=lifespan)
    app.state.services=services
    @app.get('/api/v1/meta')
    def meta(request:Request):return {'api_version':1,'pid':os.getpid(),'port':request.scope['server'][1]}
    return app
`;

async function until(check) {
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    if (await check()) return;
    await new Promise(resolve => setTimeout(resolve, 20));
  }
  assert.fail("synthetic process did not reach expected stage");
}

const marker = (profile, name) => readFile(path.join(profile, name), "utf8").then(() => true, () => false);

const peerProof = url => createHmac("sha256", token)
  .update("renulus-domain-http/1:" + new URL(url, "http://127.0.0.1").searchParams.get("nonce")).digest("hex");

test("facade sends credentials and body only on the TCP connection that proved ownership", async () => {
  const observed = [];
  let connections = 0;
  const upstream = http.createServer(async (request, response) => {
    let body = "";
    for await (const chunk of request) body += chunk;
    observed.push({ url: request.url, token: request.headers["x-renulus-token"], body, socket: request.socket });
    if (request.url.startsWith("/__renulus_peer?")) return response.end(peerProof(request.url));
    response.writeHead(201);
    response.end("synthetic saved response");
  });
  upstream.on("connection", () => connections++);
  await new Promise(resolve => upstream.listen(0, "127.0.0.1", resolve));
  const facade = await openCompatibilityFacade({ token, peerKey: token, upstreamPort: upstream.address().port, port: 0 });
  try {
    const response = await fetch(`http://127.0.0.1:${facade.port}/api/v1/synthetic`, {
      method: "POST", headers, body: "SYNTHETIC learning request body",
    });
    assert.equal(response.status, 201);
    assert.equal(await response.text(), "synthetic saved response");
    assert.equal(connections, 1);
    assert.equal(observed.length, 2);
    assert.match(observed[0].url, /^\/__renulus_peer\?nonce=[0-9a-f]{64}$/);
    assert.equal(observed[0].token, undefined);
    assert.equal(observed[0].body, "");
    assert.equal(observed[1].socket, observed[0].socket);
    assert.equal(observed[1].token, token);
    assert.equal(observed[1].body, "SYNTHETIC learning request body");
  } finally {
    await facade.close();
    await new Promise(resolve => upstream.close(resolve));
  }
});

for (const validProof of [false, true]) {
  test(validProof ? "a proven connection closed by the peer cannot reconnect and leak credentials/body" :
    "a foreign peer receives only the credential-free nonce probe", async () => {
    const observed = [];
    let connections = 0;
    const upstream = http.createServer(async (request, response) => {
      let body = "";
      for await (const chunk of request) body += chunk;
      observed.push({ url: request.url, token: request.headers["x-renulus-token"], body });
      // Only the first connection can prove ownership. Any reconnect reaches a
      // foreign peer. Connection: close makes loss deterministic before reuse.
      response.setHeader("connection", "close");
      response.end(validProof && observed.length === 1 ? peerProof(request.url) : "foreign-peer");
    });
    upstream.on("connection", () => connections++);
    await new Promise(resolve => upstream.listen(0, "127.0.0.1", resolve));
    const facade = await openCompatibilityFacade({ token, peerKey: token, upstreamPort: upstream.address().port, port: 0 });
    try {
      const response = await fetch(`http://127.0.0.1:${facade.port}/api/v1/runtime/shutdown`, {
        method: "POST", headers, body: "SYNTHETIC sensitive control body",
      });
      assert.equal(response.status, 503);
      await response.text();
      assert.equal(connections, 1, "a proven Agent must never create a second TCP connection");
      assert.equal(observed.length, 1);
      assert.match(observed[0].url, /^\/__renulus_peer\?nonce=[0-9a-f]{64}$/);
      assert.equal(observed[0].token, undefined);
      assert.equal(observed[0].body, "");
    } finally {
      await facade.close();
      await new Promise(resolve => upstream.close(resolve));
    }
  });
}

test("facade preserves streamed bytes/status and authenticates before upstream effects", async () => {
  let calls = 0;
  const pending = [];
  const upstream = http.createServer((request, response) => {
    calls++;
    if (request.url === "/api/v1/hold") { pending.push(response); return; }
    response.writeHead(207, { "content-type": "text/event-stream" });
    response.write('event: started\ndata: {"id":"synthetic"}\n\n');
    setTimeout(() => response.end('event: completed\ndata: {"state":"saved"}\n\n'), 5);
  });
  await new Promise(resolve => upstream.listen(0, "127.0.0.1", resolve));
  const facade = await openCompatibilityFacade({ token, upstreamPort: upstream.address().port, port: 0, maxInflight: 1 });
  const origin = `http://127.0.0.1:${facade.port}`;
  try {
    assert.equal((await fetch(origin + "/api/v1/meta")).status, 401);
    assert.equal((await fetch(origin + "/api/v1/meta", { headers: { ...headers, origin: "https://untrusted.example" } })).status, 403);
    assert.equal(calls, 0);
    const response = await fetch(origin + "/api/v1/synthetic", { headers });
    assert.equal(response.status, 207);
    assert.equal(await response.text(), 'event: started\ndata: {"id":"synthetic"}\n\nevent: completed\ndata: {"state":"saved"}\n\n');
    const held = fetch(origin + "/api/v1/hold", { headers });
    while (!pending.length) await new Promise(resolve => setTimeout(resolve, 2));
    const overloaded = await fetch(origin + "/api/v1/synthetic", { headers });
    assert.equal(overloaded.status, 503);
    assert.equal((await overloaded.json()).error.code, "runtime_overloaded");
    const control = await fetch(origin + "/api/v1/runtime/status", { headers });
    assert.equal(control.status, 207);
    await control.text();
    pending[0].end("held response settled");
    assert.equal(await (await held).text(), "held response settled");
    facade.seal();
    assert.equal((await fetch(origin + "/api/v1/search?q=CKD", { headers })).status, 503);
  } finally {
    for (const response of pending) response.end();
    await facade.close();
    await new Promise(resolve => upstream.close(resolve));
  }
});

for (const action of ['deadline', 'block', 'close']) {
  test(`peer proof with repeated 103 and no final response is drained by ${action}`, { timeout: 7000 }, async t => {
    const entered = Promise.withResolvers(), disconnected = Promise.withResolvers();
    let hints = 0, calls = 0, wire = '', connections = 0;
    const sockets = new Set();
    const upstream = http.createServer((request, response) => {
      calls++;
      assert.match(request.url, /^\/__renulus_peer\?nonce=[0-9a-f]{64}$/);
      assert.equal(request.headers['x-renulus-token'], undefined);
      const hint = () => { hints++; response.writeEarlyHints({ link: '</synthetic>; rel=preload' }); };
      hint();
      const traffic = setInterval(hint, 40);
      request.socket.once('close', () => { clearInterval(traffic); disconnected.resolve(); });
      entered.resolve();
    });
    upstream.on('connection', socket => {
      connections++; sockets.add(socket);
      socket.on('data', chunk => { wire += chunk.toString('utf8'); });
      socket.once('close', () => sockets.delete(socket));
    });
    await new Promise(resolve => upstream.listen(0, '127.0.0.1', resolve));
    const facade = await openCompatibilityFacade({ token, peerKey: token, upstreamPort: upstream.address().port, port: 0 });
    t.after(async () => {
      await facade.close();
      for (const socket of sockets) socket.destroy();
      await new Promise(resolve => upstream.close(resolve));
    });
    const started = performance.now();
    const pending = fetch(`http://127.0.0.1:${facade.port}/api/v1/synthetic`, {
      method: 'POST', headers, body: 'SYNTHETIC withheld request payload', signal: AbortSignal.timeout(5000),
    });
    await entered.promise;
    if (action === 'block') { await facade.block(); assert.equal(facade.state().active, 0); }
    if (action === 'close') await facade.close();
    const response = await pending;
    assert.equal(response.status, 503);
    await response.arrayBuffer();
    await disconnected.promise;
    await until(() => facade.state().active === 0);
    const elapsed = performance.now() - started;
    assert.ok(elapsed < (action === 'deadline' ? 3500 : 1000), `${action} took ${elapsed} ms`);
    if (action === 'deadline') assert.ok(hints > 20, `expected sustained informational traffic, got ${hints}`);
    assert.equal(connections, 1);
    assert.equal(calls, 1);
    assert.ok(!wire.includes(token), 'no token bytes before ownership proof');
    assert.ok(!wire.includes('SYNTHETIC withheld request payload'), 'no body before ownership proof');
    assert.ok(!wire.includes('/api/v1/synthetic'));
    if (action === 'block') {
      const blocked = await fetch(`http://127.0.0.1:${facade.port}/api/v1/meta`, { headers });
      assert.equal(blocked.status, 503);
      await blocked.arrayBuffer();
      assert.equal(connections, 1, 'blocked ownership cannot create another probe');
    }
  });
}

test("Effect facade starts an account-free real Python owner, reads canonical data and settles", {
  skip: !process.env.RENULUS_BACKEND_TEST_PYTHON,
  timeout: 60_000,
}, async () => {
  const profile = await mkdtemp(path.join(tmpdir(), "renulus-bf00-facade-"));
  const app = await openCompatibilityApplication({ token, port: 0, profile,
    python: process.env.RENULUS_BACKEND_TEST_PYTHON,
    sourceRoot: source, desktopHarness: false });
  const origin = `http://127.0.0.1:${app.port}`;
  try {
    const meta = await fetch(origin + "/api/v1/meta", { headers });
    assert.equal(meta.status, 200);
    assert.equal((await meta.json()).api_version, 1);
    const connections = await fetch(origin + "/api/v1/connections", { headers });
    assert.equal(connections.status, 200);
    assert.equal((await connections.json()).selected_provider, null);
    const search = await fetch(origin + "/api/v1/search?q=transplant", { headers });
    assert.equal(search.status, 200);
    assert.deepEqual((await search.json()).items, []);
  } finally { await app.close(); }
});

test("failed shutdown retains the same Effect owner and retries real settlement before reporting closed", {
  skip: !process.env.RENULUS_BACKEND_TEST_PYTHON, timeout: 30_000,
}, async () => {
  const options = await fixture(syntheticApp);
  const { profile } = options;
  await writeFile(path.join(profile, "refuse-settlement"), "synthetic refusal");
  const app = await openCompatibilityApplication({ ...options, port: 0 });
  const origin = `http://127.0.0.1:${app.port}`;
  await assert.rejects(app.close());
  await assert.rejects(app.close(), undefined, "A disposed scope must not falsely acknowledge a second close");
  assert.equal(app.state().admission, "closed");
  assert.equal((await fetch(origin + "/api/v1/meta", { headers })).status, 200);
  await writeFile(path.join(profile, "allow-settlement"), "synthetic settlement allowed");
  await app.close();
  await assert.rejects(fetch(origin + "/api/v1/meta", { headers }));
});

test("unexpected real Python death never acknowledges settlement, including repeated close", {
  skip: !python, timeout: 30_000,
}, async () => {
  const profile = await mkdtemp(path.join(tmpdir(), "renulus-bf00-domain-death-"));
  const owner = await openPythonDomain({ python, sourceRoot: source, profile, token, desktopHarness: false });
  assert.equal(owner.ready.process.launcher_pid, owner.launcherPid);
  assert.equal(owner.ready.process.actual_pid, owner.pid);
  assert.ok(owner.ready.process.ancestry_depth >= 1, "prove actual Windows venv redirector ancestry");
  process.kill(owner.pid);
  await until(async () => {
    try { process.kill(owner.pid, 0); return false; } catch { return true; }
  });
  for (let attempt = 0; attempt < 2; attempt++) {
    await assert.rejects(owner.close(), error => {
      assert.match(error.message, /python_domain_(exit_uncertain|control_lost)/);
      assert.equal(error.settlement, "uncertain");
      assert.equal(error.ownedPid, owner.pid);
      return true;
    });
  }
});

test("real Python death blocks every facade route after its port is reused without leaking token/body", {
  skip: !python, timeout: 30_000,
}, async () => {
  const options = await fixture(syntheticApp);
  // The uncertain application intentionally retains its facade and Effect owner.
  // Isolate this failure proof so exiting the test does not add a force-close API
  // or falsely acknowledge the dead Python process's settlement.
  const result = spawnSync(process.execPath, ["--input-type=module", "-e", `
import assert from 'node:assert/strict';
import http from 'node:http';
import { openCompatibilityApplication } from ${JSON.stringify(new URL("../src/host/application.ts", import.meta.url).href)};
const until = ${until.toString()};
const options = ${JSON.stringify(options)};
const app = await openCompatibilityApplication({ ...options, port: 0 });
const origin = 'http://127.0.0.1:' + app.port;
const headers = { 'x-renulus-token': options.token };
let foreign, killed = false;
try {
  const meta = await fetch(origin + '/api/v1/meta', { headers });
  assert.equal(meta.status, 200);
  const owner = await meta.json();
  process.kill(owner.pid);
  killed = true;
  await until(() => app.state().admission === 'closed');
  await until(() => { try { process.kill(owner.pid, 0); return false; } catch { return true; } });
  let connections = 0, wire = '', calls = 0;
  foreign = http.createServer((request, response) => { calls++; request.resume(); response.end('foreign'); });
  foreign.on('connection', socket => { connections++; socket.on('data', chunk => { wire += chunk; }); });
  await new Promise((resolve, reject) => {
    foreign.once('error', reject);
    foreign.listen(owner.port, '127.0.0.1', resolve);
  });
  assert.equal(foreign.address().port, owner.port, 'reuse the actual dead Python listener port');
  for (const route of ['/api/v1/health', '/api/v1/meta', '/api/v1/runtime/status',
      '/api/v1/runtime/shutdown', '/api/v1/synthetic']) {
    const response = await fetch(origin + route, {
      method: 'POST', headers: route.endsWith('/health') ? {} : headers,
      body: 'SYNTHETIC private body after Python death',
    });
    assert.equal(response.status, 503, route);
    assert.equal((await response.json()).error.code, 'backend_owner_uncertain', route);
  }
  for (let attempt = 0; attempt < 2; attempt++) {
    await assert.rejects(app.close(), error => {
      assert.match(error.message, /python_domain_(exit_uncertain|control_lost)/);
      assert.equal(error.settlement, 'uncertain');
      assert.equal(error.ownedPid, owner.pid);
      return true;
    });
  }
  assert.equal(connections, 0, 'owner loss must block even credential-free probes');
  assert.equal(calls, 0);
  assert.equal(wire, '', 'the replacement receives zero token, headers or body bytes');
} finally {
  if (foreign?.listening) await new Promise(resolve => foreign.close(resolve));
  if (!killed) await app.close();
}
process.exit(0);
`], { encoding: "utf8", windowsHide: true, timeout: 25_000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr || result.stdout);
});

test("ready waits for lifespan startup and close waits for exit after a real settlement ACK", {
  skip: !python, timeout: 30_000,
}, async () => {
  const options = await fixture(syntheticApp);
  await writeFile(path.join(options.profile, "delay-startup"), "delay");
  await writeFile(path.join(options.profile, "delay-exit"), "delay");
  let opened = false, closed = false;
  const opening = openPythonDomain(options).then(owner => { opened = true; return owner; });
  await until(() => marker(options.profile, "startup-entered"));
  assert.equal(opened, false);
  await writeFile(path.join(options.profile, "allow-startup"), "continue");
  const owner = await opening;
  const closing = owner.close().then(() => { closed = true; });
  await until(() => marker(options.profile, "shutdown-finished"));
  await new Promise(resolve => setTimeout(resolve, 250));
  assert.equal(closed, false, "settled Services alone cannot prove lifespan/process exit");
  await writeFile(path.join(options.profile, "allow-exit"), "continue");
  await closing;
  assert.equal(await marker(options.profile, "lifespan-closed"), true);
  assert.throws(() => process.kill(owner.pid, 0));
  await owner.close();
});

test("foreign HTTP meta/shutdown cannot prove readiness or receive the private token", {
  skip: !python, timeout: 30_000,
}, async t => {
  let calls = 0;
  const foreign = http.createServer((request, response) => {
    calls++;
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify({ api_version: 1, state: "settled" }));
  });
  await new Promise(resolve => foreign.listen(0, "127.0.0.1", resolve));
  try {
    for (const field of ["launch_nonce", "profile", "launcher_pid", "actual_pid", "creation_time"]) {
      await t.test(field, async () => {
        const control = `
import argparse,json,os,sys
from renulus.workers.lineage import attest_launcher
p=argparse.ArgumentParser();p.add_argument('--profile');p.add_argument('--source-root');p.add_argument('--launch-nonce');a=p.parse_args()
h=json.loads(sys.stdin.readline())
assert 'RENULUS_SESSION_TOKEN' not in os.environ and h['token'] not in ' '.join(sys.argv)
proof=attest_launcher(h['expected_launcher_pid']).model_dump()
r=dict(protocol='renulus-domain/1',kind='ready',profile=h['profile'],launch_nonce=h['launch_nonce'],pid=os.getpid(),process=proof,port=${foreign.address().port})
field=${JSON.stringify(field)}
if field in ('launch_nonce','profile'):r[field]='foreign'
elif field=='creation_time':proof['actual_creation_filetime']='0'
else:proof[field]+=1
print(json.dumps(r),flush=True)
sys.stdin.read()
`;
        const options = await fixture("", control);
        await assert.rejects(openPythonDomain(options), /python_domain_invalid_control/);
        assert.equal(calls, 0, "a foreign HTTP listener must receive no probe, shutdown or token");
      });
    }
  } finally { await new Promise(resolve => foreign.close(resolve)); }
});

test("stale shutdown replies and clean exit without ACK remain uncertain across retries", {
  skip: !python, timeout: 30_000,
}, async t => {
  for (const field of ["request_id", "launch_nonce", "profile", "pid", "no_ack"]) {
    await t.test(field, async () => {
      const control = `
import argparse,json,os,sys
from renulus.workers.lineage import attest_launcher
p=argparse.ArgumentParser();p.add_argument('--profile');p.add_argument('--source-root');p.add_argument('--launch-nonce');a=p.parse_args()
h=json.loads(sys.stdin.readline())
r=dict(protocol='renulus-domain/1',kind='ready',profile=h['profile'],launch_nonce=h['launch_nonce'],pid=os.getpid(),process=attest_launcher(h['expected_launcher_pid']).model_dump(),port=12345)
print(json.dumps(r),flush=True)
request=json.loads(sys.stdin.readline())
field=${JSON.stringify(field)}
if field!='no_ack':
    reply={k:v for k,v in request.items() if k!='timeout_seconds'}
    reply['state']='settled'
    reply[field]=1 if field=='pid' else 'stale'
    print(json.dumps(reply),flush=True)
    sys.stdin.read()
`;
      const options = await fixture("", control);
      const owner = await openPythonDomain(options);
      for (let attempt = 0; attempt < 2; attempt++) {
        await assert.rejects(owner.close(), error => {
          assert.equal(error.settlement, "uncertain");
          assert.match(error.message, /python_domain_(invalid_control|control_lost|exit_uncertain)/);
          return true;
        });
      }
      await until(async () => {
        try { process.kill(owner.pid, 0); return false; } catch { return true; }
      });
    });
  }
});
