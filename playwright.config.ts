import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000",
      port: 8000,
      reuseExistingServer: !process.env.CI,
      timeout: 30000,
      env: {
        ...process.env,
        // Deterministic e2e auth (overrides .env) + no engine for speed.
        AEGIS_ADMIN_TOKEN: "e2e-test-token",
        AEGIS_ENGINE_ENABLED: "false",
      },
    },
    {
      command: "npx vite --host 0.0.0.0 --port 5173",
      port: 5173,
      reuseExistingServer: !process.env.CI,
      timeout: 30000,
    },
  ],
});
