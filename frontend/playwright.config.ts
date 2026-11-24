import { defineConfig } from '@playwright/test'

// Runs against a live stack: Django on :8000 (seeded with `seed_company`) and Vite on :5173.
// E2E_USER / E2E_PASS must be a chief accountant of the seeded company.
// Set CHROME_PATH to use an installed Chrome instead of Playwright's download.
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  workers: 1,
  use: {
    baseURL: process.env.E2E_URL ?? 'http://127.0.0.1:5173',
    launchOptions: process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {},
  },
})
