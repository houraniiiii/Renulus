import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

const evidence = path.resolve('test-results', 'browser-' + randomUUID());
await mkdir(evidence, { recursive: true });
const browser = await chromium.launchPersistentContext(path.join(evidence, 'profile'), { executablePath: process.env.RENULUS_TEST_BROWSER ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, viewport: { width: 1440, height: 960 } });
const page = await browser.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const results = [];
let connections;
try {
  await page.goto(process.env.RENULUS_PREVIEW_URL ?? 'http://127.0.0.1:5191'); await page.waitForSelector('h1'); await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(evidence, 'flow-browser-desktop.png'), fullPage: true });
  for (const label of ['Learn', 'Library', 'Cases', 'Test', 'Memory', 'Updates', 'Connections', 'Today']) {
    await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: label, exact: true }).click(); await page.waitForFunction(label => document.title === 'Renulus · ' + label, label); results.push({ route: label, h1: await page.locator('h1').innerText() });
    if (label === 'Connections') {
      await page.getByRole('region', { name: 'Learning subscriptions' }).waitFor();
      connections = await page.evaluate(async () => { const response = await fetch('/api/v1/connections'); if (!response.ok) throw new Error('Connections API failed'); return response.json(); });
      if (connections.selected_provider !== null || connections.connections.some(connection => connection.status !== 'disconnected')) throw new Error('Use a disconnected development profile for this synthetic proof.');
      await page.screenshot({ path: path.join(evidence, 'flow-browser-connections.png'), fullPage: true });
    }
  }
  await page.getByRole('button', { name: 'End temporary context' }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Open navigation' }).click(); await page.getByRole('navigation').getByRole('link', { name: 'Connections', exact: true }).click();
  await page.getByRole('region', { name: 'Learning subscriptions' }).waitFor();
  const overflow = await page.evaluate(() => ({ width: window.innerWidth, scroll: document.documentElement.scrollWidth }));
  if (overflow.scroll > overflow.width) throw new Error('Compact browser viewport overflows.');
  await page.screenshot({ path: path.join(evidence, 'flow-browser-compact.png'), fullPage: true });
  if (errors.length) throw new Error('Renderer errors: ' + errors.join('; '));
  await writeFile(path.join(evidence, 'browser-evidence.json'), JSON.stringify({ checkedAt: new Date().toISOString(), routes: results, connections, overflow, pageErrors: errors, limits: ['Feature entries remain integration states', 'No provider login or inference'] }, null, 2));
} finally { await browser.close(); }
console.log(JSON.stringify({ evidence, routes: results.length, pageErrors: errors.length, visualCaptures: 3 }));
