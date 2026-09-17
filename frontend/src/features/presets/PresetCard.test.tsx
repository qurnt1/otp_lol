import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Champion, PresetSlot } from "../../types/api";
import { PresetCard } from "./PresetCard";

const champion: Champion = {
  id: 86,
  name: "Garen",
  slug: "Garen",
  tags: ["Fighter"],
  icon_url: "/api/assets/champions/86.png?v=16.18.1",
  splash_url: "/api/assets/champions/86/splash?v=16.18.1",
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
  rune_auto_apply: true,
  rune_keystone_path: "",
  rune_sub_style_icon_path: "",
};

describe("PresetCard", () => {
  it("carries the champion catalog version into a generated skin URL", () => {
    const { container } = render(
      <PresetCard
        slotKey="pick_1"
        slot={slot}
        index={0}
        champion={champion}
        spells={[]}
        isOpen={false}
        onOpen={vi.fn()}
      />,
    );

    expect(container.querySelector(".preset-card-art img")).toHaveAttribute(
      "src",
      "/api/assets/skins/86/86013/splash?skin_num=13&v=16.18.1",
    );
  });
});
