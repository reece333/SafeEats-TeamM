import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  // ✅ Only run tests in this directory
  testDir: './e2e',

  // ✅ Only pick up files that look like E2E specs, not Jest tests
  testMatch: '**/*.spec.ts',

  use: {
    baseURL: 'http://localhost:3000', // CRA dev server default
    headless: true,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});

