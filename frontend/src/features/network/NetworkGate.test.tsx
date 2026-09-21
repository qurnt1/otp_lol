import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NetworkGate } from "./NetworkGate";

describe("NetworkGate", () => {
  it("shows a local image and blocks the app while offline", () => {
    render(<NetworkGate state="offline" onRetry={vi.fn()} />);

    expect(screen.getByRole("status")).toHaveTextContent("Connexion Internet requise");
    expect(screen.getByRole("img")).toHaveAttribute("src", "/assets/app/garen.webp");
    expect(screen.getByRole("button", { name: "Réessayer maintenant" })).toBeVisible();
  });

  it("shows the checking state without exposing a retry action", () => {
    render(<NetworkGate state="checking" />);

    expect(screen.getByRole("status")).toHaveTextContent("Vérification de la connexion Internet");
    expect(screen.queryByRole("button")).toBeNull();
  });
});
