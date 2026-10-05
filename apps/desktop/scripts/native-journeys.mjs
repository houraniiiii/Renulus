/** Packaged viewer/source proof. Library DTO/PDF fixtures are synthetic, not ingestion evidence. */
import { _electron as electron } from '@playwright/test';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { randomUUID, randomBytes, createHash } from 'node:crypto';
import { createServer } from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { waitForFlowWindow } from './wait-for-flow-window.mjs';
import { syntheticPdf } from './synthetic-pdf.mjs';
import { capturePdfFrames, classifyPdfFrames } from './pdf-viewer-evidence.mjs';
import { proveNativeProductBackup } from './native-product-backup.mjs';
const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sourceDesktop = process.env.RENULUS_SOURCE_DESKTOP;
const expectedRevision = process.env.RENULUS_EXPECT_SOURCE_REVISION;
const executable = sourceDesktop ? path.join(desktop, 'node_modules/electron/dist/electron.exe') : process.env.RENULUS_PACKAGED_EXECUTABLE;
if (!executable || !path.isAbsolute(executable) || sourceDesktop && process.env.RENULUS_PACKAGED_EXECUTABLE) throw new Error('One explicit source desktop or packaged executable is required.');
let sourceProvenance;
if (sourceDesktop) {
  const relative = path.relative(path.join(desktop, 'test-results'), sourceDesktop);
  if (!path.isAbsolute(sourceDesktop) || relative.startsWith('..') || path.isAbsolute(relative) || !/^[0-9a-f]{40}$/.test(expectedRevision ?? '')) throw new Error('Source proof requires an owned immutable compiled snapshot and exact revision.');
  sourceProvenance = JSON.parse(await readFile(path.join(sourceDesktop, 'dist-electron/native-provenance.json'), 'utf8'));
  const renderer = JSON.parse(await readFile(path.join(sourceDesktop, 'dist/renderer-provenance.json'), 'utf8'));
  const main = createHash('sha256').update(await readFile(path.join(sourceDesktop, 'dist-electron/main.cjs'))).digest('hex');
  const preload = createHash('sha256').update(await readFile(path.join(sourceDesktop, 'dist-electron/preload.cjs'))).digest('hex');
  if (sourceProvenance.source_revision !== expectedRevision || renderer.source_revision !== expectedRevision || sourceProvenance.main_bundle_sha256 !== main || sourceProvenance.preload_bundle_sha256 !== preload || sourceProvenance.backend_adoption.source_sha256 !== sourceProvenance.backend_adoption.adopted_sha256) throw new Error('The source journey requires unchanged matching compiled main/preload/backend.');
}
await mkdir(path.join(desktop, 'test-results'), { recursive: true });
const evidence = path.join(desktop, 'test-results', 'journeys-' + randomUUID().slice(0, 8));
await mkdir(evidence);
const expectedVersion = JSON.parse(await readFile(path.join(desktop, 'package.json'), 'utf8')).devDependencies.electron;
const env = {};
for (const name of ['SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA']) if (process.env[name]) env[name] = process.env[name];
env.PATH = path.join(process.env.SystemRoot, 'System32');
env.RENULUS_PROFILE = path.join(evidence, 'profile');
let attachedServer;
if (sourceDesktop) {
  const token = randomBytes(32).toString('hex'); let metadataRequests = 0;
  attachedServer = createServer(async (request, response) => {
    if (request.headers['x-renulus-token'] !== token) { response.writeHead(401).end(); return; }
    if (request.url === '/api/v1/meta') {
      if (++metadataRequests === 1) await new Promise(resolve => setTimeout(resolve, 1500));
      response.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify({ api_version: 1, version: '0.1.0', modules: {} }));
    } else response.writeHead(404, { 'Content-Type': 'application/json' }).end(JSON.stringify({ error: { code: 'synthetic_source_fixture', message: 'This native source journey supplies declared Library fixtures only.', retryable: false } }));
  });
  await new Promise(resolve => attachedServer.listen(0, '127.0.0.1', resolve));
  env.RENULUS_BACKEND_URL = 'http://127.0.0.1:' + attachedServer.address().port; env.RENULUS_SESSION_TOKEN = token;
}
const pdf = syntheticPdf();
await writeFile(path.join(evidence, 'synthetic-two-page.pdf'), pdf);
if (process.env.RENULUS_PDF_FIXTURE_ONLY === '1') { console.log(JSON.stringify({ fixture: path.join(evidence, 'synthetic-two-page.pdf') })); process.exit(0); }
const metadata = { source_id: 'native-viewer-fixture', source_owner: 'Renulus synthetic test', canonical_url: null, edition: 'Viewer fixture', publication_date: null, received_at: null, checked_at: null, publication_status: 'unverified', latest_final_verified: false, content_reviewed: false, collection_section: null, collection_chapter: null, notes: [] };
const rights = { display: true, cache: true, index: false, embedding: false, model_input: false, derivation: false, evaluation: false, redistribution: true, licence: 'Renulus synthetic test', permission_reference: 'Explicit test fixture', attribution: 'Renulus' };
const revision = { id: 'native-pdf-revision', document_id: 'native-pdf-document', ordinal: 1, status: 'ready', sha256: createHash('sha256').update(pdf).digest('hex'), media_type: 'application/pdf', bytes: pdf.length, passage_count: 0, metadata, rights };
const document = { id: revision.document_id, title: 'Synthetic two-page PDF viewer fixture', source_id: metadata.source_id, status: 'ready', reserved: false, active_revision: revision.id, latest_revision: revision.id, revisions: [revision], cleanup_pending: false };
const citation = { document_id: document.id, document_revision: revision.id, title: document.title, page: 2, locators: [{ item_ref: 'synthetic-page-two', page: 2, char_span: [0, 18] }], original_url: '/library/revisions/native-pdf-revision/original' };
let application;
const result = { checkedAt: new Date().toISOString(), executable, sourceProvenance, pdfFixture: { sha256: revision.sha256, pages: 2, citationPage: 2 }, limits: ['Library DTO/original requests use declared synthetic fixtures; no parsing/indexing proof', 'No account, provider inference or private original', 'System-browser observation recorded separately'] };
if (sourceDesktop) result.limits.push('Unchanged committed source main/preload/renderer with attached fixture metadata; not an installed app or real backend/Home/module/managed-child readiness proof');
try {
  const startedAt = Date.now();
  application = await electron.launch({ executablePath: executable, args: sourceDesktop ? [sourceDesktop] : [], cwd: sourceDesktop ?? path.dirname(executable), env, timeout: sourceDesktop ? 45_000 : 360_000 });
  const { page, ...windowTiming } = await waitForFlowWindow(application, { startedAt, timeout: sourceDesktop ? 45_000 : 360_000, requireHeading: !sourceDesktop });
  result.windowTiming = windowTiming;
  const meta = await page.evaluate(async () => { const response = await fetch('/api/v1/meta'); return { status: response.status, value: await response.json() }; });
  if (meta.status !== 200 || meta.value.api_version !== 1) throw new Error('The native renderer did not authenticate its backend.');
  result.windowTiming[sourceDesktop ? 'fixtureMetadataReadySeconds' : 'backendReadySeconds'] = (Date.now() - startedAt) / 1000;
  result.native = await application.evaluate(({ app }) => ({ packaged: app.isPackaged, version: process.versions.electron, executable: process.execPath }));
  if (result.native.packaged !== !sourceDesktop || result.native.version !== expectedVersion) throw new Error('The patched Electron and declared source/package mode are required.');
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.route(url => url.pathname === '/api/v1/library/documents', route => route.fulfill({ json: { documents: [document], total: 1, counts: { ready: 1 }, offset: 0, limit: 25 } }));
  await page.route(url => url.pathname === '/api/v1/library/documents/native-pdf-document', route => route.fulfill({ json: document }));
  await page.route('**/api/v1/library/revisions/native-pdf-revision/citation*', route => route.fulfill({ json: citation }));
  await page.route('**/api/v1/library/revisions/native-pdf-revision/original', route => route.fulfill({ status: 200, contentType: 'application/pdf', body: pdf }));
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Library', exact: true }).click();
  await page.getByRole('button', { name: document.title, exact: true }).click();
  const pdfConsole = [], requestFailures = [];
  page.on('console', message => { if (pdfConsole.length < 50) pdfConsole.push({ type: message.type(), text: message.text().slice(0, 3000) }); });
  page.on('requestfailed', request => { if (requestFailures.length < 50) requestFailures.push({ url: request.url(), failure: request.failure() }); });
  await page.getByRole('button', { name: 'Open original · page 2', exact: true }).click();
  const viewer = page.getByTitle('Original document viewer', { exact: true }); await viewer.waitFor(); await page.waitForTimeout(3000);
  result.pdfViewer = { requestedUrl: await viewer.getAttribute('src'), frames: await capturePdfFrames(page), console: pdfConsole, requestFailures };
  await viewer.screenshot({ path: path.join(evidence, 'library-pdf-viewer.png') });
  await page.screenshot({ path: path.join(evidence, 'library-source-reader.png'), fullPage: true });
  Object.assign(result.pdfViewer, classifyPdfFrames(result.pdfViewer.frames, citation.page));
  result.pdfViewer.visualReview = 'required: confirm PAGE TWO marker in captured native viewer';
  await application.evaluate(({ shell }) => {
    globalThis.renulusPublisherProof = [];
    const original = shell.openExternal.bind(shell);
    shell.openExternal = async (url, options) => { const record = { url, state: 'requested' }; globalThis.renulusPublisherProof.push(record); try { const value = await original(url, options); record.state = 'OS-open-completed'; return value; } catch (error) { record.state = 'failed'; record.message = error.message; throw error; } };
  });
  if (sourceDesktop) {
    result.publisher = { href: 'https://kdigo.org/guidelines/', rendererUrl: page.url(), kind: 'actual public source IPC; Updates link UI remains a packaged producer check' };
    await page.evaluate(url => window.renulus.openSource(url), result.publisher.href);
  } else {
    await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Updates', exact: true }).click();
    await page.getByRole('button', { name: 'Source checks', exact: true }).click();
    const publisher = page.locator('.source-check-list a[href^="https://kdigo.org/"]').first(); await publisher.waitFor();
    result.publisher = { href: await publisher.getAttribute('href'), label: await publisher.innerText(), rendererUrl: page.url() }; await publisher.click();
  }
  await page.waitForTimeout(1000);
  result.publisher.dispatch = await application.evaluate(() => globalThis.renulusPublisherProof);
  result.publisher.sourceBridge = { available: await page.evaluate(() => typeof window.renulus?.openSource === 'function') };
  if (process.env.RENULUS_EXPECT_SOURCE_BRIDGE === '1' && !result.publisher.sourceBridge.available) throw new Error('The required native source bridge is missing.');
  if (result.publisher.sourceBridge.available && sourceDesktop) {
    result.publisher.sourceBridge.dispatch = result.publisher.dispatch;
  } else if (result.publisher.sourceBridge.available) {
    const before = result.publisher.dispatch.length;
    await page.evaluate(url => window.renulus.openSource(url), result.publisher.href);
    result.publisher.sourceBridge.dispatch = (await application.evaluate(() => globalThis.renulusPublisherProof)).slice(before);
    if (!result.publisher.sourceBridge.dispatch.some(record => record.url === result.publisher.href && record.state === 'OS-open-completed')) throw new Error('The public HTTPS source bridge did not complete a system-browser dispatch.');
  }
  result.publisher.rendererWindows = await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().length);
  result.publisher.rendererStayedLocal = page.url() === result.publisher.rendererUrl;
  if (!result.publisher.dispatch.some(record => record.url === result.publisher.href && record.state === 'OS-open-completed') || result.publisher.rendererWindows !== 1 || !result.publisher.rendererStayedLocal) throw new Error('The publisher link did not complete a system-browser dispatch.');
  if (result.pdfViewer.blocked || !result.pdfViewer.viewerDetected || !result.pdfViewer.citationPageSelected) throw new Error('The native PDF viewer failed to show the requested physical page. Inspect its frame, console and screenshot evidence.');
  if (process.env.RENULUS_EXPECT_PRODUCT_BACKUP === '1') {
    if (sourceDesktop) throw new Error('The actual producer archive gate requires a packaged managed backend.');
    result.productBackup = await proveNativeProductBackup(application, page, evidence, executable, env);
  }
} catch (error) { result.error = { message: error.message, stack: error.stack }; }
finally {
  if (application) await application.close();
  if (attachedServer) { attachedServer.closeAllConnections(); await new Promise(resolve => attachedServer.close(resolve)); }
  await writeFile(path.join(evidence, 'journey-evidence.json'), JSON.stringify(result, null, 2));
}
console.log(JSON.stringify({ evidence, error: result.error?.message, pdfViewerBlocked: result.pdfViewer?.blocked, publisher: result.publisher }));
if (result.error) process.exitCode = 1;
