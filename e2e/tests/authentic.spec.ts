/**
 * authentic.spec.ts
 *
 * Scans every front+back pair in AUTHENTIC_IMAGES_DIR and asserts each one
 * returns verdict=AUTHENTIC.  A failure here means a regression introduced a
 * false-positive counterfeit flag on a known-good product.
 *
 * Pairs are discovered by matching *_front.* with *_back.* / *_left.* files
 * that share the same filename prefix.
 */

import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs   from 'fs';
import * as dotenv from 'dotenv';
import { discoverPairs, ImagePair } from '../helpers/image-pairs';
import { runUploadScan, ScanResult } from '../helpers/scan-page';

dotenv.config({ path: path.resolve(__dirname, '../.env') });

const AUTHENTIC_DIR = process.env.AUTHENTIC_IMAGES_DIR
  ?? path.resolve(__dirname, '../../product_images/authentic_products');
const SCREENSHOT_DIR = path.resolve(__dirname, '../screenshots/authentic');

// ── Discover pairs at collection time ────────────────────────────────────────
let pairs: ImagePair[] = [];
try {
  pairs = discoverPairs(AUTHENTIC_DIR);
} catch (err) {
  console.error(`[authentic.spec] Could not discover pairs: ${(err as Error).message}`);
}

// Summary table accumulated across tests
const summary: Array<{
  product:    string;
  expected:   string;
  actual:     string;
  pass:       boolean;
  confidence: string;
  screenshot: string;
}> = [];

// ── Tests ─────────────────────────────────────────────────────────────────────
test.describe('Authentic products → expect AUTHENTIC verdict', () => {

  test.beforeAll(() => {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
    if (pairs.length === 0) {
      console.warn(`[authentic.spec] No pairs found in: ${AUTHENTIC_DIR}`);
    } else {
      console.log(`[authentic.spec] ${pairs.length} pair(s) to test in: ${AUTHENTIC_DIR}`);
    }
  });

  if (pairs.length === 0) {
    test('SKIP — no image pairs discovered', () => {
      test.skip(true, `No front+back pairs found in ${AUTHENTIC_DIR}`);
    });
  }

  for (const pair of pairs) {
    test(`${pair.name}`, async ({ page }) => {
      const slug = pair.name.replace(/[^\w-]/g, '_').slice(0, 50);

      const result: ScanResult = await runUploadScan(page, {
        frontImage:    pair.front,
        backImage:     pair.back,
        screenshotDir: SCREENSHOT_DIR,
        productName:   slug,
      });

      const pass = result.verdict === 'AUTHENTIC';
      summary.push({
        product:    pair.name,
        expected:   'AUTHENTIC',
        actual:     result.verdict,
        pass,
        confidence: result.confidence,
        screenshot: result.screenshotPath,
      });

      console.log(
        `  [${pass ? 'PASS' : 'FAIL'}] ${pair.name}\n` +
        `    verdict:    ${result.verdict} (${result.verdictHeading})\n` +
        `    confidence: ${result.confidence}\n` +
        `    screenshot: ${result.screenshotPath}`
      );

      expect(result.verdict,
        `"${pair.name}" returned ${result.verdict} — expected AUTHENTIC.\n` +
        `Heading: "${result.verdictHeading}"\n` +
        `Why text: ${result.whyText}\n` +
        `Screenshot: ${result.screenshotPath}`
      ).toBe('AUTHENTIC');
    });
  }

  test.afterAll(async () => {
    if (summary.length === 0) return;
    const passed = summary.filter(r => r.pass).length;
    console.log(`\n${'─'.repeat(70)}`);
    console.log(`AUTHENTIC PRODUCTS SUMMARY  ${passed}/${summary.length} passed`);
    console.log(`${'─'.repeat(70)}`);
    console.log(
      'Product'.padEnd(45) +
      'Expected'.padEnd(12) +
      'Actual'.padEnd(15) +
      'Conf'.padEnd(8) +
      'Result'
    );
    for (const r of summary) {
      console.log(
        r.product.slice(0, 44).padEnd(45) +
        r.expected.padEnd(12) +
        r.actual.padEnd(15) +
        r.confidence.padEnd(8) +
        (r.pass ? 'PASS' : 'FAIL')
      );
    }
    console.log(`${'─'.repeat(70)}\n`);
    console.log(`Screenshots in: ${SCREENSHOT_DIR}`);
  });
});
