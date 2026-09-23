import { describe, expect, it } from "vitest";

import { filterChampions, updateSkinPool } from "./picker-utils";

const champions = [
  { id: 1, name: "Topper", slug: "Topper", tags: ["Fighter"], roles: ["TOP"], icon_url: null, splash_url: null },
  { id: 2, name: "Ahri", slug: "Ahri", tags: ["Mage"], roles: ["MIDDLE"], icon_url: null, splash_url: null },
];

describe("picker data", () => {
  it("filters by lane positions locally, not champion classes", () => {
    expect(filterChampions(champions, "", "top").map((champion) => champion.name)).toEqual(["Topper"]);
    expect(filterChampions(champions, "ah", "mid").map((champion) => champion.name)).toEqual(["Ahri"]);
  });

  it("keeps hidden random-pool entries when the owned filter changes", () => {
    const catalog = [
      { champion_id: 1, champion_name: "Topper", champion_slug: "Topper", skin_id: 1, skin_num: 1, skin_name: "Hidden", splash_url: "", tile_url: "", centered_splash_url: "", uncentered_splash_url: "" },
      { champion_id: 1, champion_name: "Topper", champion_slug: "Topper", skin_id: 2, skin_num: 2, skin_name: "Visible", splash_url: "", tile_url: "", centered_splash_url: "", uncentered_splash_url: "" },
    ];
    const pool = [{ skin_id: 1, skin_name: "Hidden", skin_num: 1 }];
    expect(updateSkinPool(pool, catalog, catalog[1], true)).toEqual([
      { skin_id: 1, skin_name: "Hidden", skin_num: 1 },
      { skin_id: 2, skin_name: "Visible", skin_num: 2 },
    ]);
  });
});
