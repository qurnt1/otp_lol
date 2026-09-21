import { createRef } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import type { Champion, PresetPreview, PresetSlot, SummonerSpell } from "../../types/api";
import { PresetEditorDialog } from "./PresetEditorDialog";

const champion: Champion = {
  id: 86,
  name: "Garen",
  slug: "Garen",
  title: "La Force de Demacia",
  tags: ["Fighter"],
  icon_url: "/assets/garen.png",
  splash_url: "/assets/garen-splash.png",
};

const preview: PresetPreview = {
  champion_id: 86,
  champion_name: "Garen",
  champion_icon_url: "/assets/garen.png",
  champion_splash_url: "/assets/garen-splash.png",
  spell_1_url: null,
  spell_2_url: null,
  skin_name: "God-King Garen",
  skin_preview_url: "/assets/god-king.png",
};

const baseSlot: PresetSlot = {
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

const spells: SummonerSpell[] = [
  { name: "(None)", icon_url: null },
  { name: "Flash", icon_url: "/assets/flash.png" },
  { name: "Ignite", icon_url: "/assets/ignite.png" },
];

beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });
});

function editor(slot: PresetSlot, skinPreview: PresetPreview = preview) {
  return <PresetEditorDialog
    open
    slotKey="pick_1"
    slot={slot}
    priority={1}
    champion={champion}
    preview={skinPreview}
    spells={spells}
    pending={false}
    feedback=""
    leagueConnected={false}
    returnFocusRef={createRef<HTMLButtonElement>()}
    onClose={vi.fn()}
    onOpenPicker={vi.fn()}
    onUpdate={vi.fn()}
  >{null}</PresetEditorDialog>;
}

describe("PresetEditorDialog previews", () => {
  it("uses an explicit do-nothing rune choice without an automation toggle", () => {
    render(editor(baseSlot));

    expect(screen.getByText("Ne rien faire")).toBeVisible();
    expect(screen.queryByRole("switch", { name: "Appliquer automatiquement" })).not.toBeInTheDocument();
  });

  it("shows the matching bootstrap skin preview and falls back to the champion icon for none", () => {
    const { rerender } = render(editor(baseSlot));
    const skinChoice = screen.getByRole("button", { name: /Galerie des skins/ });
    expect(skinChoice.querySelector(".editor-skin-preview")).toHaveAttribute("src", preview.skin_preview_url);

    rerender(editor({ ...baseSlot, skin_mode: "none" }));

    const noneChoice = screen.getByRole("button", { name: /Galerie des skins/ });
    expect(noneChoice).toBeDisabled();
    expect(noneChoice.querySelector(".editor-skin-preview")).toHaveAttribute("src", champion.icon_url);
  });

  it("shows the bootstrap preview for the selected random pool", () => {
    const randomSlot: PresetSlot = {
      ...baseSlot,
      skin_mode: "random",
      random_skin_id: 86013,
      random_skin_name: "God-King Garen",
      random_skin_num: 13,
      random_skin_pool: [{ skin_id: 86013, skin_name: "God-King Garen", skin_num: 13 }],
    };
    render(editor(randomSlot));

    const skinChoice = screen.getByRole("button", { name: /Pool aléatoire/ });
    expect(skinChoice.querySelector(".editor-skin-preview")).toHaveAttribute("src", preview.skin_preview_url);
  });

  it("drops a stale skin image during an optimistic update and uses the refreshed preview", () => {
    const { rerender } = render(editor(baseSlot));
    const nextSlot = { ...baseSlot, skin_id: 86015, skin_name: "Steel Legion Garen", skin_num: 5 };
    rerender(editor(nextSlot));
    expect(screen.getByRole("button", { name: /Galerie des skins/ }).querySelector(".editor-skin-preview"))
      .toHaveAttribute("src", champion.icon_url);

    const nextPreview = { ...preview, skin_name: "Steel Legion Garen", skin_preview_url: "/assets/steel-legion.png" };
    rerender(editor(nextSlot, nextPreview));
    expect(screen.getByRole("button", { name: /Galerie des skins/ }).querySelector(".editor-skin-preview"))
      .toHaveAttribute("src", nextPreview.skin_preview_url);
  });

  it("renders spell icons in selected values and dropdown options", async () => {
    render(editor(baseSlot));

    const flashSelect = screen.getByRole("combobox", { name: "Sort 1" });
    expect(flashSelect.querySelector(".spell-select-icon")).toHaveAttribute("src", "/assets/flash.png");
    expect(screen.getByRole("combobox", { name: "Sort 2" }).querySelector(".spell-select-icon"))
      .toHaveAttribute("src", "/assets/ignite.png");

    fireEvent.keyDown(flashSelect, { key: "Enter" });
    const flashOption = await screen.findByRole("option", { name: "Flash" });
    const flashItemText = document.getElementById(flashOption.getAttribute("aria-labelledby") ?? "");
    expect(flashItemText).toContainElement(flashOption.querySelector(".spell-select-option"));
    expect(flashOption.querySelector(".spell-select-icon")).toHaveAttribute("src", "/assets/flash.png");
    expect(screen.getByRole("option", { name: "Ignite" }).querySelector(".spell-select-icon"))
      .toHaveAttribute("src", "/assets/ignite.png");
    expect(screen.getByRole("option", { name: "Aucun" }).querySelector(".spell-select-icon svg"))
      .toBeInTheDocument();
  });
});
