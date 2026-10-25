import path from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));

export default {
  testDir: scriptDir,
  testMatch: "diagnostics-api.spec.mjs",
  fullyParallel: false,
  reporter: "line",
  timeout: 90_000,
  expect: { timeout: 10_000 },
  outputDir: path.join(tmpdir(), `otp-lol-e2e-diagnostics-api-${process.pid}`),
  use: {
    baseURL: "http://127.0.0.1",
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
};
