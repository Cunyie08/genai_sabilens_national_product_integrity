/**
 * global-setup.ts
 *
 * Logs in once with test credentials and saves the browser storageState
 * (localStorage + cookies) to .auth/consumer.json.
 * All tests load this file via playwright.config.ts#use.storageState
 * so they skip the login flow entirely.
 */

import { chromium } from '@playwright/test';
import * as dotenv from 'dotenv';
import * as path from 'path';
import * as fs from 'fs';

dotenv.config({ path: path.resolve(__dirname, '.env') });

export default async function globalSetup() {
  const BASE_URL  = process.env.BASE_URL  ?? 'https://sabilens.com';
  const phone     = process.env.TEST_PHONE;
  const password  = process.env.TEST_PASSWORD;

  if (!phone || !password) {
    throw new Error(
      'TEST_PHONE and TEST_PASSWORD must be set in e2e/.env\n' +
      'Copy e2e/.env.example to e2e/.env and fill in the values.'
    );
  }

  const authDir = path.resolve(__dirname, '.auth');
  fs.mkdirSync(authDir, { recursive: true });
  const storageStatePath = path.join(authDir, 'consumer.json');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport:    { width: 390, height: 844 },
    geolocation: { latitude: 6.5244, longitude: 3.3792 },
    permissions: ['geolocation'],
  });
  const page = await context.newPage();

  console.log('[global-setup] Logging in…');
  await page.goto(`${BASE_URL}/login`);
  await page.waitForLoadState('networkidle');

  // Phone input (10 digits, no country code — the +234 prefix is cosmetic)
  await page.locator('input[name="phone"]').fill(phone);
  await page.locator('input[name="password"]').fill(password);
  await page.click('button[type="submit"]');

  // Login redirects to /home on success
  await page.waitForURL('**/home', { timeout: 30_000 });

  // Mark onboarding as seen so tests never hit the onboarding screen
  await page.evaluate(() => {
    localStorage.setItem('hasSeenOnboarding', 'true');
  });

  await context.storageState({ path: storageStatePath });
  await browser.close();

  console.log(`[global-setup] Auth saved → ${storageStatePath}`);
}
