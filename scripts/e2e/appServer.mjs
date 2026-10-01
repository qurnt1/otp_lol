import { spawn } from "node:child_process";
import { lstat, mkdir, mkdtemp, realpath, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createInterface } from "node:readline";
import { isDeepStrictEqual } from "node:util";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "../..");
const retainedStateDirs = new Set();
const stateDirPrefix = "otp-lol-e2e-";

function normalizeRealPath(value) {
  return value.replaceAll("\\", "/")
    .replace(/^\/\/\?\/UNC\//i, "//")
    .replace(/^\/\/\?\//, "")
    .replace(/\/+$/, "")
    .toLowerCase();
}

async function comparePaths(paths) {
  return Promise.all(paths.map(async ({ name, expected, reported }) => {
    let canonicalExpected = null;
    let canonicalReported = null;
    let expectedError = null;
    let reportedError = null;
    try {
      canonicalExpected = normalizeRealPath(await realpath(expected));
    } catch (error) {
      expectedError = error.message;
    }
    try {
      canonicalReported = normalizeRealPath(await realpath(reported));
    } catch (error) {
      reportedError = error.message;
    }
    return {
      name,
      expected,
      reported,
      canonicalExpected,
      canonicalReported,
      expectedError,
      reportedError,
      matches: canonicalExpected !== null && canonicalExpected === canonicalReported,
    };
  }));
}

export async function startOtpApp({
  python = process.env.PYTHON || "python",
  startupTimeoutMs = 60_000,
  stateDir: retainedStateDir,
  settingsToml,
  legacySettingsJson,
  legacySettingsFolder = "OTP LOL",
  legacyMainSettingsJson,
  legacySettingsBackupJson,
} = {}) {
  const stateDir = retainedStateDir
    ? path.resolve(retainedStateDir)
    : await mkdtemp(path.join(tmpdir(), stateDirPrefix));
  if (retainedStateDir) {
    const info = await lstat(stateDir).catch(() => null);
    if (
      !retainedStateDirs.has(stateDir)
      || !(await comparePaths([
        { name: "retainedStateParent", expected: tmpdir(), reported: path.dirname(stateDir) },
      ])).every(({ matches }) => matches)
      || !path.basename(stateDir).startsWith(stateDirPrefix)
      || !info?.isDirectory()
      || info.isSymbolicLink()
    ) {
      throw new Error("Only a stopped state directory retained by this E2E helper can be restarted.");
    }
    retainedStateDirs.delete(stateDir);
  }
  const appDataDir = path.join(stateDir, "profile", "Roaming");
  const localAppDataDir = path.join(stateDir, "profile", "Local");
  const tempDir = path.join(stateDir, "temp");
  if (settingsToml !== undefined) {
    const currentSettingsDir = path.join(appDataDir, "OTP LOL");
    await mkdir(currentSettingsDir, { recursive: true });
    await writeFile(path.join(currentSettingsDir, "parameters.toml"), settingsToml, { flag: "wx" });
  }
  if (legacySettingsJson !== undefined) {
    if (legacySettingsFolder !== "OTP LOL" && legacySettingsFolder !== "MainLoL") {
      throw new Error("Legacy settings fixtures must use the OTP LOL or MainLoL profile folder.");
    }
    const userSettingsDir = path.join(appDataDir, legacySettingsFolder);
    await mkdir(userSettingsDir, { recursive: true });
    await writeFile(path.join(userSettingsDir, "parameters.json"), legacySettingsJson, { flag: "wx" });
    if (legacySettingsBackupJson !== undefined) {
      await writeFile(path.join(userSettingsDir, "parameters.json.bak"), legacySettingsBackupJson, { flag: "wx" });
    }
  }
  if (legacyMainSettingsJson !== undefined) {
    const mainSettingsDir = path.join(appDataDir, "MainLoL");
    await mkdir(mainSettingsDir, { recursive: true });
    await writeFile(path.join(mainSettingsDir, "parameters.json"), legacyMainSettingsJson, { flag: "wx" });
  }
  const frontendDir = path.join(repoRoot, "frontend", "dist");
  const appServerPath = path.join(scriptDir, "app_server.py");
  const childEnv = { ...process.env };
  childEnv.APPDATA = appDataDir;
  childEnv.LOCALAPPDATA = localAppDataDir;
  childEnv.TEMP = tempDir;
  childEnv.TMP = tempDir;
  childEnv.PYTHONPATH = [repoRoot, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  childEnv.PYTHONDONTWRITEBYTECODE = "1";
  for (const name of ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]) {
    delete childEnv[name];
  }
  delete childEnv.OTP_LOL_LOG_LEVEL;
  delete childEnv.PYWEBVIEW_LOG;
  delete childEnv.OTP_LOL_ALLOW_DEV_ORIGINS;

  const child = spawn(
    python,
    [appServerPath, "--state-dir", stateDir, "--frontend-dir", frontendDir],
    { cwd: repoRoot, env: childEnv, stdio: ["pipe", "pipe", "pipe"], detached: process.platform !== "win32" },
  );

  const messages = [];
  const lcuRequests = [];
  const cleanupWarnings = [];
  const commandWaiters = new Map();
  const requestWaiters = new Set();
  let stderr = "";
  let exited = false;
  let exitCode = null;
  let exitSignal = null;
  let spawnError = null;

  const output = createInterface({ input: child.stdout });
  output.on("line", (line) => {
    let message;
    try {
      message = JSON.parse(line);
    } catch {
      messages.push({ type: "protocol-error", line });
      return;
    }
    messages.push(message);
    if (message.type === "lcu-request") {
      lcuRequests.push(message);
      for (const waiter of requestWaiters) {
        if (waiter.matches(message)) {
          requestWaiters.delete(waiter);
          clearTimeout(waiter.timer);
          waiter.resolve(message);
        }
      }
    }
    if (message.type === "cleanup-warning") cleanupWarnings.push(message);
    if (message.id && commandWaiters.has(message.id)) {
      const waiter = commandWaiters.get(message.id);
      commandWaiters.delete(message.id);
      clearTimeout(waiter.timer);
      if (message.type === "command-error") waiter.reject(new Error(message.error));
      else waiter.resolve(message);
    }
  });
  child.stderr.on("data", (chunk) => {
    stderr = (stderr + chunk.toString("utf8")).slice(-12_000);
  });
  const exitPromise = new Promise((resolve) => {
    child.once("exit", (code, signal) => {
      exited = true;
      exitCode = code;
      exitSignal = signal;
      resolve({ code, signal });
    });
    child.once("error", (error) => {
      spawnError = error;
      exited = true;
      resolve({ code: null, signal: null, error });
    });
  });
  const closePromise = new Promise((resolve) => {
    child.once("close", (code, signal) => resolve({ code, signal }));
  });

  function waitBounded(promise, timeoutMs, label) {
    let timer;
    return Promise.race([
      promise.then((value) => ({ completed: true, value })),
      new Promise((resolve) => {
        timer = setTimeout(() => resolve({ completed: false, label }), timeoutMs);
      }),
    ]).finally(() => clearTimeout(timer));
  }

  function getSyntheticPid() {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index];
      if (message.type === "synthetic-league-started") return message.pid;
      if (message.type === "synthetic-league-stopped") return null;
    }
    return null;
  }

  function getSyntheticPids() {
    return [...new Set(
      messages
        .filter((message) => message.type === "synthetic-league-started")
        .map((message) => message.pid),
    )];
  }

  function startupDiagnostics() {
    return JSON.stringify({
      exitCode,
      exitSignal,
      messages: messages.slice(-25),
      stderr,
    }, null, 2);
  }

  function isPidRunning(pid) {
    try {
      process.kill(pid, 0);
      return true;
    } catch (error) {
      if (error.code === "ESRCH") return false;
      if (error.code === "EPERM") return true;
      throw error;
    }
  }

  async function waitForPidExit(pid, timeoutMs) {
    if (!Number.isInteger(pid)) return true;
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (!isPidRunning(pid)) return true;
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    return !isPidRunning(pid);
  }

  async function stopChild() {
    if (exited) return { code: exitCode, signal: exitSignal, forced: false };
    try {
      child.stdin.write('{"command":"stop"}\n');
    } catch {
      // The process can exit between the state check and the write.
    }
    const graceful = await waitBounded(exitPromise, 30_000, "graceful stop");
    if (graceful.completed) return { ...graceful.value, forced: false };

    let forceError = null;
    if (process.platform === "win32" && child.pid) {
      try {
        const killer = spawn("taskkill.exe", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore", windowsHide: true });
        const killerExit = new Promise((resolve, reject) => {
          killer.once("error", reject);
          killer.once("exit", (code) => code === 0 ? resolve() : reject(new Error(`taskkill exited ${code}`)));
        });
        const killed = await waitBounded(killerExit, 5_000, "taskkill.exe");
        if (!killed.completed) {
          killer.kill();
          throw new Error("taskkill.exe timed out after 5 seconds.");
        }
      } catch (error) {
        forceError = error;
      }
    } else if (child.pid) {
      try {
        process.kill(-child.pid, "SIGKILL");
      } catch (error) {
        try {
          child.kill("SIGKILL");
        } catch {
          forceError = error;
        }
      }
    }
    const forcedExit = await waitBounded(closePromise, 5_000, "forced child close");
    return forcedExit.completed
      ? { ...forcedExit.value, forced: true, forceError }
      : { code: null, signal: "kill-timeout", forced: true, forceError };
  }

  async function confirmStoppedAndRemoveState({ retainState = false } = {}) {
    const closed = await waitBounded(closePromise, 5_000, "app process close");
    if (!closed.completed) {
      throw new Error(`E2E app process did not close; temporary state retained at ${stateDir}.`);
    }
    const syntheticPids = getSyntheticPids();
    for (const syntheticPid of syntheticPids) {
      if (!(await waitForPidExit(syntheticPid, 5_000))) {
        throw new Error(`Synthetic League PID ${syntheticPid} is still alive; temporary state retained at ${stateDir}.`);
      }
    }
    output.close();
    if (retainState) {
      retainedStateDirs.add(stateDir);
    } else {
      retainedStateDirs.delete(stateDir);
      await rm(stateDir, { recursive: true, force: true });
    }
    return { ...closed.value, syntheticPids, stateRetained: retainState };
  }

  const waitForMessage = (predicate, timeoutMs, description = "app server startup") => new Promise((resolve, reject) => {
    const existing = messages.find(predicate);
    if (existing) {
      resolve(existing);
      return;
    }
    let poll;
    const timer = setTimeout(() => {
      clearInterval(poll);
      reject(new Error(`Timed out waiting for ${description}.\n${startupDiagnostics()}`));
    }, timeoutMs);
    poll = setInterval(() => {
      if (spawnError) {
        clearInterval(poll);
        clearTimeout(timer);
        reject(new Error(`Could not start the E2E app process: ${spawnError.message}\n${startupDiagnostics()}`));
        return;
      }
      if (exited) {
        clearInterval(poll);
        clearTimeout(timer);
        reject(new Error(`E2E app process exited (${exitCode ?? exitSignal}).\n${startupDiagnostics()}`));
      } else {
        const match = messages.find(predicate);
        if (match) {
          clearInterval(poll);
          clearTimeout(timer);
          resolve(match);
        }
      }
    }, 25);
  });

  let ready;
  try {
    ready = await waitForMessage(
      (message) => message.type === "ready" || message.type === "startup-error",
      startupTimeoutMs,
    );
    if (ready.type === "startup-error") throw new Error(`${ready.error}\n${startupDiagnostics()}`);
    const pathComparisons = await comparePaths([
      { name: "stateDir", expected: stateDir, reported: ready.stateDir },
      { name: "appDataDir", expected: appDataDir, reported: ready.appDataDir },
      { name: "tempDir", expected: tempDir, reported: ready.tempDir },
    ]);
    if (pathComparisons.some(({ matches }) => !matches)) {
      throw new Error(
        `The E2E subprocess reported paths outside its isolated temporary profile: ${JSON.stringify(pathComparisons)}`,
      );
    }
  } catch (error) {
    let cleanup = "not attempted";
    try {
      const stopped = await stopChild();
      const closed = await confirmStoppedAndRemoveState();
      cleanup = JSON.stringify({ stopResult: stopped, closeResult: closed });
    } catch (cleanupError) {
      cleanup = `failed: ${cleanupError.message}; state retained at ${stateDir}`;
    }
    throw new Error(`${error.message}\nStartup diagnostics:\n${startupDiagnostics()}\nStartup cleanup: ${cleanup}`);
  }

  async function sendCommand(command, timeoutMs = 5_000) {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const response = new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        commandWaiters.delete(id);
        reject(new Error(`Timed out sending E2E app command '${command.command}'.`));
      }, timeoutMs);
      commandWaiters.set(id, { resolve, reject, timer });
    });
    child.stdin.write(`${JSON.stringify({ ...command, id })}\n`);
    return response;
  }

  return {
    baseURL: ready.url,
    stateDir,
    appDataDir: ready.appDataDir,
    localAppDataDir,
    tempDir: ready.tempDir,
    lcuURL: ready.lcuUrl,
    lcuDiscovery: ready.lcuDiscovery,
    processDiscovery: ready.processDiscovery,
    pathIsolation: ready.pathIsolation,
    networkBoundary: ready.networkBoundary,
    socketGuardProof: ready.socketGuardProof,
    get lcuRequests() {
      return [...lcuRequests];
    },
    get externalRequestsBlocked() {
      return messages.filter((message) => message.type === "network-request-blocked");
    },
    get externalFixtureRequests() {
      return messages.filter((message) => message.type === "network-request-fixture");
    },
    get socketEgressBlocked() {
      return messages.filter((message) => message.type === "socket-egress-blocked");
    },
    get socketConnections() {
      return messages.filter((message) => message.type === "socket-connect-allowed");
    },
    get websocketSubscription() {
      return messages.find((message) => message.type === "lcu-websocket-subscribed") ?? null;
    },
    get websocketSubscriptions() {
      return messages.filter((message) => message.type === "lcu-websocket-subscribed");
    },
    get syntheticLeaguePid() {
      return getSyntheticPid();
    },
    get syntheticLeaguePids() {
      return getSyntheticPids();
    },
    async emitLcuEvent(uri, data, timeoutMs = 5_000) {
      const firstNewMessageIndex = messages.length;
      await sendCommand({ command: "event", uri, data }, timeoutMs);
      return waitForMessage(
        (message) => message.type === "lcu-websocket-event"
          && message.topic === uri
          && isDeepStrictEqual(message.data, data)
          && messages.indexOf(message) >= firstNewMessageIndex,
        timeoutMs,
        `LCU WebSocket event ${uri}`,
      );
    },
    async waitForChampSelectRetryReady() {
      await sendCommand({ command: "wait-champ-select-retry-ready" }, 6_000);
    },
    async configureLcuState(state, timeoutMs = 5_000) {
      await sendCommand({ command: "state", state }, timeoutMs);
    },
    async readLcuState(timeoutMs = 5_000) {
      const response = await sendCommand({ command: "lcu-state" }, timeoutMs);
      return response.state;
    },
    async configureExternalState(state, timeoutMs = 5_000) {
      return sendCommand({ command: "external-state", state }, timeoutMs);
    },
    async configureLcuConnection({ online }, timeoutMs = 8_000) {
      return sendCommand({ command: "lcu-connection", online }, timeoutMs);
    },
    waitForWebSocketSubscription(number = 1, timeoutMs = 10_000) {
      if (!Number.isInteger(number) || number < 1) {
        throw new RangeError("WebSocket subscription number must be a positive integer.");
      }
      return waitForMessage(
        (message) => message.type === "lcu-websocket-subscribed"
          && messages.filter((item) => item.type === "lcu-websocket-subscribed").indexOf(message) === number - 1,
        timeoutMs,
        `LCU WebSocket subscription #${number}`,
      );
    },
    waitForExternalFixtureRequest(host, requestPath, status, timeoutMs = 8_000) {
      return waitForMessage(
        (message) => message.type === "network-request-fixture"
          && message.host === host
          && message.path === requestPath
          && message.status === status,
        timeoutMs,
        `external fixture GET ${host}${requestPath} (${status})`,
      );
    },
    waitForLcuRequest(method, requestPath, timeoutMs = 8_000) {
      const matches = (message) => message.method === method && message.path === requestPath;
      const existing = lcuRequests.find(matches);
      if (existing) return Promise.resolve(existing);
      return new Promise((resolve, reject) => {
        const waiter = {
          matches,
          resolve,
          timer: setTimeout(() => {
            requestWaiters.delete(waiter);
            reject(new Error(`Timed out waiting for fake LCU ${method} ${requestPath}.\n${stderr}`));
          }, timeoutMs),
        };
        requestWaiters.add(waiter);
      });
    },
    waitForLcuResponse(method, requestPath, status, timeoutMs = 8_000) {
      return waitForMessage(
        (message) => message.type === "lcu-response"
          && message.method === method
          && message.path === requestPath
          && message.status === status
          && message.complete === true,
        timeoutMs,
        `fake LCU ${method} ${requestPath} response (${status})`,
      );
    },
    async stop({ retainState = false } = {}) {
      const result = await stopChild();
      const stopped = await confirmStoppedAndRemoveState({ retainState });
      if (stopped.code !== 0 || cleanupWarnings.length || result.forceError) {
        if (retainState) {
          retainedStateDirs.delete(stateDir);
          await rm(stateDir, { recursive: true, force: true });
        }
        throw new Error(`E2E subprocess cleanup failed (exit=${stopped.code}). ${JSON.stringify(cleanupWarnings)} ${result.forceError ?? ""}\n${stderr}`);
      }
      return {
        ...result,
        ...stopped,
        cleanupWarnings: [...cleanupWarnings],
        syntheticLeagueStopped: stopped.syntheticPids.length === getSyntheticPids().length
          && getSyntheticPids().every((syntheticPid) => messages.some(
            (message) => message.type === "synthetic-league-stopped" && message.pid === syntheticPid,
          )),
        externalRequestsBlocked: messages.filter((message) => message.type === "network-request-blocked"),
        externalFixtureRequests: messages.filter((message) => message.type === "network-request-fixture"),
        socketEgressBlocked: messages.filter((message) => message.type === "socket-egress-blocked"),
        socketConnections: messages.filter((message) => message.type === "socket-connect-allowed"),
        stderr,
      };
    },
  };
}
