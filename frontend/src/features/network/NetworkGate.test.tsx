import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { fr } from "../../content/fr";
import { NetworkWarning } from "./NetworkGate";

describe("NetworkWarning", () => {
  it("shows a local image and keeps the application available while offline", () => {
    render(<NetworkWarning state="offline" onRetry={vi.fn()} />);

    expect(screen.getByRole("status")).toHaveTextContent(fr.network.warningTitle);
    expect(screen.getByRole("img")).toHaveAttribute("src", "/assets/app/garen.webp");
    expect(screen.getByRole("button", { name: fr.network.retry })).toBeVisible();
  });

  it("shows the checking state without exposing a retry action", () => {
    render(<NetworkWarning state="checking" />);

    expect(screen.getByRole("status")).toHaveTextContent(fr.network.checking);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
