import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Champion, PresetPreview, PresetSlot } from "../../types/api";
import { ChampionPriorityCard } from "./ChampionPriorityCard";

const champion: Champion = {
  id: 86,
  name: "Garen",
  slug: "Garen",
  title: "La Force de Demacia",
  tags: ["Fighter"],
  icon_url: "/assets/garen.png",
  splash_url: "/assets/champion-splash.png",
};

const preview: PresetPreview = {
  champion_id: 86,
  champion_name: "Garen",
  champion_icon_url: "/assets/garen.png",
  champion_splash_url: "/assets/base-preview.png",
  spell_1_url: null,
  spell_2_url: null,
  skin_name: "God-King Garen",
  skin_preview_url: "/assets/selected-skin.png",
};

const slot: PresetSlot = {
  champion: "Garen",
  spell_1: "Flash",
  spell_2: "Ignite",
  skin_mode: "fixed",
  skin_id: 86013,
  skin_name: "God-King Garen",
  skin_num: 13,
  random_skin_id: 0,
  random_skin_name: "",
  random_skin_num: 0,
  random_skin_pool: [],
  rune_page_id: 0,
  rune_page_name: "",
  rune_keystone_id: 0,
  rune_keystone_path: "",
  rune_sub_style_icon_path: "",
};

describe("ChampionPriorityCard skin rendering", () => {
  it("uses the selected skin preview before the base splash", () => {
    const { container } = render(<ChampionPriorityCard slotKey="pick_1" slot={slot} index={0} spells={[]} preview={preview} champion={champion} />);

    expect(container.querySelector(".priority-art img")).toHaveAttribute("src", preview.skin_preview_url);
    expect(container.querySelector(".priority-card-link")).toHaveAttribute("href", "#presets/pick_1");
    expect(container.querySelector(".priority-mode-select")).toBeNull();
  });

  it("uses the champion splash when the effective mode is none", () => {
    const { container } = render(<ChampionPriorityCard slotKey="pick_1" slot={{ ...slot, skin_mode: "none" }} index={0} spells={[]} preview={preview} champion={champion} />);

    expect(container.querySelector(".priority-art img")).toHaveAttribute("src", preview.champion_splash_url);
  });

  it("falls back to the catalog champion splash when bootstrap has no base splash", () => {
    const { container } = render(<ChampionPriorityCard slotKey="pick_1" slot={{ ...slot, skin_mode: "none" }} index={0} spells={[]} preview={{ ...preview, champion_splash_url: null }} champion={champion} />);

    expect(container.querySelector(".priority-art img")).toHaveAttribute("src", champion.splash_url);
  });
});
