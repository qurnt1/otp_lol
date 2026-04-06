"""Website picker helpers for settings."""

import os
from typing import TYPE_CHECKING

import ttkbootstrap as ttk
from PIL import Image, ImageTk

from ..config import HOTKEY_SITE_LABELS, HOTKEY_SITE_ORDER, STATS_SITE_LABELS, STATS_SITE_ORDER, WEBSITE_LOGO_FILES, resource_path

if TYPE_CHECKING:
    from .settings_window import SettingsWindow


def _load_site_logo(owner: "SettingsWindow", site: str, size: int = 28):
    if not hasattr(owner, "website_logo_cache"):
        owner.website_logo_cache = {}
    cache_key = (site, size)
    if cache_key in owner.website_logo_cache:
        return owner.website_logo_cache[cache_key]

    icon_rel_path = WEBSITE_LOGO_FILES.get(site)
    if not icon_rel_path:
        return None

    icon_path = resource_path(icon_rel_path)
    if not os.path.exists(icon_path):
        alt_path = os.path.splitext(icon_path)[0] + ".webp"
        if os.path.exists(alt_path):
            icon_path = alt_path
        else:
            return None

    try:
        image = Image.open(icon_path).convert("RGBA")
        image.thumbnail((size, size), Image.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        left = (size - image.width) // 2
        top = (size - image.height) // 2
        canvas.paste(image, (left, top), image)
        photo = ImageTk.PhotoImage(canvas)
        owner.website_logo_cache[cache_key] = photo
        return photo
    except Exception:
        return None


def open_site_picker(owner: "SettingsWindow", picker_type: str) -> None:
    """Open the website picker as a vertical list."""
    if owner.site_picker_window and owner.site_picker_window.winfo_exists():
        owner.site_picker_window.destroy()

    picker = ttk.Toplevel(owner.window)
    owner.site_picker_window = picker
    if owner.window._icon_img:
        picker.iconphoto(False, owner.window._icon_img)
    picker.resizable(False, False)
    picker.transient(owner.window)
    picker.protocol("WM_DELETE_WINDOW", owner._close_site_picker)
    picker.bind("<Escape>", lambda e: owner._close_site_picker())

    if picker_type == "stats":
        picker.title("Choose the main button website")
        allowed_sites = STATS_SITE_ORDER
        labels = STATS_SITE_LABELS
        current_site = owner.preferred_stats_site_var.get()
        on_select = owner._select_stats_site
    else:
        picker.title("Choose the shortcut website")
        allowed_sites = HOTKEY_SITE_ORDER
        labels = HOTKEY_SITE_LABELS
        current_site = owner.preferred_hotkey_site_var.get()
        on_select = owner._select_hotkey_site

    picker.geometry(f"320x260+{owner.window.winfo_x()+70}+{owner.window.winfo_y()+90}")

    container = ttk.Frame(picker, padding=12)
    container.pack(fill="both", expand=True)

    ttk.Label(
        container,
        text="Choose the website to use",
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w", pady=(0, 10))

    for site in allowed_sites:
        row_frame = ttk.Frame(container)
        row_frame.pack(fill="x", pady=4)
        icon = _load_site_logo(owner, site, size=28)
        suffix = "  ✓" if site == current_site else ""
        btn = ttk.Button(
            row_frame,
            text=f"  {labels.get(site, site)}{suffix}",
            command=lambda s=site: on_select(s),
            bootstyle="secondary-outline" if site != current_site else "primary",
            width=28,
            compound="left",
            padding=(10, 8),
        )
        if icon:
            btn.configure(image=icon)
            btn.image = icon
        btn.pack(fill="x")

    picker.focus_force()
