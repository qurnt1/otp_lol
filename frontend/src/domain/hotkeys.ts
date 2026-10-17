type HotkeyModifiers = Pick<KeyboardEvent, "altKey" | "ctrlKey" | "metaKey" | "shiftKey">;

const keyAliases: Record<string, string> = {
  " ": "space", ArrowLeft: "left", ArrowUp: "up", ArrowRight: "right", ArrowDown: "down",
  Backspace: "backspace", Delete: "delete", End: "end", Enter: "enter", Escape: "escape",
  Home: "home", Insert: "insert", PageDown: "pagedown", PageUp: "pageup", Tab: "tab",
};

export function formatCapturedHotkey(key: string, modifiers: HotkeyModifiers): string | null {
  const parts = [
    modifiers.ctrlKey && "ctrl",
    modifiers.altKey && "alt",
    modifiers.shiftKey && "shift",
    modifiers.metaKey && "win",
  ].filter(Boolean);
  if (!parts.length || ["Alt", "Control", "Shift", "Meta"].includes(key)) return null;
  return [...parts, keyAliases[key] ?? key.toLowerCase()].join("+");
}
