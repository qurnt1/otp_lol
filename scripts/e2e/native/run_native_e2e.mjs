import assert from "node:assert/strict";
import { spawn, spawnSync, execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { once } from "node:events";
import fs from "node:fs/promises";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

if (process.platform !== "win32") throw new Error("The native WebView2 E2E proof is Windows-only.");

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "../../..");
const python = process.env.PYTHON ?? "python";
const nativeApp = path.join(scriptDir, "native_app.py");
const nativeDialog = path.join(scriptDir, "win32_dialog.py");
const frontendDir = path.join(repoRoot, "frontend");
const requireFromFrontend = createRequire(path.join(frontendDir, "package.json"));
const { chromium } = requireFromFrontend("@playwright/test");

function pythonJson(args) {
  const result = spawnSync(python, [nativeApp, ...args], {
    cwd: repoRoot,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
    encoding: "utf8",
    windowsHide: true,
    timeout: 10_000,
  });
  if (result.error) throw result.error;
  let payload;
  try {
    payload = JSON.parse(result.stdout.trim());
  } catch {
    throw new Error(`Native E2E helper returned invalid JSON: ${result.stderr.trim()}`);
  }
  return { ...result, payload };
}

function win32Json(args, timeout = 15_000) {
  const result = spawnSync(python, [nativeDialog, ...args], {
    cwd: repoRoot,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
    encoding: "utf8",
    windowsHide: true,
    timeout,
  });
  if (result.error) throw result.error;
  let payload;
  try {
    payload = JSON.parse(result.stdout.trim());
  } catch {
    throw new Error(`Native Win32 helper returned invalid JSON: ${result.stderr.trim() || result.stdout.trim()}`);
  }
  if (result.status !== 0) throw new Error(`Native Win32 helper failed: ${result.stderr.trim() || JSON.stringify(payload)}`);
  return payload;
}

async function waitForJsonFile(filePath, timeoutMs = 10_000) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      return JSON.parse(await fs.readFile(filePath, "utf8"));
    } catch (error) {
      if (error.code !== "ENOENT" && !(error instanceof SyntaxError)) throw error;
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error(`Native evidence file did not become readable: ${filePath} (${String(lastError)})`);
}

async function waitForSetting(page, key, expected, timeoutMs = 5_000) {
  const endpoint = new URL("/api/settings", page.url()).toString();
  const deadline = Date.now() + timeoutMs;
  let latest;
  while (Date.now() < deadline) {
    const response = await page.request.get(endpoint);
    assert.equal(response.status(), 200);
    latest = await response.json();
    if (latest[key] === expected) return latest;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Setting ${key} did not reach ${expected}: ${JSON.stringify(latest)}`);
}

async function waitForNativeWindow(appPid, predicate, timeoutMs = 5_000) {
  const deadline = Date.now() + timeoutMs;
  let latest;
  while (Date.now() < deadline) {
    latest = win32Json(["--app-pid", String(appPid), "--window-snapshot"]);
    if (predicate(latest)) return latest;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Native window did not reach its expected state: ${JSON.stringify(latest)}`);
}

async function lockFileSnapshot(lockfilePath) {
  const stat = await fs.stat(lockfilePath);
  let ownerPid = null;
  let readError = null;
  try {
    const contents = (await fs.readFile(lockfilePath, "utf8")).trim();
    if (/^\d+$/.test(contents)) ownerPid = Number(contents);
  } catch (error) {
    readError = error.code ?? "read_failed";
  }
  return { exists: true, size: stat.size, mtimeMs: stat.mtimeMs, ownerPid, readError };
}

async function launchSecondaryInstanceProbe(tempRoot, browserArgs, primaryPid) {
  const secondaryProfile = path.join(tempRoot, "profile", "duplicate-launcher");
  const secondaryRoaming = path.join(secondaryProfile, "Roaming");
  const secondaryLocal = path.join(secondaryProfile, "Local");
  await Promise.all([fs.mkdir(secondaryRoaming, { recursive: true }), fs.mkdir(secondaryLocal, { recursive: true })]);
  const lockfilePath = path.join(tempRoot, "temp", "otp_lol.lock");
  const primaryLockProof = await waitForJsonFile(path.join(tempRoot, "primary-single-instance.json"));
  assert.equal(primaryLockProof.lockAcquired, true);
  assert.equal(primaryLockProof.pid, primaryPid, "The first app process must have acquired the lock.");
  assert.equal(primaryLockProof.lockOwnerPid, primaryPid, "The lock contents must identify the first app PID as owner.");
  assert.equal(path.resolve(primaryLockProof.lockfilePath).toLowerCase(), path.resolve(lockfilePath).toLowerCase());
  const lockBefore = await lockFileSnapshot(lockfilePath);
  assert.equal(lockBefore.exists, true, "The primary isolated launcher must already hold its temp lock file.");
  if (lockBefore.ownerPid !== null) {
    assert.equal(lockBefore.ownerPid, primaryPid, "The lock file must still name the first app process before the duplicate launch.");
  }

  const launcher = path.join(repoRoot, "launcher_web.py");
  const pythonPath = [scriptDir, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  const guardEvidencePath = path.join(tempRoot, "secondary-guard.json");
  const child = spawn(python, [launcher], {
    cwd: repoRoot,
    env: {
      ...process.env,
      APPDATA: secondaryRoaming,
      LOCALAPPDATA: secondaryLocal,
      TEMP: path.join(tempRoot, "temp"),
      TMP: path.join(tempRoot, "temp"),
      PYTHONPATH: pythonPath,
      PYTHONDONTWRITEBYTECODE: "1",
      OTP_LOL_NATIVE_E2E_GUARD_EVIDENCE: guardEvidencePath,
      WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: browserArgs,
    },
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (chunk) => { stdout += chunk.toString("utf8"); });
  child.stderr.on("data", (chunk) => { stderr += chunk.toString("utf8"); });
  const exited = new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("close", (code, signal) => resolve({ code, signal }));
  });
  let timeoutId;
  let outcome = await Promise.race([
    exited,
    new Promise((resolve) => { timeoutId = setTimeout(() => resolve(null), 8_000); }),
  ]);
  clearTimeout(timeoutId);
  if (outcome === null) {
    const snapshot = await processTree(child.pid);
    if (snapshot.root?.pid === child.pid && snapshot.root.name.toLowerCase().startsWith("python")) {
      const taskkill = spawnSync("taskkill.exe", ["/PID", String(child.pid), "/T", "/F"], {
        encoding: "utf8",
        windowsHide: true,
        timeout: 15_000,
      });
      if (taskkill.error) throw taskkill.error;
      const expected = [snapshot.root, ...(snapshot.descendants ?? [])];
      const deadline = Date.now() + 10_000;
      let survivors = [];
      while (Date.now() < deadline) {
        const alive = pythonJson(["--pids-alive", expected.map(({ pid }) => pid).join(",")]);
        survivors = (alive.payload.alive ?? []).filter((process) => {
          const initial = expected.find((item) => item.pid === process.pid);
          return initial?.createTime === process.createTime;
        });
        if (!survivors.length) break;
        await new Promise((resolve) => setTimeout(resolve, 200));
      }
      if (survivors.length) throw new Error(`Duplicate launcher process tree survived cleanup: ${JSON.stringify(survivors)}`);
    }
    throw new Error("The secondary launcher did not return after the single-instance guard; its isolated process tree was stopped.");
  }

  const guardEvidence = JSON.parse(await fs.readFile(guardEvidencePath, "utf8"));
  assert.equal(guardEvidence.pid, child.pid);
  assert.equal(guardEvidence.processDiscoveryFiltered, true);
  assert.equal(guardEvidence.lcuConnectionGuarded, true, "The duplicate-launcher process must guard Connection.init before production startup.");
  assert.equal(guardEvidence.pythonNetworkGuarded, true);
  assert.equal(guardEvidence.shellActionsSuppressed, true);
  assert.equal(guardEvidence.loadedBeforeLauncher, true);

  const lockAfter = await lockFileSnapshot(lockfilePath);
  const log = `${stdout}\n${stderr}`;
  assert.equal(outcome.code, 0, `The secondary launcher should exit successfully after refusal: ${log.trim()}`);
  assert.match(log, /Another instance is already running\. Closing\./);
  assert.equal(lockAfter.exists, true, "The primary instance lock must remain present after the second launch attempt.");
  if (lockBefore.ownerPid !== null && lockAfter.ownerPid !== null) {
    assert.equal(lockAfter.ownerPid, primaryPid, "The second process must not replace the first app's lock owner.");
  } else {
    assert.equal(lockAfter.size, lockBefore.size, "The locked file must retain its size when the owner cannot be read during a lock.");
    assert.equal(lockAfter.mtimeMs, lockBefore.mtimeMs, "The locked file must not be rewritten when the owner cannot be read.");
  }
  return {
    command: "python launcher_web.py",
    pid: child.pid,
    exitCode: outcome.code,
    stderr: stderr.trim().split(/\r?\n/).slice(-4),
    isolatedSecondaryProfile: secondaryProfile,
    lockfilePath,
    primaryLockProof,
    lockBefore,
    lockAfter,
    safetyGuard: guardEvidence,
    duplicateUiLaunched: false,
  };
}

function allocateLoopbackPort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close((error) => error ? reject(error) : resolve(port));
    });
  });
}

async function startExternalDenyProxy() {
  const attempts = [];
  const server = http.createServer((request, response) => {
    let host = "unknown";
    try { host = new URL(request.url).hostname || host; } catch { /* malformed external request */ }
    attempts.push({ protocol: "http", host });
    response.writeHead(451, { "Connection": "close", "Content-Length": "0" }).end();
  });
  server.on("connect", (request, socket) => {
    attempts.push({ protocol: "connect", host: request.url.split(":", 1)[0] || "unknown" });
    socket.end("HTTP/1.1 451 Unavailable For Legal Reasons\r\nConnection: close\r\nContent-Length: 0\r\n\r\n");
  });
  server.on("upgrade", (request, socket) => {
    attempts.push({ protocol: "upgrade", host: request.headers.host || "unknown" });
    socket.end("HTTP/1.1 451 Unavailable For Legal Reasons\r\nConnection: close\r\nContent-Length: 0\r\n\r\n");
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  assert.equal(address.address, "127.0.0.1", "The external-deny proxy must bind loopback only.");
  return { server, port: address.port, attempts };
}

function getListeners(port) {
  const command = `@(Get-NetTCPConnection -State Listen -LocalPort ${port} -ErrorAction SilentlyContinue | Select-Object LocalAddress,OwningProcess) | ConvertTo-Json -Compress`;
  const output = execFileSync("powershell.exe", ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command], {
    encoding: "utf8",
    windowsHide: true,
    timeout: 10_000,
  }).trim();
  if (!output || output === "null") return [];
  const listeners = JSON.parse(output);
  return Array.isArray(listeners) ? listeners : [listeners];
}

function waitForAppEvent(child, eventName, timeoutMs = 20_000) {
  return new Promise((resolve, reject) => {
    const existing = appEvents.find((event) => event.event === eventName);
    if (existing) return resolve(existing);
    const timeout = setTimeout(() => reject(new Error(`App did not emit ${eventName}.`)), timeoutMs);
    const onData = (chunk) => {
      for (const line of chunk.toString("utf8").split(/\r?\n/)) {
        if (!line.startsWith("NATIVE_E2E ")) continue;
        const event = JSON.parse(line.slice("NATIVE_E2E ".length));
        if (event.event === eventName) {
          clearTimeout(timeout);
          child.stdout.off("data", onData);
          resolve(event);
        }
      }
    };
    child.stdout.on("data", onData);
    child.once("exit", (code) => {
      clearTimeout(timeout);
      child.stdout.off("data", onData);
      reject(new Error(`App exited before ${eventName} (exit ${code}).`));
    });
  });
}

async function waitForDevTools(port, child) {
  const endpoint = `http://127.0.0.1:${port}/json/version`;
  const deadline = Date.now() + 30_000;
  let lastError;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`App exited before WebView2 CDP became ready (exit ${child.exitCode}).`);
    try {
      const response = await fetch(endpoint, { signal: AbortSignal.timeout(1_000) });
      if (response.ok) return { endpoint, version: await response.json() };
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`WebView2 CDP did not become ready: ${String(lastError ?? "timeout")}`);
}

async function waitForLcuDiscoveryEvidence(stateDir, timeoutMs = 10_000) {
  const evidencePath = path.join(stateDir, "lcu-discovery.json");
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const evidence = JSON.parse(await fs.readFile(evidencePath, "utf8"));
      if (evidence.scanCalls > 0) return evidence;
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error("The test process did not prove that its LCU process scanner is active and filtered.");
}

async function waitForPage(browser, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const page = browser.contexts().flatMap((context) => context.pages()).find((candidate) => {
      try {
        const url = new URL(candidate.url());
        return url.protocol === "http:" && ["127.0.0.1", "localhost", "::1"].includes(url.hostname);
      } catch {
        return false;
      }
    });
    if (page) return page;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error("No loopback application page appeared in the WebView2 CDP session.");
}

function startJsonHelper(args) {
  const child = spawn(python, args, {
    cwd: repoRoot,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  activeHelpers.add(child);
  child.once("close", () => activeHelpers.delete(child));
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (chunk) => { stdout += chunk.toString("utf8"); });
  child.stderr.on("data", (chunk) => { stderr += chunk.toString("utf8"); });
  return { child, get stdout() { return stdout; }, get stderr() { return stderr; } };
}

async function helperResult(helper) {
  const [code] = helper.child.exitCode === null ? await once(helper.child, "close") : [helper.child.exitCode];
  const lines = helper.stdout.trim().split(/\r?\n/);
  let payload;
  try {
    payload = JSON.parse(lines.at(-1));
  } catch {
    throw new Error(`Native Win32 helper returned no JSON (exit ${code}): ${helper.stderr.trim() || helper.stdout.trim()}`);
  }
  if (code !== 0) throw new Error(`Native Win32 helper failed (exit ${code}): ${helper.stderr.trim() || helper.stdout.trim()}`);
  return payload;
}

async function waitForHelperReady(helper, timeoutMs = 3_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const line = helper.stdout.trim().split(/\r?\n/).at(-1);
    if (line) {
      try {
        if (JSON.parse(line).waitingFor === "native_file_dialog") return;
      } catch {
        // The helper has not emitted its readiness line yet.
      }
    }
    if (helper.child.exitCode !== null) throw new Error(`Native dialog helper exited early: ${helper.stderr.trim()}`);
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error("Native dialog helper did not enter its wait state.");
}

async function processTree(pid, expectedBrowserArg) {
  const args = ["--tree-pid", String(pid)];
  if (expectedBrowserArg) args.push(`--expected-browser-arg=${expectedBrowserArg}`);
  const { status, payload } = pythonJson(args);
  if (status !== 0) throw new Error(`Could not inspect test process tree: ${JSON.stringify(payload)}`);
  return payload;
}

function rememberProcessTree(snapshot) {
  if (snapshot.root) knownProcesses.set(snapshot.root.pid, snapshot.root);
  for (const process of snapshot.descendants ?? []) knownProcesses.set(process.pid, process);
  processSnapshot = [...knownProcesses.values()];
}

async function verifyStopped(expected) {
  const ids = expected.map((process) => process.pid).join(",");
  const { status, payload } = pythonJson(["--pids-alive", ids]);
  if (status !== 0) throw new Error("Could not verify test process cleanup.");
  const original = new Map(expected.map((process) => [process.pid, process.createTime]));
  return (payload.alive ?? []).filter((process) => original.get(process.pid) === process.createTime);
}

function removeOwnTempRoot(root) {
  const tempParent = fs.realpath(os.tmpdir());
  return Promise.all([tempParent, fs.realpath(root)]).then(([parent, resolved]) => {
    const prefix = parent.endsWith(path.sep) ? parent : `${parent}${path.sep}`;
    if (!resolved.toLowerCase().startsWith(prefix.toLowerCase()) || !path.basename(resolved).startsWith("otp-lol-native-e2e-")) {
      throw new Error("Refusing to remove a directory outside this run's unique temp root.");
    }
    return fs.rm(resolved, { recursive: true, force: true });
  });
}

const preflight = pythonJson(["--preflight"]);
if (preflight.status !== 0) {
  throw new Error(`Refusing to run because LeagueClientUx.exe is already present: ${JSON.stringify(preflight.payload.leagueProcesses)}`);
}

const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), "otp-lol-native-e2e-"));
const captureRunId = new Date().toISOString().replace(/[:.]/g, "-");
const captureDir = path.resolve(scriptDir, "../../../frontend/test-results/native-e2e", captureRunId);
const screenshots = [];
async function saveScreenshot(page, name) {
  await fs.mkdir(captureDir, { recursive: true });
  const screenshotPath = path.join(captureDir, `${name}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true, animations: "disabled" });
  screenshots.push(screenshotPath);
}
let app;
let browser;
let externalDenyProxy;
const knownProcesses = new Map();
const activeHelpers = new Set();
let processSnapshot = [];
let cleanupProof = { processTreeStopped: false, helpersStopped: true, profileRemoved: false };
let appEvents = [];
let appStdout = "";
let appStderr = "";
let lcuEvidence;
let browserIsolationEvidence;
let nativeWindowEvidence;
const completedActions = [];
const skippedActions = [];
const nativeActionEvidence = {};
let result;

try {
  const cdpPort = await allocateLoopbackPort();
  externalDenyProxy = await startExternalDenyProxy();
  const browserIsolationArg = `--proxy-server=http://127.0.0.1:${externalDenyProxy.port}`;
  const browserArgs = `${browserIsolationArg} --proxy-bypass-list=127.0.0.1;localhost;[::1]`;
  app = spawn(python, [nativeApp, "--run", "--state-dir", tempRoot, "--cdp-port", String(cdpPort)], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: "1",
      WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: browserArgs,
    },
    windowsHide: false,
    stdio: ["ignore", "pipe", "pipe"],
  });
  app.stdout.on("data", (chunk) => {
    const text = chunk.toString("utf8");
    appStdout = `${appStdout}${text}`.slice(-16_000);
    for (const line of text.split(/\r?\n/)) {
      if (line.startsWith("NATIVE_E2E ")) appEvents.push(JSON.parse(line.slice("NATIVE_E2E ".length)));
    }
  });
  app.stderr.on("data", (chunk) => { appStderr = `${appStderr}${chunk.toString("utf8")}`.slice(-12_000); });
  app.once("error", (error) => { appStderr += `${error.message}\n`; });

  assert.equal(path.basename(app.spawnfile).toLowerCase().startsWith("python"), true, "Only the isolated Python source launcher may be started.");
  assert.equal(app.spawnargs.some((argument) => /OTP LOL\.exe/i.test(argument)), false, "The existing packaged executable must not be launched.");
  const started = await waitForAppEvent(app, "app_starting");
  assert.equal(started.pid, app.pid);
  assert.equal(started.isolatedProfile, true);
  assert.equal(started.isolatedPaths, true);
  assert.equal(started.leagueProcessScan, "blocked-empty-in-test-process");
  assert.equal(started.productExecutableLaunched, false);
  rememberProcessTree(await processTree(app.pid));

  const cdp = await waitForDevTools(cdpPort, app);
  browserIsolationEvidence = await processTree(app.pid, browserIsolationArg);
  rememberProcessTree(browserIsolationEvidence);
  assert.equal(browserIsolationEvidence.browserIsolationArgumentFound, true, "WebView2 must inherit the external-deny proxy before page startup.");
  lcuEvidence = await waitForLcuDiscoveryEvidence(tempRoot);
  assert.equal(lcuEvidence.scanner, "lcu_driver.utils.process_iter");
  assert.equal(lcuEvidence.candidateCount, 0, "The LCU connector must not discover any process or target.");
  assert.deepEqual(lcuEvidence.attempts, [], "No HTTP or WSS connection target may be attempted.");
  const listeners = getListeners(cdpPort);
  assert.ok(listeners.length > 0, "The WebView2 remote debugging endpoint must have a listener.");
  assert.ok(listeners.every((listener) => ["127.0.0.1", "::1"].includes(listener.LocalAddress)), `CDP must bind loopback only, got ${JSON.stringify(listeners)}.`);
  const appPids = new Set([browserIsolationEvidence.root?.pid, ...(browserIsolationEvidence.descendants ?? []).map(({ pid }) => pid)]);
  assert.ok(listeners.every((listener) => appPids.has(listener.OwningProcess)), "The CDP listener must belong to the isolated app process tree.");
  const proxyListeners = getListeners(externalDenyProxy.port);
  assert.ok(proxyListeners.some((listener) => listener.LocalAddress === "127.0.0.1"), "The WebView2 external-deny proxy must remain available on loopback.");
  assert.ok(proxyListeners.every((listener) => listener.LocalAddress === "127.0.0.1" && listener.OwningProcess === process.pid), `External-deny proxy must be owned by the harness and bind loopback only, got ${JSON.stringify(proxyListeners)}.`);

  browser = await chromium.connectOverCDP(cdp.endpoint);
  const page = await waitForPage(browser);
  const browserRequestsOutsideLoopback = [];
  const browserSocketsOutsideLoopback = [];
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (["127.0.0.1", "localhost", "::1"].includes(url.hostname)) return route.continue();
    browserRequestsOutsideLoopback.push(url.hostname || url.protocol);
    return route.abort();
  });
  page.on("websocket", (socket) => {
    const url = new URL(socket.url());
    if (!["127.0.0.1", "localhost", "::1"].includes(url.hostname)) {
      browserSocketsOutsideLoopback.push(url.hostname);
      socket.close();
    }
  });
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  const bootstrapResponse = await page.request.get(new URL("/api/bootstrap", page.url()).toString());
  assert.equal(bootstrapResponse.status(), 200, "The actual WebView must reach the embedded FastAPI app.");
  const bootstrap = await bootstrapResponse.json();
  assert.equal(bootstrap.runtime.connected, false, "The native run must remain in the controlled disconnected state.");
  completedActions.push("Read the real FastAPI bootstrap and confirmed runtime.connected=false.");

  const mainWindow = startJsonHelper([nativeDialog, "--app-pid", String(app.pid), "--wait-main-window", "--timeout", "20"]);
  nativeWindowEvidence = await helperResult(mainWindow);
  assert.equal(nativeWindowEvidence.nativeWindow.title, "OTP LOL");
  await saveScreenshot(page, "initial");
  completedActions.push("Win32 enumerated a visible top-level OTP LOL HWND in the isolated app process tree.");

  nativeActionEvidence.singleInstance = await launchSecondaryInstanceProbe(tempRoot, browserArgs, app.pid);
  completedActions.push("Launched a second real launcher_web.py process with the same isolated TEMP lock and separate isolated APPDATA; it logged the production single-instance refusal, exited 0, and left the primary lock owner unchanged.");

  await page.getByRole("link", { name: "Réglages" }).click();
  completedActions.push("Clicked the visible Réglages navigation link.");
  await page.getByRole("button", { name: "Avancé" }).click();
  completedActions.push("Clicked the visible Avancé tab.");
  await page.getByRole("heading", { name: "Fichiers et diagnostics" }).waitFor({ state: "visible" });
  await saveScreenshot(page, "settings-advanced");
  completedActions.push("Verified the Fichiers et diagnostics settings section is visible.");

  const dialogHelper = startJsonHelper([nativeDialog, "--app-pid", String(app.pid), "--wait-and-cancel", "--timeout", "20"]);
  await waitForHelperReady(dialogHelper);
  const importButton = page.locator("button.advanced-action").filter({ hasText: "Importer une configuration" });
  assert.equal(await importButton.count(), 1, "The visible import action must be unique.");
  await importButton.click();
  completedActions.push("Clicked the visible Importer une configuration button.");
  const dialogEvidence = await helperResult(dialogHelper);
  assert.equal(dialogEvidence.win32CancelClicked, true);
  assert.ok(["BM_CLICK", "IDCANCEL"].includes(dialogEvidence.cancelMethod));
  assert.equal(dialogEvidence.dialogClosed, true);
  assert.equal(await page.locator("#settings-import").evaluate((input) => input.files?.length ?? 0), 0);
  await importButton.waitFor({ state: "visible" });
  completedActions.push("Win32 canceled the native file dialog and the hidden file input remained empty.");

  const trayFile = path.join(tempRoot, "tray-window.json");
  const trayStateFile = path.join(tempRoot, "tray-menu-states.json");
  const trayMenu = (action, timeout = 15_000) => win32Json([
    "--app-pid", String(app.pid),
    "--tray-menu", action,
    "--tray-file", trayFile,
    "--tray-state-file", trayStateFile,
  ], timeout);
  const trayRecord = await waitForJsonFile(trayFile);
  assert.equal(trayRecord.pid, app.pid, "The tray HWND must belong to the exact isolated source-app PID.");
  assert.deepEqual(trayRecord.menuLabels, ["Show/Hide", "Settings", "Enable presets automations", "Enable auto-ban", "Quit"]);
  const trayHidden = trayMenu("toggle");
  assert.equal(trayHidden.action, "Show/Hide");
  assert.equal(trayHidden.visibleBefore, true);
  assert.equal(trayHidden.visibleAfter, false);
  const trayShown = trayMenu("toggle");
  assert.equal(trayShown.visibleBefore, false);
  assert.equal(trayShown.visibleAfter, true);
  nativeActionEvidence.tray = { trayRecord, hide: trayHidden, show: trayShown };
  completedActions.push("Win32 posted the real pystray WM_NOTIFY/WM_RBUTTONUP message, selected Show/Hide in its native popup menu, and verified HWND hide then show.");

  const settingsMenu = trayMenu("settings");
  assert.equal(settingsMenu.action, "Settings");
  await page.waitForFunction(() => window.location.hash === "#settings/general", null, { timeout: 8_000 });
  await saveScreenshot(page, "settings-from-tray");
  nativeActionEvidence.tray.settings = settingsMenu;
  completedActions.push("Selected Settings from the native pystray menu and verified that the WebView navigated to #settings/general.");

  await page.getByRole("link", { name: "Dashboard" }).click();
  const presetsMaster = page.getByRole("switch", { name: "Utiliser les presets en sélection" });
  await presetsMaster.waitFor({ state: "visible" });
  if (await presetsMaster.getAttribute("aria-checked") === "true") {
    await presetsMaster.click();
    await waitForSetting(page, "presets_enabled", false);
  }
  await presetsMaster.click();
  let traySettings = await waitForSetting(page, "presets_enabled", true);
  const autoBanSwitch = page.getByRole("switch", { name: "Auto-Ban" });
  if (await autoBanSwitch.getAttribute("aria-checked") === "true") {
    await autoBanSwitch.click();
    traySettings = await waitForSetting(page, "auto_ban_enabled", false);
  }
  assert.equal(traySettings.presets_enabled, true);
  assert.equal(traySettings.auto_ban_enabled, false);
  nativeActionEvidence.tray.settingsPreparation = {
    via: "visible Dashboard automation switches",
    settingsAfter: traySettings,
  };
  const trayAfterUiSettings = trayMenu("inspect");
  nativeActionEvidence.tray.afterUiSettings = trayAfterUiSettings;
  assert.equal(
    trayAfterUiSettings.menuState.items[3].enabled,
    true,
    "The native auto-ban item must become enabled after presets are enabled through the UI."
  );
  completedActions.push("Enabled preset automations through the visible Dashboard control and verified the native Auto-ban item state.");

  const autoBanEnabled = trayMenu("auto-ban");
  assert.equal(autoBanEnabled.action, "auto-ban");
  assert.equal(autoBanEnabled.menuState.items[3].enabled, true);
  assert.equal(autoBanEnabled.menuState.items[3].checked, false);
  traySettings = await waitForSetting(page, "auto_ban_enabled", true);
  nativeActionEvidence.tray.autoBanEnable = { menu: autoBanEnabled, settingsAfter: traySettings };

  const presetsDisabled = trayMenu("presets");
  assert.equal(presetsDisabled.action, "presets");
  assert.equal(presetsDisabled.menuState.items[2].checked, true);
  assert.equal(presetsDisabled.menuState.items[3].enabled, true);
  traySettings = await waitForSetting(page, "presets_enabled", false);
  assert.equal(traySettings.auto_ban_enabled, true, "Disabling the master must preserve the auto-ban setting.");

  const disabledMenu = trayMenu("inspect");
  assert.equal(disabledMenu.menuState.items[2].checked, false);
  assert.equal(disabledMenu.menuState.items[3].enabled, false, "The native auto-ban menu item must be disabled with its master off.");
  assert.equal(disabledMenu.menuState.items[3].checked, true);

  const presetsReenabled = trayMenu("presets");
  assert.equal(presetsReenabled.menuState.items[2].checked, false);
  assert.equal(presetsReenabled.menuState.items[3].enabled, false);
  traySettings = await waitForSetting(page, "presets_enabled", true);
  nativeActionEvidence.tray.presets = {
    disable: presetsDisabled,
    disabledMenu: disabledMenu.menuState,
    reenable: presetsReenabled,
    settingsAfter: traySettings,
  };

  const autoBanDisabled = trayMenu("auto-ban");
  assert.equal(autoBanDisabled.menuState.items[3].enabled, true);
  assert.equal(autoBanDisabled.menuState.items[3].checked, true);
  traySettings = await waitForSetting(page, "auto_ban_enabled", false);
  nativeActionEvidence.tray.autoBanDisable = { menu: autoBanDisabled, settingsAfter: traySettings };
  completedActions.push("Toggled master preset automations and auto-ban through the real tray menu, verified persisted API state, native checked states, and auto-ban disabling when the master is off.");

  await page.getByRole("button", { name: "Avancé" }).click();
  await page.getByRole("heading", { name: "Fichiers et diagnostics" }).waitFor({ state: "visible" });

  const windowBeforeFullscreen = win32Json(["--app-pid", String(app.pid), "--window-snapshot"]);
  const fullscreenButton = page.locator("button.advanced-action").filter({ hasText: "Basculer en plein écran" });
  assert.equal(await fullscreenButton.count(), 1, "The visible native fullscreen action must be unique.");
  await fullscreenButton.click();
  const fullscreenOn = await waitForNativeWindow(
    app.pid,
    (snapshot) => snapshot.rect.left === snapshot.monitorBounds.left
      && snapshot.rect.top === snapshot.monitorBounds.top
      && snapshot.rect.right === snapshot.monitorBounds.right
      && snapshot.rect.bottom === snapshot.monitorBounds.bottom,
  );
  await saveScreenshot(page, "fullscreen");
  await fullscreenButton.click();
  const fullscreenOff = await waitForNativeWindow(
    app.pid,
    (snapshot) => JSON.stringify(snapshot.rect) === JSON.stringify(windowBeforeFullscreen.rect),
  );
  nativeActionEvidence.fullscreen = {
    before: windowBeforeFullscreen,
    fullscreen: fullscreenOn,
    restored: fullscreenOff,
  };
  completedActions.push("Clicked the visible fullscreen control twice and verified native monitor bounds followed by exact restoration of the original HWND rectangle.");

  const syntheticSettingsResponse = await page.request.patch(new URL("/api/settings", page.url()).toString(), {
    headers: { Origin: new URL(page.url()).origin },
    data: {
      summoner_name_auto_detect: false,
      manual_summoner_name: "Native E2E#TEST",
      manual_region: "na",
    },
  });
  assert.equal(syntheticSettingsResponse.status(), 200, "The synthetic account may be stored only in the temporary profile.");
  const [statsLinkResponse, liveLinkResponse] = await Promise.all([
    page.request.get(new URL("/api/links/stats", page.url()).toString()),
    page.request.get(new URL("/api/links/live", page.url()).toString()),
  ]);
  assert.equal(statsLinkResponse.status(), 200);
  assert.equal(liveLinkResponse.status(), 200);
  const [statsLink, liveLink] = await Promise.all([statsLinkResponse.json(), liveLinkResponse.json()]);
  for (const link of [statsLink, liveLink]) {
    assert.equal(link.available, true);
    assert.equal(link.riot_id, "Native E2E#TEST");
    assert.equal(link.region, "na");
    assert.equal(link.account_source, "manual");
    const target = new URL(link.url);
    assert.equal(target.protocol, "https:");
    assert.equal(target.origin, new URL(link.homepage_url).origin);
  }
  nativeActionEvidence.providerLinks = { stats: statsLink, live: liveLink, accountIsSynthetic: true };
  completedActions.push("Saved a synthetic Riot ID only in the isolated profile and verified real stats/live link endpoints return HTTPS URLs on each configured provider origin.");

  const diagnosticsResponse = await page.request.get(new URL("/api/diagnostics", page.url()).toString());
  assert.equal(diagnosticsResponse.status(), 200);
  const diagnostics = await diagnosticsResponse.json();
  nativeActionEvidence.hotkeys = diagnostics.hotkeys;
  for (const [slot, expectedHotkey] of [["window", "alt+c"], ["site", "alt+p"]]) {
    assert.equal(diagnostics.hotkeys[slot].hotkey, expectedHotkey);
    if (!diagnostics.hotkeys[slot].active) {
      skippedActions.push(`${expectedHotkey} input not sent because the app did not report an active backend (${diagnostics.hotkeys[slot].backend}).`);
    }
  }

  if (diagnostics.hotkeys.window.active) {
    await page.bringToFront();
    const hotkeyC = win32Json(["--app-pid", String(app.pid), "--send-hotkey", "--key", "c"]);
    assert.equal(hotkeyC.injected, true);
    const hiddenByHotkey = await waitForNativeWindow(app.pid, (snapshot) => !snapshot.nativeWindow.visible);
    assert.equal(hiddenByHotkey.nativeWindow.visible, false);
    const shownAfterHotkey = trayMenu("toggle");
    assert.equal(shownAfterHotkey.visibleAfter, true);
    nativeActionEvidence.hotkeys.window = { registration: diagnostics.hotkeys.window, input: hotkeyC, hidden: hiddenByHotkey, restoredByTray: shownAfterHotkey };
    completedActions.push("Verified Alt+C was reported actively registered, injected the real chord while the isolated OTP window was foreground, observed HWND hide, then restored it through the native tray menu.");
  }

  if (diagnostics.hotkeys.site.active) {
    await page.bringToFront();
    const hotkeyP = win32Json(["--app-pid", String(app.pid), "--send-hotkey", "--key", "p"]);
    assert.equal(hotkeyP.injected, true);
    await page.waitForFunction(() => window.location.hash === "#live", null, { timeout: 8_000 });
    await page.getByRole("heading", { name: "En direct" }).waitFor({ state: "visible" });
    await saveScreenshot(page, "live");
    nativeActionEvidence.hotkeys.site = { registration: diagnostics.hotkeys.site, input: hotkeyP, route: page.url() };
    completedActions.push("Verified Alt+P was reported actively registered, injected the real chord with the app foreground, and observed the real WebView navigate to En direct.");
  } else {
    await page.getByRole("link", { name: "En direct" }).click();
    await page.getByRole("heading", { name: "En direct" }).waitFor({ state: "visible" });
    await saveScreenshot(page, "live");
    skippedActions.push("Alt+P was not fired; navigated to En direct by visible navigation only so provider behavior remained inspectable.");
  }

  await page.getByRole("button", { name: "Ouvrir dans le navigateur" }).click();
  const capturedShellActions = await waitForJsonFile(path.join(tempRoot, "native-shell-actions.json"));
  const externalShellAction = capturedShellActions.find((action) => action.kind === "external_url");
  assert.ok(externalShellAction, "The provider external-link action must reach the desktop bridge.");
  assert.equal(externalShellAction.url, liveLink.url);
  assert.equal(externalShellAction.launchSuppressed, true, "The system browser must not launch outside the controlled WebView2 egress proxy.");
  nativeActionEvidence.externalShell = externalShellAction;
  completedActions.push("Clicked the visible provider external-link button and captured the validated URL at the real pywebview bridge; the test-only shell interceptor suppressed launch to keep egress contained.");

  const openInAppButton = page.getByRole("button", { name: "Ouvrir dans OTP LOL" });
  if (await openInAppButton.count()) {
    const providerOpenResponse = page.waitForResponse((response) => response.url().includes("/api/desktop/providers/live/open"));
    await openInAppButton.click();
    const providerOpen = await (await providerOpenResponse).json();
    assert.equal(providerOpen.ok, false);
    assert.equal(providerOpen.reason, "network_unavailable");
    nativeActionEvidence.providerWindow = providerOpen;
    completedActions.push("Clicked the in-app provider action with external network hard-blocked; FastAPI returned the expected network_unavailable response without creating an external browser process.");
  } else {
    skippedActions.push("The live-provider in-app button was not rendered, so the offline open path was not clickable in this state.");
  }

  await page.getByRole("link", { name: "Réglages" }).click();
  await page.getByRole("button", { name: "Avancé" }).click();
  const appDataButton = page.locator("button.advanced-action").filter({ hasText: "Dossier AppData" });
  assert.equal(await appDataButton.count(), 1);
  await appDataButton.click();
  const folderOpenActions = await waitForJsonFile(path.join(tempRoot, "native-shell-actions.json"));
  const folderOpenAction = folderOpenActions.find((action) => action.kind === "open_folder");
  assert.ok(folderOpenAction, "The app-data action must reach the native bridge.");
  assert.equal(folderOpenAction.path.toLowerCase(), path.join(tempRoot, "profile", "Roaming", "OTP LOL").toLowerCase());
  assert.equal(folderOpenAction.launchSuppressed, true);
  nativeActionEvidence.localShell = folderOpenAction;
  completedActions.push("Clicked Dossier AppData and captured only this run's isolated APPDATA target; Explorer launch was suppressed by the test-only shell interceptor.");

  const diagnosticsAction = page.locator("button.advanced-action").filter({ hasText: "Diagnostics LCU" });
  assert.equal(await diagnosticsAction.count(), 1);
  await diagnosticsAction.click();
  await page.getByRole("heading", { name: "Diagnostics LCU" }).waitFor({ state: "visible" });
  await saveScreenshot(page, "diagnostics");
  const saveDialogHelper = startJsonHelper([nativeDialog, "--app-pid", String(app.pid), "--wait-and-cancel", "--timeout", "20"]);
  await waitForHelperReady(saveDialogHelper);
  await page.getByRole("button", { name: "Exporter le rapport" }).click();
  const saveDialogEvidence = await helperResult(saveDialogHelper);
  assert.equal(saveDialogEvidence.win32CancelClicked, true);
  assert.equal(saveDialogEvidence.dialogClosed, true);
  await page.getByRole("status").filter({ hasText: "Export annulé." }).waitFor({ state: "visible" });
  nativeActionEvidence.diagnosticsSaveDialog = saveDialogEvidence;
  completedActions.push("Opened the diagnostics native Save dialog through the visible export action, canceled it through Win32, and verified the UI reports Export annulé.");

  const quitTray = trayMenu("quit", 20_000);
  assert.equal(quitTray.action, "Quit");
  assert.equal(quitTray.processExited, true);
  nativeActionEvidence.tray.quit = quitTray;
  completedActions.push("Selected Quit from the actual pystray native popup menu and verified the isolated source-app PID exited.");

  assert.deepEqual(browserRequestsOutsideLoopback, [], "The native UI must not send browser requests off loopback.");
  assert.deepEqual(browserSocketsOutsideLoopback, [], "The native UI must not open WebSockets off loopback.");
  assert.deepEqual(pageErrors, [], "The desktop page must not raise uncaught JavaScript errors during the flow.");
  assert.deepEqual(skippedActions, [], "Required native actions were skipped and are not covered.");

  result = {
    status: "passed",
    app: "real launcher_web.py source process with pywebview/WebView2",
    browser: cdp.version.Browser,
      cdpBinding: listeners,
    nativeWindow: { title: nativeWindowEvidence.nativeWindow.title, className: nativeWindowEvidence.nativeWindow.className },
    actions: completedActions,
    skippedActions,
    nativeActionEvidence,
    isolation: {
      isolatedProfile: true,
      profileEnvironment: ["APPDATA", "LOCALAPPDATA", "TEMP", "TMP"],
      storagePathsVerifiedUnderProfile: true,
      leagueClientPreflight: "no LeagueClientUx.exe found",
      lcuProcessDiscovery: "test-process scanner is forced empty, including if League starts during the run",
      externalPythonNetwork: "Python DNS and non-loopback sockets are blocked in-process before application imports",
      browserEgress: "WebView2 receives a pre-start loopback-only deny proxy; requests to external hosts receive 451 without proxy forwarding",
      browserIsolationArgumentFound: browserIsolationEvidence.browserIsolationArgumentFound,
      browserIsolationProcessIds: browserIsolationEvidence.browserIsolationProcesses.map(({ pid, name }) => ({ pid, name })),
      externalBrowserAttempts: externalDenyProxy.attempts,
      productExeLaunched: false,
    },
    lcuEvidence: {
      scanner: lcuEvidence.scanner,
      scanCalls: lcuEvidence.scanCalls,
      candidateCount: lcuEvidence.candidateCount,
      connectionAttempts: lcuEvidence.attempts,
    },
    errors: { page: pageErrors, browserEgress: browserRequestsOutsideLoopback, browserSockets: browserSocketsOutsideLoopback },
  };
} catch (error) {
  result = { status: "failed", error: error instanceof Error ? error.message : String(error), completedActions, skippedActions, nativeActionEvidence };
} finally {
  if (browser) {
    try { await browser.close(); } catch { /* disconnect cleanup continues below */ }
  }
  for (const helper of [...activeHelpers]) {
    if (helper.exitCode !== null) continue;
    const stopped = await new Promise((resolve) => {
      const timeout = setTimeout(() => resolve(false), 5_000);
      helper.once("exit", () => { clearTimeout(timeout); resolve(true); });
      if (helper.exitCode === null) helper.kill();
    });
    if (!stopped) {
      cleanupProof.helpersStopped = false;
      result = { status: "failed", error: `${result?.error ? `${result.error}; ` : ""}Win32 helper did not stop.` };
    }
  }
  if (app?.pid) {
    try {
      const snapshot = await processTree(app.pid);
      rememberProcessTree(snapshot);
      assert.equal(processSnapshot.some((process) => process.name.toLowerCase() === "otp lol.exe"), false, "The existing packaged app must never be in the launched tree.");
      if (snapshot.root) {
        assert.equal(snapshot.root.pid, app.pid, "The inspected process tree must match this exact Python child.");
        assert.equal(snapshot.root.name.toLowerCase().startsWith("python"), true, "Cleanup is limited to the test Python launcher tree.");
        const taskkill = spawnSync("taskkill.exe", ["/PID", String(app.pid), "/T", "/F"], { encoding: "utf8", windowsHide: true, timeout: 15_000 });
        if (taskkill.error) throw taskkill.error;
      }
      const deadline = Date.now() + 10_000;
      let survivors = [];
      while (Date.now() < deadline) {
        survivors = await verifyStopped(processSnapshot);
        if (!survivors.length) break;
        await new Promise((resolve) => setTimeout(resolve, 200));
      }
      cleanupProof.processTreeStopped = survivors.length === 0;
      if (!cleanupProof.processTreeStopped) throw new Error(`Test process tree did not stop: ${JSON.stringify(survivors)}`);
    } catch (cleanupError) {
      result = { status: "failed", error: `${result?.error ? `${result.error}; ` : ""}cleanup failed: ${cleanupError.message}` };
    }
  }
  if (externalDenyProxy?.server.listening) {
    await new Promise((resolve) => externalDenyProxy.server.close(resolve));
  }
  if (!lcuEvidence) {
    try { lcuEvidence = JSON.parse(await fs.readFile(path.join(tempRoot, "lcu-discovery.json"), "utf8")); } catch { /* evidence may not exist if startup was refused */ }
  }
  if (cleanupProof.processTreeStopped || !app) {
    try {
      await removeOwnTempRoot(tempRoot);
      cleanupProof.profileRemoved = true;
    } catch (cleanupError) {
      result = { status: "failed", error: `${result?.error ? `${result.error}; ` : ""}profile cleanup failed: ${cleanupError.message}` };
    }
  }
}

if (result?.status === "passed" && !cleanupProof.processTreeStopped) {
  result = { status: "failed", error: "The app process tree was not proven stopped." };
}
if (result?.status === "passed" && !cleanupProof.helpersStopped) {
  result = { status: "failed", error: "The Win32 helpers were not proven stopped." };
}
if (result?.status === "passed" && !cleanupProof.profileRemoved) {
  result = { status: "failed", error: "The unique isolated profile directory was not removed." };
}
console.log(JSON.stringify({
  ...result,
  screenshots,
  ...(lcuEvidence ? { lcuEvidence } : {}),
  ...(browserIsolationEvidence ? { browserIsolationEvidence: { argumentFound: browserIsolationEvidence.browserIsolationArgumentFound, processes: browserIsolationEvidence.browserIsolationProcesses } } : {}),
  ...(nativeWindowEvidence ? { nativeWindow: nativeWindowEvidence.nativeWindow } : {}),
  ...(externalDenyProxy ? { externalBrowserAttempts: externalDenyProxy.attempts } : {}),
  cleanup: cleanupProof,
  appEvents: appEvents.map(({ event, ...data }) => ({ event, ...data })),
  testProcessTree: processSnapshot.map(({ pid, name }) => ({ pid, name })),
  ...(cleanupProof.profileRemoved ? {} : { retainedProfile: tempRoot }),
}, null, 2));
if (result?.status !== "passed") {
  const tail = `${appStdout}\n${appStderr}`.trim().split(/\r?\n/).slice(-16).join("\n");
  if (tail) console.error(`Recent isolated app output:\n${tail}`);
  process.exitCode = 1;
}
