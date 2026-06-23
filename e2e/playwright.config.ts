import { defineConfig } from '@playwright/test';
import * as dotenv from 'dotenv';
import * as path from 'path';

dotenv.config({ path: path.resolve(__dirname, '.env') });

const BASE_URL = process.env.BASE_URL ?? 'https://sabilens.com';

export default defineConfig({
  testDir:  './tests',
  timeout:  180_000,   // 3 min — AI pipeline can take 60 s per scan
  expect:   { timeout: 15_000 },
  retries:  0,
  workers:  1,         // sequential: avoids flooding the production DB

  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],

  use: {
    baseURL: BASE_URL,

    // Mobile-first UI — iPhone 14 viewport
    viewport:   { width: 390, height: 844 },

    // Lagos coordinates — satisfies the geolocation requirement
    geolocation: { latitude: 6.5244, longitude: 3.3792 },
    permissions: ['geolocation'],

    // Session reuse from global-setup
    storageState: path.resolve(__dirname, '.auth/consumer.json'),

    screenshot: 'on',
    trace:      'on-first-retry',
    video:      'retain-on-failure',
  },

  globalSetup: './global-setup.ts',

  projects: [
    {
      name: 'chromium-mobile',
      use: { browserName: 'chromium' },
    },
  ],
});
