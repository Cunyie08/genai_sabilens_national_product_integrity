/**
 * scan-page.ts
 *
 * Page-object helper: drives the SabiLens upload scan flow and returns the
 * verdict, confidence, and "why flagged" text from the result page.
 *
 * Upload flow (mirrors ScanScreen.jsx upload mode):
 *   /scan → click "Gallery" → Upload Images UI appears
 *   → click Front slot  → file chooser → setFiles(front)
 *   → click Back slot   → file chooser → setFiles(back)
 *   → click "Analyse Both Images"
 *   → wait for /scan/(safe|fake|suspicious|rescan)
 *   → read verdict heading, confidence %, and why-text
 */

import { Page } from '@playwright/test';
import * as path from 'path';
import * as fs   from 'fs';

export type Verdict = 'AUTHENTIC' | 'FAKE' | 'SUSPICIOUS' | 'RESCAN_REQUIRED' | 'UNKNOWN';

export interface ScanResult {
  verdict:        Verdict;
  verdictHeading: string;   // raw h1 text: "SAFE TO BUY" / "DO NOT BUY" / "PROCEED WITH CAUTION"
  confidence:     string;   // e.g. "92%"
  whyText:        string;   // content of the "Why this product is…" section
  screenshotPath: string;   // absolute path of the full-page result screenshot
}

const URL_TO_VERDICT: Record<string, Verdict> = {
  '/scan/safe':       'AUTHENTIC',
  '/scan/fake':       'FAKE',
  '/scan/suspicious': 'SUSPICIOUS',
  '/scan/rescan':     'RESCAN_REQUIRED',
};

export async function runUploadScan(
  page:    Page,
  opts: {
    frontImage:    string;   // absolute path
    backImage:     string;   // absolute path
    screenshotDir: string;   // directory to write step screenshots into
    productName:   string;   // slug used in screenshot filenames
  },
): Promise<ScanResult> {
  const { frontImage, backImage, screenshotDir, productName } = opts;
  fs.mkdirSync(screenshotDir, { recursive: true });

  const shot = (step: string) =>
    path.join(screenshotDir, `${productName}_${step}.png`);

  // ── Step 1: scan page ──────────────────────────────────────────────────────
  await page.goto('/scan');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: shot('01_scan_page'), fullPage: false });

  // ── Step 2: open upload mode ───────────────────────────────────────────────
  // Gallery button: bottom-left, contains a <span>Gallery</span>
  await page.getByText('Gallery', { exact: true }).click();
  await page.getByRole('heading', { name: 'Upload Images' }).waitFor({ timeout: 8_000 });
  await page.screenshot({ path: shot('02_upload_mode') });

  // ── Step 3a: upload front image ────────────────────────────────────────────
  // The two slot buttons are inside the 2-column grid. The single hidden
  // <input type="file"> is clicked programmatically by openSlotPicker(slot).
  // Playwright intercepts the resulting file-chooser event.
  const slotButtons = page.locator('.grid.grid-cols-2 button');

  const [frontChooser] = await Promise.all([
    page.waitForEvent('filechooser'),
    slotButtons.nth(0).click(),
  ]);
  await frontChooser.setFiles(frontImage);

  // Green tick (.bg-green-500.rounded-full) appears over the slot when the
  // image has been resized and stored in uploadSlots[0]
  await slotButtons.nth(0)
    .locator('.bg-green-500.rounded-full')
    .waitFor({ timeout: 15_000 });
  await page.screenshot({ path: shot('03_front_selected') });

  // ── Step 3b: upload back image ─────────────────────────────────────────────
  const [backChooser] = await Promise.all([
    page.waitForEvent('filechooser'),
    slotButtons.nth(1).click(),
  ]);
  await backChooser.setFiles(backImage);

  await slotButtons.nth(1)
    .locator('.bg-green-500.rounded-full')
    .waitFor({ timeout: 15_000 });
  await page.screenshot({ path: shot('04_both_selected') });

  // ── Step 4: submit ─────────────────────────────────────────────────────────
  const analyseBtn = page.getByRole('button', { name: /Analyse Both Images/i });
  await analyseBtn.waitFor({ state: 'visible', timeout: 5_000 });
  await analyseBtn.click();

  // Loading indicator appears — multiple elements contain "Analysing", use first()
  await page.getByText(/Analysing/i).first().waitFor({ timeout: 10_000 });
  await page.screenshot({ path: shot('05_analysing') });

  // ── Step 5: wait for result page ──────────────────────────────────────────
  // AI pipeline can take up to 60 s; give it 2 min.
  await page.waitForURL(/\/scan\/(safe|fake|suspicious|rescan)$/, { timeout: 120_000 });
  await page.waitForLoadState('networkidle');
  const resultPath = shot('06_result');
  await page.screenshot({ path: resultPath, fullPage: true });

  // ── Step 6: read verdict ───────────────────────────────────────────────────
  const urlPath = new URL(page.url()).pathname;
  const verdict: Verdict = URL_TO_VERDICT[urlPath] ?? 'UNKNOWN';

  const verdictHeading = (await page.locator('h1').first().textContent()) ?? '';

  // Confidence: "XX%" displayed next to the confidence label
  let confidence = 'N/A';
  try {
    // Looks for a bold span that ends with "%"
    const confSpan = page.locator('span.font-bold').filter({ hasText: /%$/ }).first();
    confidence = (await confSpan.textContent({ timeout: 3_000 })) ?? 'N/A';
  } catch { /* not present on all result variants */ }

  // "Why" text: section headed "Why this product is…" (verified/flagged)
  let whyText = '';
  try {
    const whyHeader = page.locator('h3').filter({ hasText: /Why this product/i }).first();
    // Walk up to the containing div, then read all text within it
    const container = whyHeader.locator('xpath=..');
    whyText = (await container.textContent({ timeout: 3_000 })) ?? '';
    // Trim to the relevant part (strip the heading itself)
    whyText = whyText.replace(/Why this product is (verified|flagged):/i, '').trim();
  } catch { /* section may be absent */ }

  return { verdict, verdictHeading, confidence, whyText, screenshotPath: resultPath };
}
