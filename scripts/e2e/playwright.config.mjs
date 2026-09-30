import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));

export default {
  testDir: scriptDir,
  testMatch: "app.integration.spec.mjs",
  fullyParallel: false,
  reporter: "line",
  timeout: 45_000,
  expect: { timeout: 8_000 },
  outputDir: path.resolve(scriptDir, "../../frontend/test-results/fullstack-e2e"),
  use: {
    baseURL: "http://127.0.0.1",
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
};
