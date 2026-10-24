import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { EOL, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(frontendRoot, "..");
const target = resolve(frontendRoot, "src/generated/api.ts");
const checkOnly = process.argv.includes("--check");
const isolatedProfile = mkdtempSync(join(tmpdir(), "otp-lol-openapi-"));
let python;
try {
  python = spawnSync("python", [
    "-c",
    "import json, logging; logging.disable(logging.CRITICAL); from src.api.app import app; logging.disable(logging.NOTSET); print(json.dumps(app.openapi(), ensure_ascii=False))",
  ], {
    cwd: repositoryRoot,
    encoding: "utf8",
    env: {
      ...process.env,
      APPDATA: join(isolatedProfile, "Roaming"),
      LOCALAPPDATA: join(isolatedProfile, "Local"),
      TEMP: isolatedProfile,
      TMP: isolatedProfile,
      OTP_LOL_LOG_LEVEL: "CRITICAL",
    },
  });
} finally {
  rmSync(isolatedProfile, { recursive: true, force: true });
}

if (python.status !== 0) {
  console.error(python.stderr || "Unable to load FastAPI OpenAPI schema.");
  process.exit(python.status || 1);
}

const schema = JSON.parse(python.stdout);
const output = "// Generated from FastAPI. Do not edit by hand.\n" + astToString(await openapiTS(schema));
const normalizedOutput = output.replace(/\r\n/g, "\n");
if (checkOnly) {
  if (!existsSync(target) || readFileSync(target, "utf8").replace(/\r\n/g, "\n") !== normalizedOutput) {
    console.error("Generated API types are stale. Run npm run api:generate.");
    process.exit(1);
  }
  console.log("Generated API types are up to date.");
} else {
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, normalizedOutput.replace(/\n/g, EOL), "utf8");
  console.log("Generated " + target);
}
