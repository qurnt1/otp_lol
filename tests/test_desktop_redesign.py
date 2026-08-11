from copy import deepcopy

from src.config.settings import DEFAULT_PARAMS
from src.desktop.main_window import MainWindow


def test_league_companion_shell_exposes_operational_pages(qtbot):
    window = MainWindow(deepcopy(DEFAULT_PARAMS))
    qtbot.addWidget(window)

    assert set(window.nav_buttons) == {"home", "presets", "automation", "history", "settings"}
    assert window.page_title.text() == "Home"
    assert window.nav_buttons["home"].isChecked()
    assert all(button.accessibleName() for button in window.nav_buttons.values())
    assert window.stats_button.accessibleName() == "Open configured player stats website"

    window.edit_presets_button.click()
    assert window.page_title.text() == "Presets"

    for key, title in window._PAGE_TITLES.items():
        window.nav_buttons[key].click()
        assert window.page_title.text() == title
        assert window.nav_buttons[key].isChecked()
