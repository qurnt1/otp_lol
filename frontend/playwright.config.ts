import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  workers: process.env.CI ? 2 : undefined,
  reporter: "line",
  timeout: 90_000,
  expect: { timeout: 10_000 },
  use: {
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
});
