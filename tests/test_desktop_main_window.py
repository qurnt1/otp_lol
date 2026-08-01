from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QCheckBox

from src.core.events import Connected, Disconnected, SpellsApplied, StatusChanged
from src.desktop.main_window import MainWindow


def build_settings():
    return {
        "auto_accept_enabled": True,
        "presets_enabled": True,
        "auto_ban_enabled": False,
        "auto_play_again_enabled": False,
        "selected_pick_1": "Garen",
        "selected_pick_2": "Lux",
        "selected_pick_3": "Ashe",
        "selected_ban": "Teemo",
    }


def test_runtime_events_update_visible_state(qtbot):
    window = MainWindow(build_settings())
    qtbot.addWidget(window)

    window.handle_runtime_event(Connected())
    window.handle_runtime_event(StatusChanged("Champion select", "INFO"))
    window.handle_runtime_event(SpellsApplied("Flash", "Teleport"))

    assert window.connection_chip.text() == "Client connected"
    assert window.status_label.text() == "Champion select"
    assert window.spells_label.text() == "Spells: Flash + Teleport"

    window.handle_runtime_event(Disconnected(False, "client_stopped"))
    assert window.connection_chip.text() == "Client offline"


def test_presets_switch_emits_canonical_command(qtbot):
    window = MainWindow(build_settings())
    qtbot.addWidget(window)
    spy = QSignalSpy(window.presets_changed)
    presets_switch = next(
        checkbox
        for checkbox in window.findChildren(QCheckBox)
        if checkbox.accessibleName() == "Pick presets"
    )

    presets_switch.setChecked(False)

    assert len(spy) == 1
    assert spy[0][0] is False
