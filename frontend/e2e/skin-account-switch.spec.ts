import { expect, readSettings, setupApplication, test } from "./helpers";

test("skin ownership refreshes after the connected League account changes", async ({ page }) => {
  const { app } = await setupApplication(page, { configured: true });
  const firstAccount = {
    gameName: "Skin Owner A",
    gameTag: "AAAA",
    summonerId: 11111111,
    name: "Skin Owner A",
    puuid: "otp-lol-e2e-owner-a",
  };
  const secondAccount = {
    gameName: "Skin Owner B",
    gameTag: "BBBB",
    summonerId: 22222222,
    name: "Skin Owner B",
    puuid: "otp-lol-e2e-owner-b",
  };

  await app.configureLcuState({
    account_responses: { "/lol-chat/v1/me": { status: 200, payload: firstAccount } },
    inventory_skins: [{ id: 86001, ownershipType: "owned" }],
  });
  await app.emitLcuEvent("/lol-chat/v1/me", firstAccount);
  await expect.poll(async () => (await readSettings(page)).auto_detected_riot_id).toBe("Skin Owner A#AAAA");

  await page.goto("/#dashboard/pick_1");
  const editor = page.getByRole("dialog", { name: "Modifier la priorité 1" });
  await expect(editor).toBeVisible();
  const firstInventoryResponse = page.waitForResponse((response) =>
    response.request().method() === "GET"
      && new URL(response.url()).pathname === "/api/skins/86"
      && response.status() === 200,
  );
  await editor.getByRole("button", { name: /Galerie des skins/ }).click();

  const skinDialog = page.getByRole("dialog", { name: "Galerie des skins" });
  await expect(skinDialog.getByRole("checkbox", { name: "Possédés uniquement" })).toBeChecked();
  await expect(skinDialog.locator(".skin-option").filter({ hasText: "Commando Garen" })).toBeVisible();
  await expect(skinDialog.locator(".skin-option").filter({ hasText: "God-King Garen" })).toHaveCount(0);
  expect((await (await firstInventoryResponse).json()).owned.owned_skins.map((skin: { skin_id: number }) => skin.skin_id)).toEqual([86001]);
  await expect.poll(() => app.lcuRequests.some(({ method, path }) =>
    method === "GET" && path === "/lol-champions/v1/inventories/11111111/champions/86/skins"
  )).toBe(true);

  await page.keyboard.press("Escape");
  await expect(skinDialog).toHaveCount(0);
  await app.configureLcuState({
    account_responses: { "/lol-chat/v1/me": { status: 200, payload: secondAccount } },
    inventory_skins: [{ id: 86013, ownershipType: "owned" }],
  });
  await app.emitLcuEvent("/lol-chat/v1/me", secondAccount);
  await expect.poll(async () => (await readSettings(page)).auto_detected_riot_id).toBe("Skin Owner B#BBBB");

  const secondInventoryResponse = page.waitForResponse((response) =>
    response.request().method() === "GET"
      && new URL(response.url()).pathname === "/api/skins/86"
      && response.status() === 200,
  );
  await editor.getByRole("button", { name: /Galerie des skins/ }).click();
  await expect(skinDialog.getByRole("checkbox", { name: "Possédés uniquement" })).toBeChecked();
  await expect(skinDialog.locator(".skin-option").filter({ hasText: "God-King Garen" })).toBeVisible();
  await expect(skinDialog.locator(".skin-option").filter({ hasText: "Commando Garen" })).toHaveCount(0);
  expect((await (await secondInventoryResponse).json()).owned.owned_skins.map((skin: { skin_id: number }) => skin.skin_id)).toEqual([86013]);
  await expect.poll(() => app.lcuRequests.some(({ method, path }) =>
    method === "GET" && path === "/lol-champions/v1/inventories/22222222/champions/86/skins"
  )).toBe(true);
});
