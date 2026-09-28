import { describe, expect, it } from "vitest";

import { formatCapturedHotkey } from "./hotkeys";

describe("formatCapturedHotkey", () => {
  it("formats modifiers and named keys in the backend syntax", () => {
    expect(formatCapturedHotkey("ArrowLeft", { ctrlKey: true, altKey: true, shiftKey: false, metaKey: false }))
      .toBe("ctrl+alt+left");
  });

  it("does not accept an unmodified key or a modifier by itself", () => {
    const noModifiers = { ctrlKey: false, altKey: false, shiftKey: false, metaKey: false };
    expect(formatCapturedHotkey("p", noModifiers)).toBeNull();
    expect(formatCapturedHotkey("Alt", { ...noModifiers, altKey: true })).toBeNull();
  });
});
