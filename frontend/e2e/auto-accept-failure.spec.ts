import { readFile } from "node:fs/promises";
import path from "node:path";

import { expect, readHistory, readRuntime, readSettings, setupApplication, test, waitForRuntimeEvents } from "./helpers";

test("Auto-Accept ne présente pas le ready-check comme accepté après un refus LCU", async ({ page }) => {
  const { app } = await setupApplication(page, { connected: true, phase: "ReadyCheck" });
  const runtimeEvents = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await runtimeEvents;

  const autoAccept = page.getByRole("switch", { name: "Auto-Accept" });
  await expect(autoAccept).toHaveAttribute("aria-checked", "false");
  await autoAccept.click();
  await expect(autoAccept).toHaveAttribute("aria-checked", "true");
  await expect.poll(async () => (await readSettings(page)).auto_accept_enabled).toBe(true);

  const successStatus = page.getByText("Ready-check accepté.", { exact: true });
  await expect(successStatus).toHaveCount(0);
  await app.configureLcuState({
    mutation_responses: { "POST /lol-matchmaking/v1/ready-check/accept": [503] },
  });
  const requestOffset = app.lcuRequests.length;
  const acceptPath = "/lol-matchmaking/v1/ready-check/accept";
  const failedEvent = await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
  const acceptRequest = await app.waitForLcuRequest("POST", acceptPath);
  const rejectedResponse = await app.waitForLcuResponse("POST", acceptPath, 503);
  await app.waitForLcuEventCompletion(failedEvent.id);

  expect(app.lcuRequests.slice(requestOffset)).toContainEqual(expect.objectContaining({
    method: "POST",
    path: acceptPath,
    body: null,
  }));
  expect(acceptRequest.body).toBeNull();
  expect(rejectedResponse).toMatchObject({
    status: 503,
    body: { detail: "Synthetic LCU mutation rejected" },
    complete: true,
  });
  const appLogPath = path.join(app.appDataDir, "OTP LOL", "app_debug.log");
  await expect.poll(async () => {
    const appLog = await readFile(appLogPath, "utf8");
    return appLog.includes(`[READY] POST ${acceptPath} -> 503`);
  }).toBe(true);
  await expect(successStatus).toHaveCount(0);
  await expect.poll(async () => (await app.readLcuState()).ready_check.playerResponse).toBe("None");

  const history = await readHistory(page);
  expect(history.items.some((item) => item.message === "Match automatically accepted.")).toBe(false);

  await page.goto("/#history");
  await expect(page.getByRole("heading", { name: "Journal de logs" })).toBeVisible();
  await expect(page.getByText("Match automatically accepted.", { exact: true })).toHaveCount(0);

  await app.configureLcuState({ mutation_responses: {} });
  const retryEvent = await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
  await app.waitForLcuEventCompletion(retryEvent.id);

  const attempts = app.lcuRequests.slice(requestOffset).filter((request) =>
    request.method === "POST" && request.path === acceptPath,
  );
  expect(attempts).toHaveLength(2);
  await expect.poll(async () => (await app.readLcuState()).ready_check.playerResponse).toBe("Accepted");
  await expect.poll(async () => (await readHistory(page)).items.filter((item) =>
    item.message === "Match automatically accepted.",
  ).length).toBe(1);

  await expect(page.getByText("Match automatically accepted.", { exact: true })).toHaveCount(1);
});

test("[FE-LCU-AUTO-ACCEPT-OFF-01] désactiver Auto-Accept empêche toute acceptation du Ready Check", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    phase: "None",
    autoAccept: true,
    settings: { close_app_on_lol_exit: false },
  });
  const runtimeEvents = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await runtimeEvents;

  const autoAccept = page.getByRole("switch", { name: "Auto-Accept" });
  await expect(autoAccept).toHaveAttribute("aria-checked", "true");
  await autoAccept.click();
  await expect(autoAccept).toHaveAttribute("aria-checked", "false");
  await expect.poll(async () => (await readSettings(page)).auto_accept_enabled).toBe(false);

  const requestOffset = app.lcuRequests.length;
  const phaseEvent = await app.emitLcuEvent("/lol-gameflow/v1/gameflow-phase", "ReadyCheck");
  await app.waitForLcuEventCompletion(phaseEvent.id);
  await expect.poll(async () => (await readRuntime(page)).phase).toBe("ReadyCheck");

  const event = await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
  await app.waitForLcuEventCompletion(event.id);

  expect(app.lcuRequests.slice(requestOffset).filter((request) =>
    request.method === "POST" && request.path === "/lol-matchmaking/v1/ready-check/accept",
  )).toHaveLength(0);
  expect((await app.readLcuState()).ready_check.playerResponse).toBe("None");
  await expect(page.locator(".automation-status.is-success")).toHaveCount(0);
  await expect(page.getByText("Ready-check accepté.", { exact: true })).toHaveCount(0);
  expect((await readHistory(page)).items.some((item) => item.message === "Match automatically accepted.")).toBe(false);

  await page.goto("/#history");
  await expect(page.getByRole("heading", { name: "Journal de logs" })).toBeVisible();
  await expect(page.getByText("Match automatically accepted.", { exact: true })).toHaveCount(0);
});

test("un doublon Ready Check en vol autorise un seul retry après le refus initial", async ({ page }) => {
  const { app } = await setupApplication(page, {
    connected: true,
    phase: "ReadyCheck",
    autoAccept: true,
  });
  const runtimeEvents = waitForRuntimeEvents(page);
  await page.goto("/#dashboard");
  await runtimeEvents;

  const acceptPath = "/lol-matchmaking/v1/ready-check/accept";
  await app.configureLcuState({
    mutation_responses: { [`POST ${acceptPath}`]: [503, 200] },
    ready_check_accept_paused: true,
  });
  const requestOffset = app.lcuRequests.length;
  let firstEventId = "";
  try {
    const firstEvent = await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
    firstEventId = firstEvent.id;
    await app.waitForLcuRequest("POST", acceptPath);

    const duplicateEvent = await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
    await app.waitForLcuEventCompletion(duplicateEvent.id);
    expect(app.lcuRequests.slice(requestOffset).filter((request) =>
      request.method === "POST" && request.path === acceptPath,
    )).toHaveLength(1);
  } finally {
    await app.configureLcuState({ ready_check_accept_paused: false });
  }

  expect(firstEventId).not.toBe("");
  await app.waitForLcuEventCompletion(firstEventId);
  await expect(app.waitForLcuResponse("POST", acceptPath, 503)).resolves.toMatchObject({ status: 503 });
  await expect(app.waitForLcuResponse("POST", acceptPath, 200)).resolves.toMatchObject({ status: 200 });
  expect(app.lcuRequests.slice(requestOffset).filter((request) =>
    request.method === "POST" && request.path === acceptPath,
  )).toHaveLength(2);
  await expect.poll(async () => (await app.readLcuState()).ready_check.playerResponse).toBe("Accepted");
  await expect.poll(async () => (await readHistory(page)).items.filter((item) =>
    item.message === "Match automatically accepted.",
  ).length).toBe(1);
  await expect(page.getByText("Ready-check accepté.", { exact: true })).toBeVisible();
});
