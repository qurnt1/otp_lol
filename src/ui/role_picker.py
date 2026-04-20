"""
FILE NAME: src/ui/role_picker.py
GLOBAL PURPOSE:
- Build the role-profile picker used by the settings window.
- Keep role-selection UI separate from the main settings implementation.
- Highlight the currently selected profile while allowing fast profile switching.

KEY FUNCTIONS:
- open_role_picker: Open the role-profile picker dialog for the settings window.

AUDIENCE & LOGIC:
Why:
This module exists so profile-role selection remains a small, isolated UI helper instead of inflating the settings module further.
For whom:
Developers maintaining settings navigation and role-profile editing.

DEPENDENCIES:
Used by:
- src.ui.settings_window
Uses:
- Standard library typing helpers
- Third-party library: ttkbootstrap
- Local modules: src.config
"""

from typing import TYPE_CHECKING

import ttkbootstrap as ttk

from ..config import ROLE_PROFILE_LABELS, ROLE_PROFILE_ORDER

if TYPE_CHECKING:
    from .settings_window import SettingsWindow


def open_role_picker(owner: "SettingsWindow") -> None:
    """Open the profile role picker."""
    if owner.role_picker_window and owner.role_picker_window.winfo_exists():
        owner.role_picker_window.lift()
        owner.role_picker_window.focus_force()
        return

    picker = ttk.Toplevel(owner.window)
    owner.role_picker_window = picker
    if owner.window._icon_img:
        picker.iconphoto(False, owner.window._icon_img)
    picker.title("Choose a role profile")
    picker.resizable(False, False)
    picker.transient(owner.window)
    picker.geometry(f"310x360+{owner.window.winfo_x()+60}+{owner.window.winfo_y()+80}")
    picker.protocol("WM_DELETE_WINDOW", owner._close_role_picker)
    picker.bind("<Escape>", lambda e: owner._close_role_picker())

    container = ttk.Frame(picker, padding=12)
    container.pack(fill="both", expand=True)

    ttk.Label(
        container,
        text="Choose the profile to edit",
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w", pady=(0, 10))

    # Show the global profile first because it acts as the fallback source for all
    # role-specific overrides elsewhere in the application.
    roles = ["GLOBAL", *ROLE_PROFILE_ORDER]
    current_role = owner._get_selected_profile_role()

    for role in roles:
        icon = owner._load_role_icon(role, size=24)
        suffix = "  ✓" if role == current_role else ""
        btn = ttk.Button(
            container,
            text=f"  {ROLE_PROFILE_LABELS.get(role, role.title())}{suffix}",
            command=lambda r=role: owner._select_profile_role(r),
            bootstyle="secondary-outline" if role != current_role else "primary",
            compound="left",
            width=24,
        )
        if icon:
            btn.configure(image=icon)
            btn.image = icon
        btn.pack(fill="x", pady=4)

    picker.focus_force()
