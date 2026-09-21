import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "../../app/AppShell";

describe("desktop shell", () => {
  it("marks the current page and keeps every navigation link in the shared sidebar", () => {
    render(<AppShell activePage="settings" />);

    expect(screen.getByRole("link", { name: "Réglages" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "#dashboard");
    expect(screen.queryByRole("link", { name: "Presets" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Statistiques" })).toHaveAttribute("href", "#statistics");
    expect(screen.getByRole("link", { name: "En direct" })).toHaveAttribute("href", "#live");
    expect(screen.getByRole("link", { name: "Journal de logs" })).toHaveAttribute("href", "#history");
    expect(screen.getByRole("status", { name: "Client déconnecté" })).toBeInTheDocument();
    expect(screen.getByText("Aucun compte connecté")).toBeInTheDocument();
    expect(screen.getByText("Version")).toBeInTheDocument();
  });

  it("shows the connected account in the sidebar with a full-value tooltip", () => {
    render(<AppShell activePage="live" runtime={{
      version: "11.0", connected: true, phase: "InProgress", riot_id: "Player#EUW", region: "euw", queue_id: 420,
      assigned_position: "MID", presets_enabled: true, auto_accept_enabled: false, auto_pick_enabled: false,
      auto_ban_enabled: false, auto_summoners_enabled: false,
    }} />);

    expect(screen.getByRole("link", { name: "En direct" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("status", { name: "Client connecté" })).toBeInTheDocument();
    expect(screen.getByText("Player#EUW").parentElement).toHaveAttribute("title", "Player#EUW");
  });
});
