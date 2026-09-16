import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(frontendRoot, "..");
const target = resolve(frontendRoot, "src/generated/api.ts");
const checkOnly = process.argv.includes("--check");
const python = spawnSync("python", [
  "-c",
  "import json; from src.api.app import app; print(json.dumps(app.openapi(), ensure_ascii=False))",
], { cwd: repositoryRoot, encoding: "utf8" });

if (python.status !== 0) {
  console.error(python.stderr || "Unable to load FastAPI OpenAPI schema.");
  process.exit(python.status || 1);
}

const schema = JSON.parse(python.stdout);
const output = "// Generated from FastAPI. Do not edit by hand.\n" + astToString(await openapiTS(schema));
if (checkOnly) {
  if (!existsSync(target) || readFileSync(target, "utf8") !== output) {
    console.error("Generated API types are stale. Run npm run api:generate.");
    process.exit(1);
  }
  console.log("Generated API types are up to date.");
} else {
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, output, "utf8");
  console.log("Generated " + target);
}
