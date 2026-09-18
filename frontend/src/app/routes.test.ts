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

  it("parses dashboard-triggered preset actions and their return target", () => {
    expect(parseHashRoute("#presets/ban?return=dashboard")).toEqual({ page: "presets", action: "ban", returnTo: "dashboard" });
    expect(parseHashRoute("#presets/pick_3")).toEqual({ page: "presets", action: "pick_3" });
    expect(parseHashRoute("#presets")).toEqual({ page: "presets" });
  });

  it("rejects unknown pages, sections, and trailing path segments", () => {
    expect(parseHashRoute("#unknown")).toBeNull();
    expect(parseHashRoute("#settings/missing")).toBeNull();
    expect(parseHashRoute("#statistics/links")).toBeNull();
    expect(parseHashRoute("#presets/unknown")).toBeNull();
    expect(parseHashRoute("#presets/pick_1?return=dashboard")).toBeNull();
    expect(parseHashRoute("#presets/ban?return=unknown")).toBeNull();
  });

  it("serializes settings sections and normal pages", () => {
    expect(routeToHash({ page: "settings", section: "shortcuts" })).toBe("#settings/shortcuts");
    expect(routeToHash({ page: "statistics" })).toBe("#statistics");
    expect(routeToHash({ page: "live" })).toBe("#live");
    expect(routeToHash({ page: "presets", action: "ban", returnTo: "dashboard" })).toBe("#presets/ban?return=dashboard");
    expect(routeToHash({ page: "presets", action: "pick_3" })).toBe("#presets/pick_3");
  });
});
