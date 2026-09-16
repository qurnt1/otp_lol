import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "./client";

describe("desktop API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("requests runtime data through the local API boundary", async () => {
    const response = {
      connected: false,
      phase: "None",
      riot_id: null,
      region: "euw",
      queue_id: 0,
      assigned_position: "",
      presets_enabled: true,
      auto_accept_enabled: true,
      auto_pick_enabled: true,
      auto_ban_enabled: true,
      auto_summoners_enabled: true,
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getRuntime()).resolves.toEqual(response);
    expect(fetchMock).toHaveBeenCalledWith("/api/runtime", expect.objectContaining({ headers: expect.any(Headers) }));
    expect(fetchMock.mock.calls[0][1].headers.get("Content-Type")).toBeNull();
  });

  it("surfaces API errors instead of hiding failed mutations", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("invalid settings", { status: 422 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.patchSettings({ presets_enabled: false })).rejects.toMatchObject({
      message: "invalid settings",
      status: 422,
    } satisfies Partial<ApiError>);
  });
});
