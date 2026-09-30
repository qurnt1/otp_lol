import { readFile } from "node:fs/promises";
import path from "node:path";

import { expect, readHistory, readSettings, setupApplication, test, waitForRuntimeEvents } from "./helpers";

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
  await app.emitLcuEvent("/lol-matchmaking/v1/ready-check", { state: "InProgress", playerResponse: "None" });
  const acceptRequest = await app.waitForLcuRequest("POST", acceptPath);
  const rejectedResponse = await app.waitForLcuResponse("POST", acceptPath, 503);

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
  // The app-side log confirms the awaited response; no callback-complete event exists, so this check uses a bounded observation window.
  await page.waitForTimeout(1_000);
  await expect(successStatus).toHaveCount(0);
  await expect.poll(async () => (await app.readLcuState()).ready_check.playerResponse).toBe("None");

  const history = await readHistory(page);
  expect(history.items.some((item) => item.message === "Match automatically accepted.")).toBe(false);

  await page.goto("/#history");
  await expect(page.getByRole("heading", { name: "Journal de logs" })).toBeVisible();
  await expect(page.getByText("Match automatically accepted.", { exact: true })).toHaveCount(0);
});
