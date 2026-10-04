/** Packaged viewer/source proof. Library DTO/PDF fixtures are synthetic, not ingestion evidence. */
import { _electron as electron } from '@playwright/test';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { randomUUID, createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { waitForFlowWindow } from './wait-for-flow-window.mjs';
const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const executable = process.env.RENULUS_PACKAGED_EXECUTABLE;
if (!executable || !path.isAbsolute(executable)) throw new Error('An explicit packaged executable is required.');
await mkdir(path.join(desktop, 'test-results'), { recursive: true });
const evidence = path.join(desktop, 'test-results', 'journeys-' + randomUUID().slice(0, 8));
await mkdir(evidence);
const expectedVersion = JSON.parse(await readFile(path.join(desktop, 'package.json'), 'utf8')).devDependencies.electron;
const env = {};
for (const name of ['SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA']) if (process.env[name]) env[name] = process.env[name];
env.PATH = path.join(process.env.SystemRoot, 'System32');
env.RENULUS_PROFILE = path.join(evidence, 'profile');
function syntheticPdf() {
  const stream = page => ['0.95 0.98 0.97 rg 0 0 380 480 re f', '0.1 0.4 0.35 rg BT /F1 24 Tf 38 425 Td (RENULUS - PAGE ' + page + ') Tj ET', 'BT /F1 15 Tf 38 390 Td (Synthetic PDF viewer fixture) Tj ET', 'BT /F1 120 Tf 150 180 Td (' + (page === 'ONE' ? '1' : '2') + ') Tj ET', 'BT /F1 13 Tf 38 45 Td (Not clinical or patient material) Tj ET'].join('\n') + '\n';
  const one = stream('ONE'), two = stream('TWO');
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>', '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 380 480] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>', '<< /Length ' + Buffer.byteLength(one) + ' >>\nstream\n' + one + 'endstream', '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 380 480] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>', '<< /Length ' + Buffer.byteLength(two) + ' >>\nstream\n' + two + 'endstream', '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'];
  let body = '%PDF-1.4\n'; const offsets = [0];
  for (let i = 0; i < objects.length; i++) { offsets.push(Buffer.byteLength(body)); body += (i + 1) + ' 0 obj\n' + objects[i] + '\nendobj\n'; }
  const xref = Buffer.byteLength(body);
  body += 'xref\n0 ' + offsets.length + '\n0000000000 65535 f \n' + offsets.slice(1).map(offset => String(offset).padStart(10, '0') + ' 00000 n \n').join('');
  return Buffer.from(body + 'trailer\n<< /Size ' + offsets.length + ' /Root 1 0 R >>\nstartxref\n' + xref + '\n%%EOF\n');
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
const result = { checkedAt: new Date().toISOString(), executable, pdfFixture: { sha256: revision.sha256, pages: 2, citationPage: 2 }, limits: ['Library DTO/original requests use declared synthetic fixtures; no parsing/indexing proof', 'No account, provider inference or private original', 'System-browser observation recorded separately'] };
try {
  const startedAt = Date.now();
  application = await electron.launch({ executablePath: executable, cwd: path.dirname(executable), env, timeout: 360_000 });
  const { page, ...windowTiming } = await waitForFlowWindow(application, { startedAt });
  result.windowTiming = windowTiming;
  const meta = await page.evaluate(async () => { const response = await fetch('/api/v1/meta'); return { status: response.status, value: await response.json() }; });
  if (meta.status !== 200 || meta.value.api_version !== 1) throw new Error('The native renderer did not authenticate its backend.');
  result.windowTiming.backendReadySeconds = (Date.now() - startedAt) / 1000;
  result.native = await application.evaluate(({ app }) => ({ packaged: app.isPackaged, version: process.versions.electron, executable: process.execPath }));
  if (!result.native.packaged || result.native.version !== expectedVersion) throw new Error('The patched packaged Electron is required.');
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.route(url => url.pathname === '/api/v1/library/documents', route => route.fulfill({ json: { documents: [document] } }));
  await page.route(url => url.pathname === '/api/v1/library/documents/native-pdf-document', route => route.fulfill({ json: document }));
  await page.route('**/api/v1/library/revisions/native-pdf-revision/citation*', route => route.fulfill({ json: citation }));
  await page.route('**/api/v1/library/revisions/native-pdf-revision/original', route => route.fulfill({ status: 200, contentType: 'application/pdf', body: pdf }));
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Library', exact: true }).click();
  await page.getByRole('button', { name: document.title, exact: true }).click();
  await page.getByRole('button', { name: 'Open original · page 2', exact: true }).click();
  const viewer = page.getByTitle('Original document viewer', { exact: true }); await viewer.waitFor(); await page.waitForTimeout(3000);
  result.pdfViewer = { requestedUrl: await viewer.getAttribute('src'), frames: [] };
  for (const frame of page.frames().filter(frame => frame !== page.mainFrame())) {
    try {
      result.pdfViewer.frames.push({ url: frame.url(), ...await frame.evaluate(() => {
        const inputs = [];
        function scan(root) { for (const element of root.querySelectorAll('*')) { if (element.tagName === 'INPUT') inputs.push({ id: element.id, type: element.type, value: element.value }); if (element.shadowRoot) scan(element.shadowRoot); } }
        scan(document);
        return { readyState: document.readyState, body: document.body?.innerText.slice(0, 700), embeds: [...document.querySelectorAll('embed')].map(element => ({ type: element.type, src: element.src })), inputs };
      }) });
    } catch (error) { result.pdfViewer.frames.push({ url: frame.url(), error: error.message }); }
  }
  await viewer.screenshot({ path: path.join(evidence, 'library-pdf-viewer.png') });
  await page.screenshot({ path: path.join(evidence, 'library-source-reader.png'), fullPage: true });
  result.pdfViewer.blocked = result.pdfViewer.frames.some(frame => /ERR_BLOCKED|blocked|refused/i.test(frame.body ?? ''));
  result.pdfViewer.visualReview = 'required: confirm PAGE TWO marker in captured native viewer';
  await application.evaluate(({ shell }) => {
    globalThis.renulusPublisherProof = [];
    const original = shell.openExternal.bind(shell);
    shell.openExternal = async (url, options) => { const record = { url, state: 'requested' }; globalThis.renulusPublisherProof.push(record); try { const value = await original(url, options); record.state = 'OS-open-completed'; return value; } catch (error) { record.state = 'failed'; record.message = error.message; throw error; } };
  });
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Updates', exact: true }).click();
  await page.getByRole('button', { name: 'Source checks', exact: true }).click();
  const publisher = page.locator('.source-check-list a[href^="https://kdigo.org/"]').first(); await publisher.waitFor();
  result.publisher = { href: await publisher.getAttribute('href'), label: await publisher.innerText(), rendererUrl: page.url() }; await publisher.click(); await page.waitForTimeout(2000);
  result.publisher.dispatch = await application.evaluate(() => globalThis.renulusPublisherProof);
  result.publisher.rendererWindows = await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().length);
  result.publisher.rendererStayedLocal = page.url() === result.publisher.rendererUrl;
  if (!result.publisher.dispatch.some(record => record.url === result.publisher.href && record.state === 'OS-open-completed') || result.publisher.rendererWindows !== 1 || !result.publisher.rendererStayedLocal) throw new Error('The publisher link did not complete a system-browser dispatch.');
} catch (error) { result.error = { message: error.message, stack: error.stack }; }
finally { if (application) await application.close(); await writeFile(path.join(evidence, 'journey-evidence.json'), JSON.stringify(result, null, 2)); }
console.log(JSON.stringify({ evidence, error: result.error?.message, pdfViewerBlocked: result.pdfViewer?.blocked, publisher: result.publisher }));
if (result.error) process.exitCode = 1;
