from copy import deepcopy
from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtTest import QSignalSpy

from src.config.constants import (
    APP_CONTENT_ICON_NAMES,
    APP_ICON_FILES,
    APP_IMAGE_FILES,
    APP_NAVIGATION_ICON_NAMES,
)
from src.config.settings import DEFAULT_PARAMS
from src.desktop.images import app_icon_path, load_app_icon
from src.desktop.main_window import MainWindow


def test_league_companion_shell_exposes_operational_pages(qtbot):
    window = MainWindow(deepcopy(DEFAULT_PARAMS))
    qtbot.addWidget(window)

    assert set(window.nav_buttons) == {"home", "presets", "automation", "history", "settings"}
    assert window.page_title.text() == "Home"
    assert window.nav_buttons["home"].isChecked()
    assert all(button.accessibleName() for button in window.nav_buttons.values())
    assert all(not button.icon().isNull() for button in window.nav_buttons.values())
    assert not window.account_avatar.pixmap().isNull()
    assert not window.rank_icon.pixmap().isNull()
    assert not window.brand_logo.pixmap().isNull()
    assert all(not icon.pixmap().isNull() for icon in window.quick_access_icons.values())
    assert not window.active_champion_icon.pixmap().isNull()
    assert all(not icon.pixmap().isNull() for icon in window.active_spell_icons)
    assert not window.active_rune_icon.pixmap().isNull()
    assert not window.active_skin_icon.pixmap().isNull()
    assert all(not row.icon.pixmap().isNull() for row in window.preset_rows.values())
    assert window.riot_client_button.accessibleName() == "Open League Client"
    assert window.riot_client_button.height() == window.connection_panel.height() == 56
    assert not window.queue_hint.icon().isNull()
    assert window.open_stats_button.accessibleName() == "Open selected stats website"

    window.edit_presets_button.click()
    assert window.page_title.text() == "Presets"

    for key, title in window._PAGE_TITLES.items():
        window.nav_buttons[key].click()
        assert window.page_title.text() == title
        assert window.nav_buttons[key].isChecked()


def test_local_icon_set_has_navigation_and_content_assets(qtbot):
    expected_names = (*APP_NAVIGATION_ICON_NAMES, *APP_CONTENT_ICON_NAMES)

    assert tuple(APP_ICON_FILES) == expected_names
    for name in expected_names:
        path = Path(app_icon_path(name))
        assert path.is_file()
        assert path.parent.name == "navigation"
        assert path.suffix == ".svg"
        assert 'stroke="#F2F5F8"' in path.read_text(encoding="utf-8")
        assert not load_app_icon(name).isNull()

    assert Path(APP_IMAGE_FILES["icon_ico"]).name == "garen.ico"
    assert Path(APP_IMAGE_FILES["icon_ico"]).is_file()
    assert Path(APP_IMAGE_FILES["riot_client_logo"]).is_file()
    assert Path(APP_IMAGE_FILES["league_client_logo"]).is_file()


def test_settings_sidebar_opens_detailed_settings_signal(qtbot):
    window = MainWindow(deepcopy(DEFAULT_PARAMS))
    qtbot.addWidget(window)
    spy = QSignalSpy(window.settings_requested)

    window.nav_buttons["settings"].click()

    assert window.page_title.text() == "Settings"
    assert spy.count() == 1


def test_local_icon_loader_returns_icons_and_supports_tint(qtbot):
    icon = load_app_icon("home", size=24)
    tinted_icon = load_app_icon("rank_placeholder", size=32, color="#D0A843")

    assert not icon.isNull()
    assert not tinted_icon.isNull()
    assert icon.actualSize(QSize(24, 24)).isValid()
    assert tinted_icon.actualSize(QSize(32, 32)).isValid()

    with pytest.raises(ValueError, match="Unknown application icon"):
        app_icon_path("missing")
    with pytest.raises(ValueError, match="greater than zero"):
        load_app_icon("home", size=0)
    with pytest.raises(ValueError, match="Invalid icon color"):
        load_app_icon("home", color="not-a-color")
