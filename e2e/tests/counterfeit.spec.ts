/**
 * counterfeit.spec.ts
 *
 * Scans every front+back pair from DOCTORED_IMAGES_DIR and asserts each one
 * returns a verdict that is NOT AUTHENTIC (i.e. FAKE or SUSPICIOUS).
 *
 * This is where the known false-negative bug surfaces:
 *   - doctored products carry a genuine NAFDAC number on the back panel
 *   - but the front panel / product name does not match the registered product
 *   - before commit af713a6 the system returned AUTHENTIC for these scans
 *   - after the fix it should return FAKE (IDENTITY_MISMATCH override)
 *
 * Pairs are driven by pairs.json in the doctored folder so that intentionally
 * mismatched filenames (e.g. cocoa_pups_front + coco_pops_left) are explicit.
 */

import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs   from 'fs';
import * as dotenv from 'dotenv';
import { discoverPairs, ImagePair } from '../helpers/image-pairs';
import { runUploadScan, ScanResult } from '../helpers/scan-page';

dotenv.config({ path: path.resolve(__dirname, '../.env') });

const DOCTORED_DIR = process.env.DOCTORED_IMAGES_DIR
  ?? path.resolve(__dirname, '../../product_images/doctored_products');
const SCREENSHOT_DIR = path.resolve(__dirname, '../screenshots/counterfeit');

// ── Discover pairs at collection time ────────────────────────────────────────
let pairs: ImagePair[] = [];
try {
  pairs = discoverPairs(DOCTORED_DIR);
} catch (err) {
  console.error(`[counterfeit.spec] Could not discover pairs: ${(err as Error).message}`);
}

const summary: Array<{
  product:    string;
  expected:   string;
  actual:     string;
  pass:       boolean;
  confidence: string;
  whyText:    string;
  screenshot: string;
}> = [];

// ── Tests ─────────────────────────────────────────────────────────────────────
test.describe('Doctored products → expect NOT AUTHENTIC verdict', () => {

  test.beforeAll(() => {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
    if (pairs.length === 0) {
      console.warn(`[counterfeit.spec] No pairs found in: ${DOCTORED_DIR}`);
    } else {
      console.log(`[counterfeit.spec] ${pairs.length} pair(s) to test in: ${DOCTORED_DIR}`);
    }
  });

  if (pairs.length === 0) {
    test('SKIP — no image pairs discovered', () => {
      test.skip(true, `No pairs found in ${DOCTORED_DIR}`);
    });
  }

  for (const pair of pairs) {
    test(`${pair.name} → FAKE or SUSPICIOUS (not AUTHENTIC)`, async ({ page }) => {
      const slug = pair.name.replace(/[^\w-]/g, '_').slice(0, 50);

      const result: ScanResult = await runUploadScan(page, {
        frontImage:    pair.front,
        backImage:     pair.back,
        screenshotDir: SCREENSHOT_DIR,
        productName:   slug,
      });

      const pass = result.verdict !== 'AUTHENTIC';
      summary.push({
        product:    pair.name,
        expected:   'FAKE or SUSPICIOUS',
        actual:     result.verdict,
        pass,
        confidence: result.confidence,
        whyText:    result.whyText,
        screenshot: result.screenshotPath,
      });

      // Detailed output so failures are immediately actionable
      console.log(
        `  [${pass ? 'PASS' : 'FAIL'}] ${pair.name}\n` +
        `    verdict:    ${result.verdict} (${result.verdictHeading})\n` +
        `    confidence: ${result.confidence}\n` +
        `    why:        ${result.whyText.replace(/\s+/g, ' ').slice(0, 250)}\n` +
        `    screenshot: ${result.screenshotPath}`
      );

      expect(
        result.verdict,
        // Message shown when the assertion fails (i.e. the bug is present)
        `BUG — "${pair.name}" returned AUTHENTIC.\n` +
        `  This is the false-negative: a genuine NAFDAC number on mismatched packaging\n` +
        `  was enough to pass verification instead of triggering IDENTITY_MISMATCH.\n` +
        `  Confidence: ${result.confidence}\n` +
        `  Why text: ${result.whyText}\n` +
        `  Screenshot: ${result.screenshotPath}`
      ).not.toBe('AUTHENTIC');
    });
  }

  test.afterAll(async () => {
    if (summary.length === 0) return;
    const passed = summary.filter(r => r.pass).length;
    console.log(`\n${'─'.repeat(70)}`);
    console.log(`COUNTERFEIT DETECTION SUMMARY  ${passed}/${summary.length} caught`);
    console.log(`${'─'.repeat(70)}`);
    console.log(
      'Product'.padEnd(45) +
      'Actual'.padEnd(15) +
      'Conf'.padEnd(8) +
      'Result'
    );
    for (const r of summary) {
      console.log(
        r.product.slice(0, 44).padEnd(45) +
        r.actual.padEnd(15) +
        r.confidence.padEnd(8) +
        (r.pass ? 'PASS' : 'FAIL ← BUG')
      );
    }
    console.log(`${'─'.repeat(70)}`);

    // Print "why" text for any failures (BUG cases where AUTHENTIC was returned)
    const failures = summary.filter(r => !r.pass);
    if (failures.length > 0) {
      console.log('\nFAILING CASES — why text received from frontend:');
      for (const r of failures) {
        console.log(`  ${r.product}: ${r.whyText.replace(/\s+/g, ' ').slice(0, 300)}`);
      }
    }
    console.log(`\nScreenshots in: ${SCREENSHOT_DIR}\n`);
  });
});
