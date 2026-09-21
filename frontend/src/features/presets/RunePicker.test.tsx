import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { RunesResponse } from "../../types/api";
import { RunePicker } from "./RunePicker";

const runes: RunesResponse = {
  available: true,
  pages: [{ id: 7, name: "Ma page Top", primaryStyleId: 8000, subStyleId: 8300, selectedPerkIds: [8005, 9111, 9104, 8014, 8304, 8316, 5008, 5001, 5003], current: true }],
  styles: {
    "8000": { name: "Précision", iconPath: "/styles/precision.png", icon_url: null, perks: [{ id: 8005, name: "Attaque mortelle", iconPath: "/perks/lethal.png", icon_url: null }] },
    "8300": { name: "Inspiration", iconPath: "/styles/inspiration.png", icon_url: null, perks: [] },
  },
};

const slot = {
  champion: "Garen", spell_1: "Flash", spell_2: "Ignite", skin_mode: "none" as const, skin_id: 0, skin_name: "", skin_num: 0,
  random_skin_id: 0, random_skin_name: "", random_skin_num: 0, random_skin_pool: [], rune_page_id: 0, rune_page_name: "",
  rune_keystone_id: 0, rune_keystone_path: "", rune_sub_style_icon_path: "",
};

describe("rune picker", () => {
  it("shows the do-nothing page and a numeric keystone asset", () => {
    const onUpdate = vi.fn();
    render(<RunePicker slot={slot} runes={runes} onUpdate={onUpdate} />);

    expect(screen.getByRole("button", { name: /Ne rien faire/ })).toBeVisible();
    expect(screen.getByRole("button", { name: /Ma page Top/ }).querySelector("img")).toHaveAttribute("src", "/api/assets/runes/perk/8005.png");

    fireEvent.click(screen.getByRole("button", { name: /Ma page Top/ }));
    expect(onUpdate).toHaveBeenCalledWith({
      rune_page_id: 7,
      rune_page_name: "Ma page Top",
      rune_keystone_id: 8005,
      rune_keystone_path: "/perks/lethal.png",
      rune_sub_style_icon_path: "/styles/inspiration.png",
    });

    fireEvent.click(screen.getByRole("button", { name: /Ne rien faire/ }));
    expect(onUpdate).toHaveBeenLastCalledWith({
      rune_page_id: 0,
      rune_page_name: "",
      rune_keystone_id: 0,
      rune_keystone_path: "",
      rune_sub_style_icon_path: "",
    });
  });

  it("keeps do-nothing available offline and warns about a missing saved page", () => {
    const onUpdate = vi.fn();
    render(<RunePicker slot={{ ...slot, rune_page_id: 999, rune_page_name: "Ancienne page" }} runes={{ available: false, pages: [], styles: {} }} onUpdate={onUpdate} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Page de runes supprimée ou indisponible");
    expect(screen.getByRole("button", { name: /Ne rien faire/ })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Ne rien faire/ }));
    expect(onUpdate).toHaveBeenCalledWith(expect.objectContaining({ rune_page_id: 0 }));
  });
});
