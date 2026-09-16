import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "../../app/AppShell";

describe("desktop shell", () => {
  it("marks the current page and keeps every navigation link in the shared sidebar", () => {
    render(<AppShell activePage="settings" />);

    expect(screen.getByRole("link", { name: "Réglages" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "#dashboard");
    expect(screen.getByRole("link", { name: "Presets" })).toHaveAttribute("href", "#presets");
    expect(screen.getByRole("link", { name: "Historique" })).toHaveAttribute("href", "#history");
  });
});
