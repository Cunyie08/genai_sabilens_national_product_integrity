import { test, expect } from '@playwright/test';

test.use({
  channel: 'chrome', // Use system chrome to avoid downloading browser binaries
  permissions: ['camera', 'geolocation'],
  launchOptions: {
    args: [
      '--use-fake-device-for-media-stream',
      '--use-fake-ui-for-media-stream'
    ]
  }
});

test.describe('Scan Screen Diagnostics', () => {

  test('Diagnose Scan Screen Blank Issue', async ({ page }) => {
    test.setTimeout(60000);
    const consoleLogs = [];
    const consoleErrors = [];

    page.on('console', msg => {
      consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    page.on('pageerror', err => {
      consoleErrors.push(`Uncaught Error: ${err.message}`);
    });

    // Mock the backend API responses so we don't need a running/reachable server
    await page.route('**/api/v1/auth/login', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            user: { id: 1, phone: '9187654321', first_name: 'Test', last_name: 'User', role: 'consumer' },
            tokens: { access_token: 'mock_access', refresh_token: 'mock_refresh' }
          }
        })
      });
    });

    await page.route('**/api/v1/auth/me', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: { id: 1, phone: '9187654321', first_name: 'Test', last_name: 'User', role: 'consumer' }
        })
      });
    });

    // 1. Login
    console.log('Navigating to login...');
    await page.goto('http://localhost:3000/login', { waitUntil: 'domcontentloaded' });
    
    console.log('Filling credentials...');
    await page.fill('input[type="tel"]', '9187654321');
    await page.fill('input[type="password"]', 'tegafresh12345*');
    await page.click('button[type="submit"]');

    // Wait for redirect to home
    console.log('Waiting for redirect to /home...');
    await page.waitForURL('**/home', { timeout: 15000 }).catch(() => console.log('Timeout waiting for /home'));

    // 2. Navigate to /scan
    console.log('Navigating to /scan...');
    await page.goto('http://localhost:3000/scan', { waitUntil: 'networkidle' });
    
    // Wait for 5 seconds to let the page settle and catch any async crashes
    await page.waitForTimeout(5000);

    // 3. Deep Inspection
    console.log('Running deep inspection...');
    
    const sharedArrayBufferType = await page.evaluate(() => typeof SharedArrayBuffer);
    console.log(`typeof SharedArrayBuffer: ${sharedArrayBufferType}`);

    const videoState = await page.evaluate(() => {
      const vid = document.querySelector('video');
      if (!vid) return 'No <video> element found';
      return `Video found. readyState: ${vid.readyState}`;
    });
    console.log(videoState);

    // Take screenshot regardless
    await page.screenshot({ path: 'debug_scan.png', fullPage: true });
    console.log('Screenshot saved to debug_scan.png');

    // Output all errors
    console.log('\n--- ALL CONSOLE ERRORS ---');
    consoleErrors.forEach(err => console.log(err));
    console.log('--------------------------\n');

    // Verify if it's blocked by SharedArrayBuffer
    if (sharedArrayBufferType === 'undefined' || consoleErrors.some(e => e.includes('SharedArrayBuffer'))) {
      console.log('DIAGNOSIS: SharedArrayBuffer is not defined or blocked.');
    } else {
      console.log('DIAGNOSIS: SharedArrayBuffer is defined.');
    }
  });
});
