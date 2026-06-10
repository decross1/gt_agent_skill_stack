#!/usr/bin/env node
// screenshot_brain.mjs — playwright screenshot harness for the brain view pages.
//
// The framework repo carries no JS toolchain, so playwright is resolved from a
// shared tools checkout (override with PW_DIR):
//
//   node scripts/screenshot_brain.mjs [--base URL] [--out DIR]
//
// Shoots dashboard.html + graph.html at a 1440x900 viewport, fullPage. Every
// shot is written and its path printed; any console error / page error / bad
// HTTP status on either page fails the run (exit 1) after the shots land.

import { mkdir } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const pwDir = process.env.PW_DIR || '/home/decross1/projects/ui_overhaul_gallery/tools';
const { chromium } = await import(
  pathToFileURL(path.join(pwDir, 'node_modules/playwright/index.mjs'))
);

const PAGES = ['dashboard.html', 'graph.html'];

function parseArgs(argv) {
  const args = {
    base: 'http://localhost:5174',
    out: '/home/decross1/projects/ui_overhaul_gallery/latest',
  };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--base' && argv[i + 1]) args.base = argv[++i];
    else if (argv[i] === '--out' && argv[i + 1]) args.out = argv[++i];
    else {
      console.error(`unknown arg: ${argv[i]}`);
      console.error('usage: screenshot_brain.mjs [--base URL] [--out DIR]');
      process.exit(2);
    }
  }
  return args;
}

const { base, out } = parseArgs(process.argv.slice(2));
await mkdir(out, { recursive: true });

const browser = await chromium.launch();
const errors = []; // { page, text }
const written = [];

try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  for (const name of PAGES) {
    const page = await context.newPage();
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push({ page: name, text: msg.text() });
    });
    page.on('pageerror', (err) => {
      errors.push({ page: name, text: `pageerror: ${err.message}` });
    });

    const url = `${base.replace(/\/+$/, '')}/${name}`;
    try {
      const resp = await page.goto(url, { waitUntil: 'load', timeout: 30000 });
      if (!resp || !resp.ok()) {
        errors.push({
          page: name,
          text: `HTTP ${resp ? resp.status() : '<no response>'} for ${url}`,
        });
      }
      // Settle late fetches/animation; a polling page never reaches
      // networkidle, so cap the wait and shoot anyway.
      await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
      await page.waitForTimeout(400);
      const file = path.join(out, name.replace(/\.html$/, '') + '.png');
      await page.screenshot({ path: file, fullPage: true });
      written.push(file);
    } catch (err) {
      errors.push({ page: name, text: `harness: ${err.message}` });
    } finally {
      await page.close();
    }
  }
} finally {
  await browser.close();
}

for (const f of written) console.log(`wrote ${f}`);
if (errors.length) {
  console.error(`\nFAIL: ${errors.length} console/page error(s):`);
  for (const e of errors) console.error(`  [${e.page}] ${e.text}`);
  process.exit(1);
}
console.log(`OK: ${written.length} page(s) shot clean (base=${base})`);
