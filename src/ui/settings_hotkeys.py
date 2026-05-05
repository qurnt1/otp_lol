"""
FILE NAME: src/ui/settings_hotkeys.py
GLOBAL PURPOSE:
- Mixin that provides hotkey-capture and hotkey-display methods for SettingsWindow.
- Groups shortcut capture mode, key normalization, and button refresh together.

DEPENDENCIES:
Used by:
- src/ui/settings_window.py via SettingsWindow inheritance.
Uses:
- Standard library: typing
"""

from typing import Optional


class SettingsHotkeysMixin:
    """Hotkey capture and display helpers for the settings window."""

    CAPTURE_TIMEOUT_MS = 5000
    CAPTURE_BOOTSTYLE = "warning"

    @staticmethod
    def _format_hotkey_display(value: str) -> str:
        return (value or "Set").replace("+", " + ").upper()

    def _refresh_hotkey_buttons(self) -> None:
        if hasattr(self, "hotkey_toggle_btn"):
            self.hotkey_toggle_btn.configure(
                text=self._format_hotkey_display(self.hotkey_toggle_var.get()),
                bootstyle="secondary-outline",
            )
        if hasattr(self, "hotkey_open_btn"):
            self.hotkey_open_btn.configure(
                text=self._format_hotkey_display(self.hotkey_open_site_var.get()),
                bootstyle="secondary-outline",
            )

    def _start_hotkey_capture(self, target: str) -> None:
        """Enter the one-shot shortcut capture mode for the selected hotkey button."""
        if self._capture_target and self._capture_target != target:
            self._cancel_hotkey_capture()
        if not self._capture_target and hasattr(self.parent, "suspend_hotkeys"):
            self.parent.suspend_hotkeys()
        self._capture_target = target
        self._pressed_modifiers.clear()
        if target == "toggle" and hasattr(self, "hotkey_toggle_btn"):
            self.hotkey_toggle_btn.configure(text="Press a shortcut...", bootstyle=self.CAPTURE_BOOTSTYLE)
        if target == "site" and hasattr(self, "hotkey_open_btn"):
            self.hotkey_open_btn.configure(text="Press a shortcut...", bootstyle=self.CAPTURE_BOOTSTYLE)
        self._capture_timeout_id = None
        try:
            self._capture_timeout_id = self.window.after(self.CAPTURE_TIMEOUT_MS, self._cancel_hotkey_capture)
        except Exception:
            pass
        self.window.focus_force()

    def _cancel_hotkey_capture(self) -> None:
        """Leave shortcut capture mode without changing the saved shortcut."""
        self._capture_target = None
        self._pressed_modifiers.clear()
        self._cancel_capture_timeout()
        self._refresh_hotkey_buttons()
        if hasattr(self.parent, "resume_hotkeys"):
            self.parent.resume_hotkeys()

    def _cancel_capture_timeout(self) -> None:
        if hasattr(self, "_capture_timeout_id") and self._capture_timeout_id:
            try:
                self.window.after_cancel(self._capture_timeout_id)
            except Exception:
                pass
            self._capture_timeout_id = None

    def _finish_hotkey_capture(self, sequence: str) -> None:
        """Persist the captured shortcut and let the main window re-register global hotkeys."""
        target_var = self.hotkey_toggle_var if self._capture_target == "toggle" else self.hotkey_open_site_var
        other_var = self.hotkey_open_site_var if self._capture_target == "toggle" else self.hotkey_toggle_var
        if sequence == other_var.get():
            self.parent.show_toast("Shortcut already in use.")
            self._cancel_hotkey_capture()
            return

        target_var.set(sequence)
        target_key = "hotkey_toggle_window" if self._capture_target == "toggle" else "hotkey_open_site"
        self.parent.update_param(target_key, sequence)
        self._cancel_hotkey_capture()

    def _normalize_capture_key(self, keysym: str) -> Optional[str]:
        key = (keysym or "").lower()
        mapping = {
            "control_l": "ctrl",
            "control_r": "ctrl",
            "alt_l": "alt",
            "alt_r": "alt",
            "shift_l": "shift",
            "shift_r": "shift",
            "prior": "pageup",
            "next": "pagedown",
            "return": "enter",
            "escape": "esc",
            "space": "space",
        }
        return mapping.get(key, key if key else None)

    def _on_hotkey_capture_keypress(self, event) -> Optional[str]:
        """Build a normalized hotkey sequence from Tk key events."""
        if not self._capture_target:
            return None

        key = self._normalize_capture_key(event.keysym)
        if not key:
            return "break"
        if key == "esc":
            self._cancel_hotkey_capture()
            return "break"

        if key in {"ctrl", "alt", "shift"}:
            self._pressed_modifiers.add(key)
            self._update_capture_button_label()
            return "break"

        modifiers = [modifier for modifier in ("ctrl", "alt", "shift") if modifier in self._pressed_modifiers]
        if not modifiers:
            self.parent.show_toast("Use at least Ctrl, Alt, or Shift.")
            self._cancel_hotkey_capture()
            return "break"

        self._finish_hotkey_capture("+".join([*modifiers, key]))
        return "break"

    def _on_hotkey_capture_keyrelease(self, event) -> Optional[str]:
        if not self._capture_target:
            return None
        key = self._normalize_capture_key(event.keysym)
        if key in {"ctrl", "alt", "shift"} and key in self._pressed_modifiers:
            self._pressed_modifiers.discard(key)
        return "break"

    def _update_capture_button_label(self) -> None:
        modifiers = sorted(self._pressed_modifiers)
        suffix = " + ".join(modifiers).upper().replace("+", " + ") + " + ..." if modifiers else "..."
        if self._capture_target == "toggle" and hasattr(self, "hotkey_toggle_btn"):
            self.hotkey_toggle_btn.configure(text=f"Press a shortcut... ({suffix})")
        elif self._capture_target == "site" and hasattr(self, "hotkey_open_btn"):
            self.hotkey_open_btn.configure(text=f"Press a shortcut... ({suffix})")
