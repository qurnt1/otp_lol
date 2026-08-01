"""Primary PyQt6 window for OTP LOL."""

from collections import deque
from collections.abc import Mapping
from functools import partial
from typing import Any

from PyQt6.QtCore import QSignalBlocker, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.config import PICK_SLOT_LABELS, PICK_SLOT_ORDER, STATS_SITE_LABELS
from src.core.events import (
    ChampionBanned,
    ChampionPicked,
    Connected,
    Disconnected,
    PhaseChanged,
    PlayAgainSucceeded,
    ReadyCheckAccepted,
    RuntimeEvent,
    SpellsApplied,
    StatusChanged,
    SummonerUpdated,
    ToastRequested,
    UpdateAvailable,
)
from src.services.profile_config import build_effective_profile_config
from src.services.skin_modes import build_main_skin_overrides, get_effective_skin_mode_for_slot

from .images import pil_to_qimage, qpixmap_from_image
from .tasks import TaskRunner, guarded_callback
from .theme import stylesheet_for


class AutomationCard(QFrame):
    toggled = pyqtSignal(str, bool)

    def __init__(self, key: str, title: str, description: str, enabled: bool) -> None:
        super().__init__()
        self.key = key
        self.setProperty("automationCard", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setProperty("cardTitle", True)
        self.switch = QCheckBox()
        self.switch.setAccessibleName(title)
        self.switch.setChecked(enabled)
        self.switch.toggled.connect(partial(self.toggled.emit, key))
        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(self.switch)
        description_label = QLabel(description)
        description_label.setProperty("secondary", True)
        description_label.setWordWrap(True)
        layout.addLayout(header)
        layout.addWidget(description_label)

    def set_checked(self, checked: bool) -> None:
        with QSignalBlocker(self.switch):
            self.switch.setChecked(checked)


class PresetRow(QFrame):
    skin_cycle_requested = pyqtSignal(str)

    def __init__(self, slot_key: str) -> None:
        super().__init__()
        self.slot_key = slot_key
        self.setProperty("presetRow", True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        self.icon = QLabel()
        self.icon.setFixedSize(42, 42)
        self.icon.setScaledContents(True)
        name_column = QVBoxLayout()
        self.slot_label = QLabel(PICK_SLOT_LABELS[slot_key])
        self.slot_label.setProperty("secondary", True)
        self.champion = QLabel("None")
        self.champion.setProperty("cardTitle", True)
        name_column.addWidget(self.slot_label)
        name_column.addWidget(self.champion)
        self.spells = QLabel("No spells")
        self.spells.setProperty("secondary", True)
        self.runes = QLabel("No rune page")
        self.runes.setProperty("secondary", True)
        self.skin = QPushButton("Skin off")
        self.skin.clicked.connect(partial(self.skin_cycle_requested.emit, slot_key))
        layout.addWidget(self.icon)
        layout.addLayout(name_column, 1)
        layout.addWidget(self.spells, 1)
        layout.addWidget(self.runes, 1)
        layout.addWidget(self.skin)

    def update_data(self, champion: str, slot: Mapping[str, Any], skin_mode: str, *, enabled: bool) -> None:
        self.champion.setText(champion or "None")
        spell_1 = str(slot.get("spell_1") or "None").replace("(None)", "None")
        spell_2 = str(slot.get("spell_2") or "None").replace("(None)", "None")
        self.spells.setText(f"{spell_1} + {spell_2}")
        rune_name = str(slot.get("rune_page_name") or "No rune page")
        if rune_name != "No rune page" and not bool(slot.get("rune_auto_apply", True)):
            rune_name += " · off"
        self.runes.setText(rune_name)
        if skin_mode == "fixed":
            skin_text = str(slot.get("skin_name") or "Fixed skin")
        elif skin_mode == "random":
            skin_text = f"Random ({len(slot.get('random_skin_pool', []))})"
        else:
            skin_text = "Skin off"
        self.skin.setText(skin_text)
        self.skin.setEnabled(enabled)


class MainWindow(QMainWindow):
    """Render desktop state and emit user intent without owning runtime services."""

    setting_changed = pyqtSignal(str, object)
    presets_changed = pyqtSignal(bool)
    skin_cycle_requested = pyqtSignal(str)
    settings_requested = pyqtSignal()
    history_requested = pyqtSignal()
    stats_requested = pyqtSignal()
    close_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(
        self,
        settings: Mapping[str, Any],
        *,
        data_dragon: Any | None = None,
        task_runner: TaskRunner | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("OTP LOL")
        self.setMinimumSize(720, 700)
        self.resize(820, 760)
        self.data_dragon = data_dragon
        self.task_runner = task_runner
        self.settings = dict(settings)
        self.automation_cards: dict[str, AutomationCard] = {}
        self.preset_rows: dict[str, PresetRow] = {}
        self._toast_queue: deque[tuple[str, int]] = deque()
        self._toast_active = False
        self._allow_close = False
        self._icon_generation = 0
        self._pulse_on = False
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(850)
        self._pulse_timer.timeout.connect(self._pulse_connection)
        self.setStyleSheet(stylesheet_for(str(settings.get("theme") or "darkly")))
        self._build_ui()
        self.refresh_settings(settings)
        self.statusBar().showMessage("Waiting for the League client")

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("desktopRoot")
        page = QVBoxLayout(root)
        page.setContentsMargins(20, 18, 20, 16)
        page.setSpacing(13)
        page.addWidget(self._build_top_bar())
        page.addWidget(self._build_hero())
        page.addLayout(self._build_automation_grid())
        page.addWidget(self._build_loadout(), stretch=1)
        page.addLayout(self._build_actions())
        self.setCentralWidget(root)

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 12, 16, 12)
        brand = QVBoxLayout()
        brand_name = QLabel("OTP LOL")
        brand_name.setObjectName("brandName")
        brand_subtitle = QLabel("League Client automation")
        brand_subtitle.setObjectName("brandSubtitle")
        brand.addWidget(brand_name)
        brand.addWidget(brand_subtitle)
        self.stats_button = QPushButton("Open stats")
        self.stats_button.setAccessibleName("Open player stats website")
        self.stats_button.clicked.connect(self.stats_requested.emit)
        self.connection_chip = QLabel("Client offline")
        self.connection_chip.setObjectName("connectionChip")
        self.connection_chip.setProperty("connected", False)
        layout.addLayout(brand)
        layout.addStretch()
        layout.addWidget(self.stats_button)
        layout.addWidget(self.connection_chip)
        return bar

    def _build_hero(self) -> QFrame:
        hero = QFrame()
        hero.setObjectName("heroPanel")
        layout = QVBoxLayout(hero)
        layout.setContentsMargins(18, 15, 18, 15)
        title = QLabel("Champion select, under control")
        title.setObjectName("heroTitle")
        self.status_label = QLabel("Connect the League client to start automation.")
        self.status_label.setProperty("secondary", True)
        self.status_label.setWordWrap(True)
        self.phase_label = QLabel("Inactive")
        self.phase_label.setProperty("secondary", True)
        self.spells_label = QLabel("Spells will appear after champion selection.")
        self.spells_label.setProperty("secondary", True)
        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.phase_label)
        layout.addWidget(self.spells_label)
        return hero

    def _build_automation_grid(self) -> QGridLayout:
        grid = QGridLayout()
        definitions = (
            ("auto_accept_enabled", "Auto accept", "Accept ready checks immediately."),
            ("presets_enabled", "Pick presets", "Apply picks, spells, runes and skins."),
            ("auto_ban_enabled", "Auto ban", "Ban the configured champion."),
            ("auto_play_again_enabled", "Play again", "Return to lobby after the game."),
        )
        for index, (key, title, description) in enumerate(definitions):
            card = AutomationCard(key, title, description, False)
            card.toggled.connect(self._forward_setting)
            self.automation_cards[key] = card
            grid.addWidget(card, index // 2, index % 2)
        return grid

    def _build_loadout(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("loadoutPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        heading = QHBoxLayout()
        title = QLabel("Current preset route")
        title.setObjectName("sectionTitle")
        self.ban_label = QLabel("Ban: None")
        self.ban_label.setProperty("secondary", True)
        heading.addWidget(title)
        heading.addStretch()
        heading.addWidget(self.ban_label)
        layout.addLayout(heading)
        for slot_key in PICK_SLOT_ORDER:
            row = PresetRow(slot_key)
            row.skin_cycle_requested.connect(self.skin_cycle_requested.emit)
            self.preset_rows[slot_key] = row
            layout.addWidget(row)
        return panel

    def _build_actions(self) -> QHBoxLayout:
        actions = QHBoxLayout()
        for label, accessible_name, signal in (
            ("Settings", "Open settings", self.settings_requested),
            ("History", "Open automation history", self.history_requested),
            ("Quit", "Quit OTP LOL", self.quit_requested),
        ):
            button = QPushButton(label)
            button.setAccessibleName(accessible_name)
            button.clicked.connect(signal.emit)
            if label == "Quit":
                actions.addStretch()
            actions.addWidget(button)
        return actions

    @pyqtSlot(str, bool)
    def _forward_setting(self, key: str, enabled: bool) -> None:
        if key == "presets_enabled":
            self.presets_changed.emit(enabled)
        else:
            self.setting_changed.emit(key, enabled)

    def apply_theme(self, theme_name: str) -> None:
        self.setStyleSheet(stylesheet_for(theme_name))

    def refresh_settings(self, settings: Mapping[str, Any]) -> None:
        self.settings = dict(settings)
        for key, card in self.automation_cards.items():
            card.set_checked(bool(settings.get(key, False)))
        effective = build_effective_profile_config(dict(settings))
        overrides = build_main_skin_overrides(settings)
        slots = effective.get("pick_slots", {})
        enabled = bool(settings.get("presets_enabled", False))
        for slot_key in PICK_SLOT_ORDER:
            slot = slots.get(slot_key, {}) if isinstance(slots, Mapping) else {}
            mode = get_effective_skin_mode_for_slot(slot_key, effective, overrides)
            self.preset_rows[slot_key].update_data(
                str(slot.get("champion") or "None"),
                slot,
                mode,
                enabled=enabled,
            )
        self.ban_label.setText(f"Ban: {settings.get('selected_ban') or 'None'}")
        site = str(settings.get("preferred_stats_site") or "opgg")
        self.stats_button.setText(f"Open {STATS_SITE_LABELS.get(site, 'stats')}")
        self._refresh_stats_enabled()
        self.apply_theme(str(settings.get("theme") or "darkly"))
        self._load_champion_icons()

    def _load_champion_icons(self) -> None:
        if self.data_dragon is None or self.task_runner is None:
            return
        names = {
            slot_key: self.preset_rows[slot_key].champion.text()
            for slot_key in PICK_SLOT_ORDER
        }
        self._icon_generation += 1
        generation = self._icon_generation

        def load() -> dict[str, Any]:
            return {
                "generation": generation,
                "images": {
                    slot_key: pil_to_qimage(self.data_dragon.get_champion_icon(name), size=(42, 42))
                    for slot_key, name in names.items()
                },
            }

        self.task_runner.submit(load, guarded_callback(self, "_apply_champion_icons"))

    def _apply_champion_icons(self, payload: Mapping[str, Any]) -> None:
        if payload.get("generation") != self._icon_generation:
            return
        images = payload.get("images", {})
        if not isinstance(images, Mapping):
            return
        for slot_key, image in images.items():
            if slot_key in self.preset_rows:
                pixmap = qpixmap_from_image(image)
                self.preset_rows[slot_key].icon.setPixmap(pixmap)

    def _current_riot_id(self) -> str:
        if bool(self.settings.get("summoner_name_auto_detect", True)):
            return str(self.settings.get("auto_detected_riot_id") or "")
        return str(self.settings.get("manual_summoner_name") or "")

    def _refresh_stats_enabled(self) -> None:
        riot_id = self._current_riot_id().strip()
        self.stats_button.setEnabled("#" in riot_id and all(riot_id.split("#", 1)))

    @pyqtSlot(object)
    def handle_runtime_event(self, event: RuntimeEvent) -> None:
        if isinstance(event, Connected):
            self._set_connected(True)
        elif isinstance(event, Disconnected):
            self._set_connected(False)
        elif isinstance(event, StatusChanged):
            self.status_label.setText(event.message)
            self.statusBar().showMessage(event.message)
        elif isinstance(event, PhaseChanged):
            self.phase_label.setText(event.phase)
        elif isinstance(event, SummonerUpdated):
            self.settings["auto_detected_riot_id"] = event.riot_id or ""
            self._refresh_stats_enabled()
        elif isinstance(event, ChampionPicked):
            self.enqueue_toast(f"Picked {event.champion}", 3000)
        elif isinstance(event, ChampionBanned):
            self.ban_label.setText(f"Ban: {event.champion}")
        elif isinstance(event, SpellsApplied):
            self.spells_label.setText(f"Spells: {event.first} + {event.second}")
            self.enqueue_toast(f"Spells applied: {event.first} + {event.second}", 3000)
        elif isinstance(event, ReadyCheckAccepted):
            self.enqueue_toast("Match accepted", 3000)
        elif isinstance(event, PlayAgainSucceeded):
            self.enqueue_toast("Returned to lobby", 2500)
        elif isinstance(event, ToastRequested):
            self.enqueue_toast(event.message, event.duration_ms)
        elif isinstance(event, UpdateAvailable):
            self.statusBar().showMessage(f"Version {event.version} is available")

    def enqueue_toast(self, message: str, duration_ms: int = 2000) -> None:
        self._toast_queue.append((message, duration_ms))
        if not self._toast_active:
            self._show_next_toast()

    def _show_next_toast(self) -> None:
        if not self._toast_queue:
            self._toast_active = False
            return
        self._toast_active = True
        message, duration = self._toast_queue.popleft()
        self.statusBar().showMessage(message)
        QTimer.singleShot(max(duration, 100), self._show_next_toast)

    def _set_connected(self, connected: bool) -> None:
        self.connection_chip.setText("Client connected" if connected else "Client offline")
        self.connection_chip.setProperty("connected", connected)
        if connected:
            self._pulse_timer.start()
        else:
            self._pulse_timer.stop()
            self.connection_chip.setProperty("pulsing", False)
        self._repolish_connection()

    def _pulse_connection(self) -> None:
        self._pulse_on = not self._pulse_on
        self.connection_chip.setProperty("pulsing", self._pulse_on)
        self._repolish_connection()

    def _repolish_connection(self) -> None:
        self.connection_chip.style().unpolish(self.connection_chip)
        self.connection_chip.style().polish(self.connection_chip)

    def allow_close(self) -> None:
        self._allow_close = True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            event.accept()
            return
        self.close_requested.emit()
        event.ignore()
