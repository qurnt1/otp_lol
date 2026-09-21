import { describe, expect, it } from "vitest";

import { parseHashRoute, routeToHash } from "./routes";

describe("hash routes", () => {
  it("parses statistics and settings subroutes", () => {
    expect(parseHashRoute("#statistics")).toEqual({ page: "statistics" });
    expect(parseHashRoute("#diagnostics")).toEqual({ page: "diagnostics" });
    expect(parseHashRoute("#live")).toEqual({ page: "live" });
    expect(parseHashRoute("#settings/links")).toEqual({ page: "settings", section: "links" });
    expect(parseHashRoute("#settings")).toEqual({ page: "settings", section: "general" });
  });

  it("parses dashboard-triggered preset actions", () => {
    expect(parseHashRoute("#dashboard")).toEqual({ page: "dashboard" });
    expect(parseHashRoute("#dashboard/ban")).toEqual({ page: "dashboard", action: "ban" });
    expect(parseHashRoute("#dashboard/pick_3")).toEqual({ page: "dashboard", action: "pick_3" });
  });

  it("rejects unknown pages, sections, and trailing path segments", () => {
    expect(parseHashRoute("#unknown")).toBeNull();
    expect(parseHashRoute("#settings/missing")).toBeNull();
    expect(parseHashRoute("#statistics/links")).toBeNull();
    expect(parseHashRoute("#dashboard/foo")).toBeNull();
    expect(parseHashRoute("#presets")).toBeNull();
    expect(parseHashRoute("#presets/pick_1")).toBeNull();
    expect(parseHashRoute("#dashboard/pick_1?return=dashboard")).toBeNull();
  });

  it("serializes settings sections and normal pages", () => {
    expect(routeToHash({ page: "settings", section: "shortcuts" })).toBe("#settings/shortcuts");
    expect(routeToHash({ page: "dashboard" })).toBe("#dashboard");
    expect(routeToHash({ page: "dashboard", action: "pick_1" })).toBe("#dashboard/pick_1");
    expect(routeToHash({ page: "dashboard", action: "ban" })).toBe("#dashboard/ban");
    expect(routeToHash({ page: "statistics" })).toBe("#statistics");
    expect(routeToHash({ page: "live" })).toBe("#live");
  });
});
