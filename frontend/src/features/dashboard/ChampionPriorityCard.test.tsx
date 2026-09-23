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
  it("keeps spells, runes, and skin in separate metadata rows", () => {
    const { container } = render(<ChampionPriorityCard slotKey="pick_1" slot={slot} index={0} spells={[]} preview={preview} champion={champion} />);

    expect(container.querySelectorAll(".summoner-row")).toHaveLength(1);
    expect(container.querySelectorAll(".rune-row")).toHaveLength(1);
    expect(container.querySelector(".rune-row .rune-name")).toHaveTextContent("Conserver ma page actuelle");
    expect(container.querySelectorAll(".skin-preview")).toHaveLength(1);
  });

  it("uses the selected skin preview before the base splash", () => {
    const { container } = render(<ChampionPriorityCard slotKey="pick_1" slot={slot} index={0} spells={[]} preview={preview} champion={champion} />);

    expect(container.querySelector(".priority-art img")).toHaveAttribute("src", preview.skin_preview_url);
    expect(container.querySelector(".skin-preview img")).toHaveAttribute("src", preview.champion_icon_url);
    expect(container.querySelector(".priority-card-link")).toHaveAttribute("href", "#dashboard/pick_1");
    expect(container.querySelector(".priority-mode-select")).toBeNull();
  });

  it("falls back to the catalog champion icon for the skin row", () => {
    const { container } = render(<ChampionPriorityCard slotKey="pick_1" slot={slot} index={0} spells={[]} preview={{ ...preview, champion_icon_url: null }} champion={champion} />);

    expect(container.querySelector(".skin-preview img")).toHaveAttribute("src", champion.icon_url);
  });

  it("treats an empty preview icon as missing", () => {
    const { container } = render(<ChampionPriorityCard slotKey="pick_1" slot={slot} index={0} spells={[]} preview={{ ...preview, champion_icon_url: "" }} champion={champion} />);

    expect(container.querySelector(".skin-preview img")).toHaveAttribute("src", champion.icon_url);
  });

  it("does not show a redundant ready subtitle when the champion catalog is unavailable", () => {
    const { container } = render(<ChampionPriorityCard slotKey="pick_1" slot={slot} index={0} spells={[]} preview={preview} />);

    expect(container.querySelector(".priority-caption small")).toBeNull();
    expect(container.querySelector(".priority-caption")).not.toHaveTextContent("Prêt");
  });

  it("keeps rune assets borderless through the dedicated asset class", () => {
    const { container } = render(<ChampionPriorityCard slotKey="pick_1" slot={slot} index={0} spells={[]} preview={preview} champion={champion} />);

    expect(container.querySelector(".rune-row .rune-asset")).not.toBeNull();
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
