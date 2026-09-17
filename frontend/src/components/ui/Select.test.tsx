import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { Select } from "./Select";

const options = [
  { id: "flash", label: "Flash" },
  { id: "ignite", label: "Ignite" },
];

const renderOption = (option: (typeof options)[number]) => <span className="test-option">
  <span className="test-icon" aria-hidden="true">{option.id}</span>
  <span>{option.label}</span>
</span>;

beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });
});

describe("Select custom rendering", () => {
  it("renders generic values and options and opens/closes with Enter and Escape", async () => {
    render(<Select label="Sort 1" value="flash" options={options} onChange={vi.fn()} renderOption={renderOption} renderValue={(option) => <span className="test-value">{option.label}</span>} />);
    const trigger = screen.getByRole("combobox", { name: "Sort 1" });

    expect(trigger.querySelector(".test-value")).toHaveTextContent("Flash");
    fireEvent.keyDown(trigger, { key: "Enter" });
    const flash = await screen.findByRole("option", { name: "Flash" });
    const ignite = screen.getByRole("option", { name: "Ignite" });
    expect(flash.querySelector(".test-icon")).toHaveTextContent("flash");
    expect(ignite.querySelector(".test-icon")).toHaveTextContent("ignite");

    fireEvent.keyDown(document.activeElement ?? trigger, { key: "Escape" });
    expect(screen.queryByRole("option", { name: "Flash" })).not.toBeInTheDocument();
  });
});
