import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AssetImage } from "./AssetImage";

describe("AssetImage", () => {
  it("retries immediately when the image source changes after a failure", () => {
    const { rerender } = render(<AssetImage src="/first.png" alt="portrait" fallback="fallback" />);
    fireEvent.error(screen.getByRole("img", { name: "portrait" }));
    expect(screen.getByText("fallback")).toBeInTheDocument();

    rerender(<AssetImage src="/second.png" alt="portrait" fallback="fallback" />);

    expect(screen.getByRole("img", { name: "portrait" })).toHaveAttribute("src", "/second.png");
  });
});
