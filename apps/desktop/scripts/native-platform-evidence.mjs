/** Actual production CSP/proxy/resource policy with synthetic PDF and streamed bytes. */
import { _electron as electron } from '@playwright/test';
import { build } from 'esbuild';
import { mkdir, readFile, writeFile, stat } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { randomUUID, createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { syntheticPdf } from './synthetic-pdf.mjs';
import { capturePdfFrames, classifyPdfFrames } from './pdf-viewer-evidence.mjs';
const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const evidence = path.join(desktop, 'test-results', 'native-platform-' + randomUUID().slice(0, 8));
const dist = path.join(evidence, 'dist');
await mkdir(dist, { recursive: true });
const expectedVersion = JSON.parse(await readFile(path.join(desktop, 'package.json'), 'utf8')).devDependencies.electron;
const sourceRevision = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: desktop, encoding: 'utf8' }).trim();
const sourceSha256 = {};
for (const file of ['electron/frontend.ts', 'electron/pdf-resources.ts', 'index.html']) sourceSha256[file] = createHash('sha256').update(await readFile(path.join(desktop, file))).digest('hex');
await build({ entryPoints: [path.join(desktop, 'electron/frontend.ts')], outfile: path.join(evidence, 'frontend.cjs'), bundle: true, platform: 'node', format: 'cjs', target: 'node24', logLevel: 'warning' });
await build({ entryPoints: [path.join(desktop, 'electron/pdf-resources.ts')], outfile: path.join(evidence, 'pdf-resources.cjs'), bundle: true, platform: 'node', format: 'cjs', target: 'node24', logLevel: 'warning' });
const index = await readFile(path.join(desktop, 'index.html'), 'utf8');
const meta = index.match(/<meta http-equiv="Content-Security-Policy" content="[^"]+"[^>]*>/i)?.[0];
if (!meta) throw new Error('The real index CSP is required.');
await writeFile(path.join(dist, 'index.html'), '<!doctype html><html><head>' + meta + '<title>Renulus synthetic native platform proof</title></head><body><h1>Synthetic native PDF</h1><iframe title="Original document viewer" style="width:760px;height:620px;border:0"></iframe><script src="/fixture.js"></script></body></html>');
const pdf = syntheticPdf();
await writeFile(path.join(evidence, 'synthetic-two-page.pdf'), pdf);
await writeFile(path.join(dist, 'fixture.js'), 'const bytes=Uint8Array.from(atob(' + JSON.stringify(pdf.toString('base64')) + '),v=>v.charCodeAt(0)); document.querySelector("iframe").src=URL.createObjectURL(new Blob([bytes],{type:"application/pdf"}))+"#page=2";');
const entry = path.join(evidence, 'main.cjs');
await writeFile(entry, `
const { app, BrowserWindow, session } = require('electron');
const { createServer } = require('node:http');
const path = require('node:path');
const { startFrontend } = require('./frontend.cjs');
const { isBuiltinPdfResource } = require('./pdf-resources.cjs');
app.setPath('userData', process.env.RENULUS_PROFILE);
let backend, frontend, window; const token='synthetic-download-session';
globalThis.platformProof = { requests:[], apiHeaders:[], transfers:[], downloads:[] };
app.whenReady().then(async () => {
  backend=createServer(async (request,response)=>{
    const transfer={ path:request.url, authenticated:request.headers['x-renulus-token']===token, bytesSent:0, finished:false, closed:false };
    globalThis.platformProof.transfers.push(transfer);
    if(!transfer.authenticated) { response.writeHead(401).end(); return; }
    response.on('close',()=>{ transfer.closed=true; });
    response.writeHead(200,{'Content-Type':'application/octet-stream','Content-Length':32*1024*1024,'Content-Disposition':'attachment; filename="synthetic-stream.bin"'});
    const chunk=Buffer.alloc(64*1024,0x5a);
    for(let index=0;index<512&&!response.destroyed;index++) {
      const flowing=response.write(chunk); transfer.bytesSent+=chunk.length;
      if(!flowing) await new Promise(resolve=>{
        const done=()=>{response.off('drain',done);response.off('close',done);resolve();};
        response.once('drain',done);response.once('close',done);
      });
      await new Promise(resolve=>setTimeout(resolve,3));
    }
    if(!response.destroyed) { transfer.finished=true; response.end(); }
  });
  await new Promise(resolve=>backend.listen(0,'127.0.0.1',resolve));
  frontend=await startFrontend(path.join(__dirname,'dist'),backend.address().port,token);
  const isolated=session.fromPartition('renulus-synthetic-platform');
  window=new BrowserWindow({width:860,height:790,show:true,webPreferences:{session:isolated,nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,plugins:false}});
  isolated.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false)); isolated.setPermissionCheckHandler(()=>false);
  isolated.webRequest.onBeforeRequest((details,callback)=>{
    const local=details.url.startsWith(frontend.origin+'/')||details.url===frontend.origin;
    const allowed=local||details.url.startsWith('data:')||details.url.startsWith('blob:')||isBuiltinPdfResource(details.url);
    globalThis.platformProof.requests.push({url:details.url,type:details.resourceType,allowed}); callback({cancel:!allowed});
  });
  isolated.webRequest.onBeforeSendHeaders({urls:[frontend.origin+'/api/v1/*']},(details,callback)=>{
    const owned=details.webContentsId===window.webContents.id;
    globalThis.platformProof.apiHeaders.push({webContentsId:details.webContentsId,ownerId:window.webContents.id,owned});
    if(!owned) { callback({cancel:true}); return; }
    callback({requestHeaders:{...details.requestHeaders,'x-renulus-token':token}});
  });
  isolated.on('will-download',(_event,item,contents)=>{
    const record={url:item.getURL(),contentsId:contents?.id,ownerId:window.webContents.id,initiator:item.getInitiatorOrigin(),updates:0,totalBytes:item.getTotalBytes()};
    globalThis.platformProof.downloads.push(record);
    const cancelling=item.getURL().includes('cancel=1');
    const target=path.join(__dirname,cancelling?'cancelled-stream.bin':'completed-stream.bin');
    item.setSaveDialogOptions({title:'Save a Renulus backup',defaultPath:target,filters:[{name:'Synthetic bytes',extensions:['bin']}]});
    record.saveDialogOptions=item.getSaveDialogOptions();
    item.setSavePath(target); // Automated synthetic fixture only; the product should show the dialog.
    item.on('updated',()=>{record.updates++;record.receivedBytes=item.getReceivedBytes();if(cancelling&&record.receivedBytes>=1024*1024){record.receivedBeforeCancel=record.receivedBytes;item.cancel();}});
    item.once('done',(_event,state)=>{record.state=state;record.receivedBytes=item.getReceivedBytes();record.savePath=item.getSavePath();});
  });
  globalThis.startPlatformDownload=(cancelling)=>window.webContents.downloadURL(frontend.origin+'/api/v1/data/backup?format_version=2'+(cancelling?'&cancel=1':''));
  window.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  window.webContents.on('will-navigate',(event,url)=>{if(new URL(url).origin!==frontend.origin)event.preventDefault();});
  await window.loadURL(frontend.origin);
});
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',()=>{frontend?.server.closeAllConnections();frontend?.server.close();backend?.closeAllConnections();backend?.close();});
`);
const env = {};
for (const name of ['SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA']) if (process.env[name]) env[name] = process.env[name];
env.PATH = path.join(process.env.SystemRoot, 'System32'); env.RENULUS_PROFILE = path.join(evidence, 'profile');
let application;
const result = { kind: 'production-policy-native-fixture', sourceRevision, sourceSha256, console: [], requestFailures: [], limits: ['Production CSP/proxy/resource functions; synthetic window and backend, not the integrated product', '32-MiB byte transfer, not a valid recovery ZIP or multi-GiB capacity proof', 'Save dialog options set but automated owned path used; no actual user-dialog interaction', 'No Python/helpers/private profile/provider calls'] };
try {
  application = await electron.launch({ executablePath: path.join(desktop, 'node_modules/electron/dist/electron.exe'), args: [entry], cwd: evidence, env });
  const page = await application.firstWindow();
  page.on('console', message => result.console.push({ type: message.type(), text: message.text().slice(0, 1500) }));
  page.on('requestfailed', request => result.requestFailures.push({ url: request.url(), failure: request.failure() }));
  await page.getByRole('heading', { name: 'Synthetic native PDF' }).waitFor();
  await page.waitForTimeout(2000);
  result.electron = await application.evaluate(() => process.versions.electron);
  if (result.electron !== expectedVersion) throw new Error('The pinned Electron artifact is required.');
  result.frames = await capturePdfFrames(page); Object.assign(result, classifyPdfFrames(result.frames));
  await page.getByTitle('Original document viewer').screenshot({ path: path.join(evidence, 'production-policy-page-two.png') });
  if (result.blocked || !result.viewerDetected || !result.citationPageSelected || result.requestFailures.length) throw new Error('The real CSP/resource policy did not render the physical cited PDF page.');
  for (const cancelling of [false, true]) {
    await application.evaluate((_electron, value) => globalThis.startPlatformDownload(value), cancelling);
    const expectedCount = cancelling ? 2 : 1;
    const deadline = Date.now() + 30_000;
    while (Date.now() < deadline) {
      const progress = await application.evaluate(() => ({ count: globalThis.platformProof.downloads.length, state: globalThis.platformProof.downloads.at(-1)?.state }));
      if (progress.count === expectedCount && progress.state) break;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    const download = await application.evaluate(() => globalThis.platformProof.downloads.at(-1));
    if (!download || download.state !== (cancelling ? 'cancelled' : 'completed') || download.contentsId !== download.ownerId) throw new Error('The authenticated native disk download/cancel did not finish.');
  }
  await page.waitForTimeout(300);
  result.native = await application.evaluate(() => globalThis.platformProof);
  if (result.native.apiHeaders.length !== 2 || result.native.apiHeaders.some(record => !record.owned) || result.native.transfers.length !== 2 || result.native.transfers.some(record => !record.authenticated) || !result.native.transfers[0].finished || result.native.transfers[1].finished || !result.native.transfers[1].closed) throw new Error('The native download lost the existing token/ownership/stream-cancel boundary.');
  const completed = path.join(evidence, 'completed-stream.bin');
  result.completedFileBytes = (await stat(completed)).size;
  const actualHash = createHash('sha256'); for await (const chunk of createReadStream(completed)) actualHash.update(chunk);
  result.completedFileSha256 = actualHash.digest('hex');
  const expectedHash = createHash('sha256'); for (let i = 0; i < 512; i++) expectedHash.update(Buffer.alloc(64 * 1024, 0x5a));
  if (result.completedFileBytes !== 32 * 1024 * 1024 || result.completedFileSha256 !== expectedHash.digest('hex')) throw new Error('The streamed synthetic file changed bytes or size.');
  result.rendererStayedLocal = page.url().startsWith('http://127.0.0.1:');
} catch (error) { result.error = error.message; }
finally { if (application) await application.close(); await writeFile(path.join(evidence, 'native-platform-evidence.json'), JSON.stringify({ checkedAt: new Date().toISOString(), ...result }, null, 2)); }
console.log(JSON.stringify({ evidence, electron: result.electron, pdfPageTwo: !result.blocked && result.citationPageSelected, streamedBytes: result.completedFileBytes, downloads: result.native?.downloads, error: result.error }));
if (result.error) process.exitCode = 1;
