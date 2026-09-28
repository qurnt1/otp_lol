import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BanPanel } from "./BanPanel";

describe("BanPanel", () => {
  it("does not claim that the ban is applied while auto-ban is disabled", () => {
    render(<BanPanel banName="Teemo" autoBanEnabled={false} />);

    expect(screen.getByText("Ban automatique désactivé.")).toBeVisible();
    expect(screen.queryByText("Banni dès que la phase le permet")).not.toBeInTheDocument();
  });
});
