/** Actual pinned Electron policy diagnosis. No backend, originals or shared-source edits. */
import { _electron as electron } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { syntheticPdf } from './synthetic-pdf.mjs';
import { capturePdfFrames, classifyPdfFrames } from './pdf-viewer-evidence.mjs';
const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const evidence = path.join(desktop, 'test-results', 'pdf-policy-' + randomUUID().slice(0, 8));
await mkdir(evidence, { recursive: true });
const expectedVersion = JSON.parse(await readFile(path.join(desktop, 'package.json'), 'utf8')).devDependencies.electron;
const baseline = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'";
const cases = [
  { name: 'baseline', csp: baseline },
  { name: 'blob-frame', csp: baseline + "; frame-src 'self' blob:" },
  { name: 'blob-frame-plugin', csp: baseline + "; frame-src 'self' blob:", plugins: true },
  { name: 'blob-frame-object', csp: baseline.replace("object-src 'none'", "object-src 'self' blob:") + "; frame-src 'self' blob:", plugins: true },
  { name: 'internal-viewer', csp: baseline.replace("object-src 'none'", "object-src 'self' blob:") + "; frame-src 'self' blob:", plugins: true, extension: true },
  { name: 'exact-builtin-frame-only', csp: baseline + "; frame-src 'self' blob:", extension: 'exact', resources: true },
  { name: 'exact-builtin-object', csp: baseline.replace("object-src 'none'", "object-src 'self' blob:") + "; frame-src 'self' blob:", extension: 'exact', resources: true },
];
const entry = path.join(evidence, 'main.cjs');
const pdf = syntheticPdf();
await writeFile(path.join(evidence, 'synthetic-two-page.pdf'), pdf);
await writeFile(entry, `
const { app, BrowserWindow, session } = require('electron');
const { createServer } = require('node:http');
app.setPath('userData', process.env.RENULUS_PROFILE);
let server; globalThis.pdfPolicyRequests = []; globalThis.pdfPolicyFailures = [];
app.whenReady().then(async () => {
  const policy = JSON.parse(process.env.RENULUS_PDF_POLICY);
  const script = 'const bytes=Uint8Array.from(atob(' + JSON.stringify(${JSON.stringify(pdf.toString('base64'))}) + '),v=>v.charCodeAt(0)); const viewer=document.querySelector("iframe"); viewer.src=URL.createObjectURL(new Blob([bytes],{type:"application/pdf"}))+"#page=2";';
  server = createServer((request, response) => {
    response.setHeader('Content-Security-Policy', policy.csp);
    if(request.url === '/fixture.js') { response.setHeader('Content-Type','text/javascript'); response.end(script); return; }
    response.setHeader('Content-Type','text/html');
    response.end('<html><head><meta http-equiv="Content-Security-Policy" content="' + policy.csp + '"><title>Native PDF policy test</title></head><body><h1>Synthetic native PDF fixture</h1><iframe title="Original document viewer" style="width:700px;height:600px;border:0"></iframe><script src="/fixture.js"></script></body></html>');
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin='http://127.0.0.1:' + server.address().port;
  const isolated=session.fromPartition('synthetic-pdf-policy');
  isolated.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false));
  isolated.setPermissionCheckHandler(()=>false);
  isolated.webRequest.onBeforeRequest((details, callback)=>{
    const url = new URL(details.url);
    const extensionAllowed = url.protocol === 'chrome-extension:' && (policy.extension === true || (policy.extension === 'exact' && url.hostname === 'mhjfbmdgcfjbbpaeojofohoefgiehjai'));
    const resourceAllowed = policy.resources && url.protocol === 'chrome:' && url.hostname === 'resources';
    const allowed=url.origin === origin || ['data:','blob:'].includes(url.protocol) || extensionAllowed || resourceAllowed;
    globalThis.pdfPolicyRequests.push({url:details.url,type:details.resourceType,allowed}); callback({cancel:!allowed});
  });
  const window=new BrowserWindow({width:820,height:780,show:true,webPreferences:{session:isolated,nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,plugins:policy.plugins ?? false}});
  window.webContents.on('did-fail-load',(_event,code,description,url,isMainFrame)=>globalThis.pdfPolicyFailures.push({code,description,url,isMainFrame}));
  window.webContents.on('will-navigate',(event,url)=>{if(new URL(url).origin!==origin) event.preventDefault();});
  await window.loadURL(origin);
});
app.on('window-all-closed',()=>app.quit()); app.on('before-quit',()=>server?.close());
`);
const env = {};
for (const name of ['SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA']) if (process.env[name]) env[name] = process.env[name];
env.PATH = path.join(process.env.SystemRoot, 'System32');
const results = [];
for (const policy of cases) {
  let application; const result = { ...policy, console: [], requestFailures: [] };
  try {
    application = await electron.launch({ executablePath: path.join(desktop, 'node_modules/electron/dist/electron.exe'), args: [entry], cwd: evidence, env: { ...env, RENULUS_PROFILE: path.join(evidence, policy.name), RENULUS_PDF_POLICY: JSON.stringify(policy) } });
    const page = await application.firstWindow();
    page.on('console', message => result.console.push({ type: message.type(), text: message.text().slice(0, 3000) }));
    page.on('requestfailed', request => result.requestFailures.push({ url: request.url(), failure: request.failure() }));
    await page.getByRole('heading', { name: 'Synthetic native PDF fixture' }).waitFor();
    await page.waitForTimeout(3000);
    result.electron = await application.evaluate(() => process.versions.electron);
    if (result.electron !== expectedVersion) throw new Error('Pinned Electron is required.');
    result.frames = await capturePdfFrames(page); Object.assign(result, classifyPdfFrames(result.frames));
    result.requests = await application.evaluate(() => globalThis.pdfPolicyRequests);
    result.loadFailures = await application.evaluate(() => globalThis.pdfPolicyFailures);
    await page.getByTitle('Original document viewer').screenshot({ path: path.join(evidence, policy.name + '.png') });
  } catch (error) { result.error = error.message; }
  finally { if (application) await application.close(); }
  results.push(result); console.log(JSON.stringify({ name:policy.name, blocked:result.blocked, viewerDetected:result.viewerDetected, citationPageSelected:result.citationPageSelected, error:result.error, console:result.console, requestFailures:result.requestFailures }));
}
await writeFile(path.join(evidence, 'pdf-policy-evidence.json'), JSON.stringify({ checkedAt:new Date().toISOString(), kind:'pinned-Electron-policy-fixture', results, limits:['Synthetic policy diagnosis only; actual product proof is separate'] }, null, 2));
console.log(JSON.stringify({ evidence }));
