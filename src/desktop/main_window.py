"""PySide6 League Companion shell and operational desktop pages.

THESIS: Show connection, active preset, automation, and health at a glance; refuse
the crowded settings wall.
OWN-WORLD: Midnight navy surfaces, warm gold action state, green connection state,
compact Segoe UI, thin cool borders, and quiet layered depth.
STORY: Home answers the live questions first, while Presets, Automation, History,
and Settings hold focused configuration and review tasks.
FIRST VIEWPORT: A persistent sidebar frames a wide Home canvas with a live header,
three operational panels, quick access, and recent activity.
FORM: Reference-image shell with reusable panels, cards, toggle rows, and a stacked
page workspace, implemented with PySide6 and existing controller signals.
"""

from collections import deque
from collections.abc import Mapping
from functools import partial
from typing import Any

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.config import CURRENT_VERSION, PICK_SLOT_LABELS, PICK_SLOT_ORDER, STATS_SITE_LABELS
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
from src.services.history import format_history_entry, get_history_entries
from src.services.profile_config import build_effective_profile_config
from src.services.skin_modes import build_main_skin_overrides, get_effective_skin_mode_for_slot

from .images import pil_to_qimage, qpixmap_from_image
from .tasks import TaskRunner, guarded_callback
from .theme import stylesheet_for


def _label(text: str = "", object_name: str | None = None, *, secondary: bool = False) -> QLabel:
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    if secondary:
        label.setProperty("secondary", True)
    return label


class Panel(QFrame):
    """Reusable bordered surface for the shell pages."""

    def __init__(self, object_name: str = "panel") -> None:
        super().__init__()
        self.setObjectName(object_name)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)


class AutomationCard(Panel):
    toggled = Signal(str, bool)

    def __init__(self, key: str, title: str, description: str, enabled: bool) -> None:
        super().__init__("automationCard")
        self.key = key
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(7)
        header = QHBoxLayout()
        title_label = _label(title, "cardTitle")
        self.switch = QCheckBox()
        self.switch.setAccessibleName("Pick presets" if key == "presets_enabled" else title)
        self.switch.setToolTip(description)
        self.switch.setChecked(enabled)
        self.switch.toggled.connect(partial(self.toggled.emit, key))
        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(self.switch)
        layout.addLayout(header)
        layout.addWidget(_label(description, secondary=True))

    def set_checked(self, checked: bool) -> None:
        with QSignalBlocker(self.switch):
            self.switch.setChecked(checked)


class PresetRow(Panel):
    skin_cycle_requested = Signal(str)

    def __init__(self, slot_key: str) -> None:
        super().__init__("presetCard")
        self.slot_key = slot_key
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 15, 16, 15)
        layout.setSpacing(10)

        heading = QHBoxLayout()
        self.slot_label = _label(PICK_SLOT_LABELS[slot_key].upper(), "eyebrow")
        heading.addWidget(self.slot_label)
        heading.addStretch()
        self.enabled_label = _label("ON", "statePill")
        heading.addWidget(self.enabled_label)
        layout.addLayout(heading)

        identity = QHBoxLayout()
        self.icon = QLabel()
        self.icon.setFixedSize(54, 54)
        self.icon.setScaledContents(True)
        self.champion = _label("None", "cardTitle")
        self.champion.setAccessibleName(f"{PICK_SLOT_LABELS[slot_key]} champion")
        identity.addWidget(self.icon)
        identity.addWidget(self.champion)
        identity.addStretch()
        layout.addLayout(identity)

        self.spells = _label("No spells", secondary=True)
        self.runes = _label("No rune page", secondary=True)
        self.skin = QPushButton("Skin off")
        self.skin.setAccessibleName(f"Cycle skin mode for {PICK_SLOT_LABELS[slot_key]}")
        self.skin.clicked.connect(partial(self.skin_cycle_requested.emit, slot_key))
        layout.addWidget(self.spells)
        layout.addWidget(self.runes)
        layout.addWidget(self.skin)

    def update_data(self, champion: str, slot: Mapping[str, Any], skin_mode: str, *, enabled: bool) -> None:
        self.champion.setText(champion or "None")
        spell_1 = str(slot.get("spell_1") or "None").replace("(None)", "None")
        spell_2 = str(slot.get("spell_2") or "None").replace("(None)", "None")
        self.spells.setText(f"Spells  {spell_1} + {spell_2}")
        rune_name = str(slot.get("rune_page_name") or "No rune page")
        if rune_name != "No rune page" and not bool(slot.get("rune_auto_apply", True)):
            rune_name += " - off"
        self.runes.setText(f"Runes   {rune_name}")
        if skin_mode == "fixed":
            skin_text = str(slot.get("skin_name") or "Fixed skin")
        elif skin_mode == "random":
            skin_text = f"Random ({len(slot.get('random_skin_pool', []))})"
        else:
            skin_text = "Skin off"
        self.skin.setText(f"Skin    {skin_text}")
        self.skin.setEnabled(enabled)
        self.enabled_label.setText("ON" if enabled else "OFF")
        self.enabled_label.setProperty("state", "on" if enabled else "off")
        self._repolish(self.enabled_label)

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)


class MainWindow(QMainWindow):
    """Render desktop state and emit user intent without owning runtime services."""

    setting_changed = Signal(str, object)
    presets_changed = Signal(bool)
    skin_cycle_requested = Signal(str)
    settings_requested = Signal()
    history_requested = Signal()
    stats_requested = Signal()
    close_requested = Signal()
    quit_requested = Signal()

    _PAGE_TITLES = {
        "home": "Home",
        "presets": "Presets",
        "automation": "Automation",
        "history": "History",
        "settings": "Settings",
    }

    def __init__(
        self,
        settings: Mapping[str, Any],
        *,
        data_dragon: Any | None = None,
        task_runner: TaskRunner | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("OTP LOL")
        self.setMinimumSize(980, 680)
        self.resize(1440, 900)
        self.data_dragon = data_dragon
        self.task_runner = task_runner
        self.settings = dict(settings)
        self.automation_cards: dict[str, AutomationCard] = {}
        self.preset_rows: dict[str, PresetRow] = {}
        self.nav_buttons: dict[str, QPushButton] = {}
        self._page_indexes: dict[str, int] = {}
        self._toast_queue: deque[tuple[str, int]] = deque()
        self._toast_active = False
        self._allow_close = False
        self._icon_generation = 0
        self._pulse_on = False
        self._connected = False
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(850)
        self._pulse_timer.timeout.connect(self._pulse_connection)
        self.setStyleSheet(stylesheet_for(str(settings.get("theme") or "darkly")))
        self._build_shell()
        self.refresh_settings(settings)
        self.statusBar().showMessage("Waiting for the League client")

    def _build_shell(self) -> None:
        shell = QWidget()
        shell.setObjectName("desktopRoot")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(self._build_sidebar())

        content = QWidget()
        content.setObjectName("contentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 18, 24, 12)
        content_layout.setSpacing(18)
        content_layout.addWidget(self._build_header())

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")
        for key, builder in (
            ("home", self._build_home_page),
            ("presets", self._build_presets_page),
            ("automation", self._build_automation_page),
            ("history", self._build_history_page),
            ("settings", self._build_settings_page),
        ):
            self._page_indexes[key] = self.page_stack.addWidget(builder())
        content_layout.addWidget(self.page_stack, 1)
        shell_layout.addWidget(content, 1)
        self.setCentralWidget(shell)
        self._show_page("home")

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(236)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 20, 18, 16)
        layout.setSpacing(8)

        brand = QVBoxLayout()
        brand.setSpacing(2)
        brand.addWidget(_label("OTP LOL", "brandName"))
        brand.addWidget(_label(f"v{CURRENT_VERSION}", "brandVersion", secondary=True))
        layout.addLayout(brand)
        layout.addSpacing(22)

        for key, label in self._PAGE_TITLES.items():
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setAccessibleName(f"Open {label} page")
            button.clicked.connect(partial(self._show_page, key))
            self.nav_buttons[key] = button
            layout.addWidget(button)
        layout.addStretch(1)

        account = Panel("accountPanel")
        account_layout = QVBoxLayout(account)
        account_layout.setContentsMargins(12, 12, 12, 12)
        self.account_name = _label("No Riot ID", "accountName")
        self.account_region = _label("Client offline", secondary=True)
        self.account_status = _label("Offline", "accountStatus")
        account_layout.addWidget(self.account_name)
        account_layout.addWidget(self.account_region)
        account_layout.addWidget(self.account_status)
        layout.addWidget(account)
        layout.addSpacing(12)
        layout.addWidget(_label("Local only  |  No account  |  No tracking", "footerNote", secondary=True))
        return sidebar

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("appHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        title_column = QVBoxLayout()
        self.page_title = _label("Home", "pageTitle")
        self.page_subtitle = _label("A clear view of what OTP LOL is doing.", secondary=True)
        title_column.addWidget(self.page_title)
        title_column.addWidget(self.page_subtitle)
        layout.addLayout(title_column)
        layout.addStretch(1)

        self.connection_chip = _label("Client offline", "connectionChip")
        self.connection_chip.setProperty("connected", False)
        layout.addWidget(self.connection_chip)
        self.stats_button = QPushButton("Open configured stats")
        self.stats_button.setObjectName("secondaryButton")
        self.stats_button.setAccessibleName("Open configured player stats website")
        self.stats_button.clicked.connect(self.stats_requested.emit)
        layout.addWidget(self.stats_button)
        return header

    def _build_home_page(self) -> QWidget:
        page = self._page_container()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        top_grid = QGridLayout()
        top_grid.setSpacing(14)
        top_grid.addWidget(self._build_match_panel(), 0, 0)
        top_grid.addWidget(self._build_active_preset_panel(), 0, 1)
        top_grid.addWidget(self._build_home_automation_panel(), 0, 2)
        top_grid.setColumnStretch(0, 4)
        top_grid.setColumnStretch(1, 4)
        top_grid.setColumnStretch(2, 3)
        layout.addLayout(top_grid)
        layout.addWidget(self._build_quick_access_panel())

        bottom_grid = QGridLayout()
        bottom_grid.setSpacing(14)
        bottom_grid.addWidget(self._build_activity_panel(), 0, 0)
        bottom_grid.addWidget(self._build_shortcuts_panel(), 0, 1)
        bottom_grid.addWidget(self._build_news_panel(), 0, 2)
        bottom_grid.setColumnStretch(0, 5)
        bottom_grid.setColumnStretch(1, 4)
        bottom_grid.setColumnStretch(2, 3)
        layout.addLayout(bottom_grid)
        layout.addStretch(1)
        return page

    def _build_match_panel(self) -> QWidget:
        panel = Panel("matchPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)
        layout.addWidget(_label("MATCH STATUS", "eyebrow"))
        self.status_label = _label("Waiting for League client", "heroTitle")
        self.phase_label = _label("Waiting for League client.", secondary=True)
        self.spells_label = _label("All systems operational", secondary=True)
        self.ban_label = _label("Ban: None", secondary=True)
        layout.addWidget(self.status_label)
        layout.addWidget(self.phase_label)
        layout.addWidget(self.spells_label)
        layout.addWidget(self.ban_label)
        layout.addStretch(1)
        self.queue_hint = QPushButton("Open League Client")
        self.queue_hint.setObjectName("primaryButton")
        self.queue_hint.setAccessibleName("Open League Client")
        self.queue_hint.setEnabled(False)
        self.queue_hint.setToolTip("Queue actions are controlled by the League client.")
        layout.addWidget(self.queue_hint, alignment=Qt.AlignmentFlag.AlignLeft)
        return panel

    def _build_active_preset_panel(self) -> QWidget:
        panel = Panel("activePresetPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)
        layout.addWidget(_label("ACTIVE PRESET", "eyebrow"))
        self.active_preset_title = _label("Preset 1", "heroTitle")
        self.active_champion_label = _label("Garen", "cardTitle")
        self.active_loadout_label = _label("Flash  +  Ignite", secondary=True)
        self.active_rune_label = _label("Rune page not selected", secondary=True)
        self.active_skin_label = _label("Skin not selected", secondary=True)
        layout.addWidget(self.active_preset_title)
        layout.addWidget(self.active_champion_label)
        layout.addSpacing(4)
        layout.addWidget(self.active_loadout_label)
        layout.addWidget(self.active_rune_label)
        layout.addWidget(self.active_skin_label)
        layout.addStretch(1)
        edit = QPushButton("Edit presets")
        self.edit_presets_button = edit
        edit.setObjectName("secondaryButton")
        edit.setAccessibleName("Edit presets")
        edit.clicked.connect(partial(self._show_page, "presets"))
        layout.addWidget(edit, alignment=Qt.AlignmentFlag.AlignLeft)
        return panel

    def _build_home_automation_panel(self) -> QWidget:
        panel = Panel("automationSummary")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)
        layout.addWidget(_label("AUTOMATION", "eyebrow"))
        self.automation_summary = _label("5 controls enabled", "cardTitle")
        self.automation_summary.setWordWrap(True)
        layout.addWidget(self.automation_summary)
        self.automation_summary_detail = _label("Open Automation to change behavior.", secondary=True)
        self.automation_summary_detail.setWordWrap(True)
        layout.addWidget(self.automation_summary_detail)
        layout.addStretch(1)
        open_page = QPushButton("Configure automation")
        open_page.setObjectName("secondaryButton")
        open_page.setAccessibleName("Configure automation")
        open_page.clicked.connect(partial(self._show_page, "automation"))
        layout.addWidget(open_page)
        return panel

    def _build_quick_access_panel(self) -> QWidget:
        panel = Panel("quickAccessPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        layout.addWidget(_label("QUICK ACCESS", "eyebrow"))
        row = QHBoxLayout()
        self.quick_access_labels: list[QLabel] = []
        for key in ("opgg", "deeplol", "dpm", "leagueofgraphs", "porofessor"):
            item = _label(STATS_SITE_LABELS.get(key, key), "quickAccessItem")
            item.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.quick_access_labels.append(item)
            row.addWidget(item, 1)
        open_button = QPushButton("Open configured")
        open_button.setObjectName("secondaryButton")
        open_button.setAccessibleName("Open configured stats website")
        open_button.clicked.connect(self.stats_requested.emit)
        row.addWidget(open_button)
        layout.addLayout(row)
        return panel

    def _build_activity_panel(self) -> QWidget:
        panel = Panel("activityPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(8)
        heading = QHBoxLayout()
        heading.addWidget(_label("RECENT ACTIVITY", "sectionTitle"))
        heading.addStretch()
        view_all = QPushButton("View full history")
        view_all.setObjectName("linkButton")
        view_all.clicked.connect(self.history_requested.emit)
        heading.addWidget(view_all)
        layout.addLayout(heading)
        self.activity_layout = QVBoxLayout()
        self.activity_layout.setSpacing(7)
        layout.addLayout(self.activity_layout)
        return panel

    def _build_shortcuts_panel(self) -> QWidget:
        panel = Panel("shortcutsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(8)
        heading = QHBoxLayout()
        heading.addWidget(_label("SHORTCUTS", "sectionTitle"))
        heading.addStretch()
        edit = QPushButton("Edit")
        edit.setObjectName("linkButton")
        edit.clicked.connect(self.settings_requested.emit)
        heading.addWidget(edit)
        layout.addLayout(heading)
        for label, shortcut in (("Show / hide OTP LOL", "Alt + C"), ("Open stats website", "Alt + P"), ("Start / stop queue", "League client")):
            row = QHBoxLayout()
            row.addWidget(_label(label, secondary=True))
            row.addStretch()
            row.addWidget(_label(shortcut, "shortcutKey"))
            layout.addLayout(row)
        layout.addStretch(1)
        return panel

    def _build_news_panel(self) -> QWidget:
        panel = Panel("newsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(8)
        layout.addWidget(_label("NEWS", "sectionTitle"))
        layout.addWidget(_label(f"OTP LOL v{CURRENT_VERSION}", "cardTitle"))
        layout.addWidget(_label("Local runtime and release checks are enabled.", secondary=True))
        layout.addStretch(1)
        updates = QPushButton("Check for updates")
        updates.setObjectName("linkButton")
        updates.clicked.connect(lambda: self.statusBar().showMessage("Update checks run in the background."))
        layout.addWidget(updates)
        return panel

    def _build_presets_page(self) -> QWidget:
        page = self._page_container()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        layout.addWidget(_label("Champion Select Presets", "pageSectionTitle"))
        layout.addWidget(_label("Three ordered presets control pick priority, spells, runes, and skins.", secondary=True))
        grid = QGridLayout()
        grid.setSpacing(14)
        for index, slot_key in enumerate(PICK_SLOT_ORDER):
            row = PresetRow(slot_key)
            row.skin_cycle_requested.connect(self.skin_cycle_requested.emit)
            self.preset_rows[slot_key] = row
            grid.addWidget(row, 0, index)
        self.preset_grid = grid
        layout.addLayout(grid)
        action_row = QHBoxLayout()
        action_row.addStretch()
        edit = QPushButton("Open full preset editor")
        edit.setObjectName("primaryButton")
        edit.setAccessibleName("Open full preset editor")
        edit.clicked.connect(self.settings_requested.emit)
        action_row.addWidget(edit)
        layout.addLayout(action_row)
        layout.addStretch(1)
        return page

    def _build_automation_page(self) -> QWidget:
        page = self._page_container()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        layout.addWidget(_label("Automation", "pageSectionTitle"))
        layout.addWidget(_label("Choose what OTP LOL is allowed to do while you play.", secondary=True))
        grid = QGridLayout()
        grid.setSpacing(12)
        definitions = (
            ("auto_accept_enabled", "Auto Accept", "Accept ready checks automatically when a match is found."),
            ("presets_enabled", "Use Presets", "Apply the selected champion, spells, runes, and skin."),
            ("auto_ban_enabled", "Auto Ban", "Ban the configured champion during champion select."),
            ("auto_summoners_enabled", "Apply Summoner Spells", "Apply the configured spell pair after hover confirmation."),
            ("auto_play_again_enabled", "Auto Play Again", "Return to the lobby after a completed game."),
            ("auto_hide_on_connect", "Hide on Connect", "Keep the companion out of the way when League is ready."),
            ("close_app_on_lol_exit", "Close with League", "Close OTP LOL when the League client exits."),
        )
        for index, (key, title, description) in enumerate(definitions):
            card = AutomationCard(key, title, description, False)
            card.toggled.connect(self._forward_setting)
            self.automation_cards[key] = card
            grid.addWidget(card, index // 2, index % 2)
        layout.addLayout(grid)
        layout.addStretch(1)
        return page

    def _build_history_page(self) -> QWidget:
        page = self._page_container()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        heading = QHBoxLayout()
        heading.addWidget(_label("History", "pageSectionTitle"))
        heading.addStretch()
        refresh = QPushButton("Refresh")
        refresh.setObjectName("secondaryButton")
        refresh.clicked.connect(self._refresh_activity)
        heading.addWidget(refresh)
        open_dialog = QPushButton("Open detailed history")
        open_dialog.setObjectName("primaryButton")
        open_dialog.clicked.connect(self.history_requested.emit)
        heading.addWidget(open_dialog)
        layout.addLayout(heading)
        layout.addWidget(_label("Useful events are shown here; technical logs remain in app_debug.log.", secondary=True))
        self.history_layout = QVBoxLayout()
        self.history_layout.setSpacing(8)
        history_panel = Panel("historyListPanel")
        history_inner = QVBoxLayout(history_panel)
        history_inner.setContentsMargins(18, 18, 18, 18)
        history_inner.addLayout(self.history_layout)
        history_inner.addStretch(1)
        layout.addWidget(history_panel, 1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = self._page_container()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        layout.addWidget(_label("Settings", "pageSectionTitle"))
        layout.addWidget(_label("Keep the dashboard focused; detailed controls open in the existing editor.", secondary=True))
        grid = QGridLayout()
        grid.setSpacing(12)
        self.settings_theme_value = self._setting_panel(grid, 0, 0, "Appearance", "Dark theme", "Theme follows the saved application setting.")
        self.settings_account_value = self._setting_panel(grid, 0, 1, "League account", "Auto detect", "Riot ID and region come from the local client when available.")
        self.settings_sites_value = self._setting_panel(grid, 1, 0, "Statistics website", "OP.GG", "The configured site opens from Home and the shortcut.")
        self.settings_data_value = self._setting_panel(grid, 1, 1, "Local data", "TOML + JSON history", "Settings and useful action history stay on this machine.")
        layout.addLayout(grid)
        action = QHBoxLayout()
        action.addStretch()
        open_editor = QPushButton("Open detailed settings")
        open_editor.setObjectName("primaryButton")
        open_editor.setAccessibleName("Open detailed settings")
        open_editor.clicked.connect(self.settings_requested.emit)
        action.addWidget(open_editor)
        layout.addLayout(action)
        layout.addStretch(1)
        return page

    @staticmethod
    def _setting_panel(grid: QGridLayout, row: int, column: int, title: str, value: str, detail: str) -> QLabel:
        panel = Panel("settingSummary")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 15, 16, 15)
        layout.addWidget(_label(title, "eyebrow"))
        value_label = _label(value, "cardTitle")
        layout.addWidget(value_label)
        layout.addWidget(_label(detail, secondary=True))
        grid.addWidget(panel, row, column)
        return value_label

    @staticmethod
    def _page_container() -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        return page

    def _show_page(self, key: str) -> None:
        if key not in self._page_indexes:
            return
        self.page_stack.setCurrentIndex(self._page_indexes[key])
        self.page_title.setText(self._PAGE_TITLES[key])
        self.page_subtitle.setText(
            {
                "home": "A clear view of what OTP LOL is doing.",
                "presets": "Manage the ordered champion-select loadouts.",
                "automation": "Choose which actions OTP LOL can perform.",
                "history": "Useful runtime events, without technical noise.",
                "settings": "Application preferences and local data.",
            }[key]
        )
        for button_key, button in self.nav_buttons.items():
            with QSignalBlocker(button):
                button.setChecked(button_key == key)

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
            if slot_key in self.preset_rows:
                mode = get_effective_skin_mode_for_slot(slot_key, effective, overrides)
                self.preset_rows[slot_key].update_data(
                    str(slot.get("champion") or "None"), slot, mode, enabled=enabled
                )

        active_slot = PICK_SLOT_ORDER[0]
        active_slot_data = slots.get(active_slot, {}) if isinstance(slots, Mapping) else {}
        active_champion = str(active_slot_data.get("champion") or settings.get("selected_pick_1") or "None")
        self.active_preset_title.setText(PICK_SLOT_LABELS.get(active_slot, "Preset 1"))
        self.active_champion_label.setText(active_champion)
        spell_1 = str(active_slot_data.get("spell_1") or "None").replace("(None)", "None")
        spell_2 = str(active_slot_data.get("spell_2") or "None").replace("(None)", "None")
        self.active_loadout_label.setText(f"{spell_1}  +  {spell_2}")
        self.active_rune_label.setText(str(active_slot_data.get("rune_page_name") or "Rune page not selected"))
        skin_mode = get_effective_skin_mode_for_slot(active_slot, effective, overrides)
        skin_name = str(active_slot_data.get("skin_name") or "Skin not selected")
        self.active_skin_label.setText(skin_name if skin_mode == "fixed" else f"Skin mode: {skin_mode}")
        self.ban_label.setText(f"Ban: {settings.get('selected_ban') or 'None'}")

        site = str(settings.get("preferred_stats_site") or "opgg")
        self.stats_button.setText(f"Open {STATS_SITE_LABELS.get(site, 'stats')}")
        self._refresh_stats_enabled()
        riot_id = self._current_riot_id().strip()
        region = str(settings.get("auto_detected_region") or settings.get("manual_region") or "euw").upper()
        self.account_name.setText(riot_id or "No Riot ID")
        self.account_region.setText(region)
        self.account_status.setText("Connected" if self._connected else "Offline")
        self.settings_theme_value.setText("Light" if settings.get("theme") == "flatly" else "Dark")
        self.settings_account_value.setText("Auto detect" if settings.get("summoner_name_auto_detect", True) else "Manual")
        self.settings_sites_value.setText(STATS_SITE_LABELS.get(site, site))
        active_count = sum(bool(settings.get(key, False)) for key in self.automation_cards)
        self.automation_summary.setText(f"{active_count} controls enabled")
        self.automation_summary_detail.setText("All systems operational" if active_count else "Automation is disabled")
        self.apply_theme(str(settings.get("theme") or "darkly"))
        self._refresh_activity()
        self._load_champion_icons()

    def _refresh_activity(self) -> None:
        for layout in (getattr(self, "activity_layout", None), getattr(self, "history_layout", None)):
            if layout is None:
                continue
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        entries = []
        try:
            entries = [format_history_entry(entry) for entry in get_history_entries(limit=6)]
        except OSError:
            entries = []
        if not entries:
            entries = [{"time": "--:--", "level_label": "INFO", "category": "No recent activity", "message": "Runtime events will appear here."}]
        for entry in entries:
            row = QFrame()
            row.setObjectName("activityRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.addWidget(_label(str(entry.get("time") or "--:--"), "activityTime"))
            row_layout.addWidget(_label(str(entry.get("level_label") or "INFO"), "activityLevel"))
            detail = QVBoxLayout()
            detail.addWidget(_label(str(entry.get("message") or entry.get("category") or "Event"), "cardTitle"))
            detail.addWidget(_label(str(entry.get("category") or "Runtime"), secondary=True))
            row_layout.addLayout(detail, 1)
            for layout in (getattr(self, "activity_layout", None), getattr(self, "history_layout", None)):
                if layout is not None:
                    layout.addWidget(row if layout is getattr(self, "activity_layout", None) else self._clone_activity_row(entry))

    @staticmethod
    def _clone_activity_row(entry: Mapping[str, Any]) -> QFrame:
        row = QFrame()
        row.setObjectName("activityRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.addWidget(_label(str(entry.get("time") or "--:--"), "activityTime"))
        row_layout.addWidget(_label(str(entry.get("level_label") or "INFO"), "activityLevel"))
        detail = QVBoxLayout()
        detail.addWidget(_label(str(entry.get("message") or entry.get("category") or "Event"), "cardTitle"))
        detail.addWidget(_label(str(entry.get("category") or "Runtime"), secondary=True))
        row_layout.addLayout(detail, 1)
        return row

    def _load_champion_icons(self) -> None:
        if self.data_dragon is None or self.task_runner is None:
            return
        names = {
            slot_key: self.preset_rows[slot_key].champion.text()
            for slot_key in PICK_SLOT_ORDER
            if slot_key in self.preset_rows
        }
        if not names:
            return
        self._icon_generation += 1
        generation = self._icon_generation

        def load() -> dict[str, Any]:
            return {
                "generation": generation,
                "images": {
                    slot_key: pil_to_qimage(self.data_dragon.get_champion_icon(name), size=(54, 54))
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
                self.preset_rows[slot_key].icon.setPixmap(qpixmap_from_image(image))

    def _current_riot_id(self) -> str:
        if bool(self.settings.get("summoner_name_auto_detect", True)):
            return str(self.settings.get("auto_detected_riot_id") or "")
        return str(self.settings.get("manual_summoner_name") or "")

    def _refresh_stats_enabled(self) -> None:
        riot_id = self._current_riot_id().strip()
        self.stats_button.setEnabled("#" in riot_id and all(riot_id.split("#", 1)))

    @Slot(object)
    def handle_runtime_event(self, event: RuntimeEvent) -> None:
        if isinstance(event, Connected):
            self._set_connected(True)
        elif isinstance(event, Disconnected):
            self._set_connected(False)
        elif isinstance(event, StatusChanged):
            self.status_label.setText(event.message)
            self.phase_label.setText(event.category or "League client connected and ready.")
            self.statusBar().showMessage(event.message)
        elif isinstance(event, PhaseChanged):
            self.phase_label.setText(event.phase)
        elif isinstance(event, SummonerUpdated):
            self.settings["auto_detected_riot_id"] = event.riot_id or ""
            self.refresh_settings(self.settings)
        elif isinstance(event, ChampionPicked):
            self.enqueue_toast(f"Picked {event.champion}", 3000)
        elif isinstance(event, ChampionBanned):
            self.ban_label.setText(f"Ban: {event.champion}")
        elif isinstance(event, SpellsApplied):
            self.spells_label.setText(f"Spells: {event.first} + {event.second}")
            self.active_loadout_label.setText(f"{event.first}  +  {event.second}")
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
        self._connected = connected
        self.connection_chip.setText("Client connected" if connected else "Client offline")
        self.connection_chip.setProperty("connected", connected)
        self.account_status.setText("Connected" if connected else "Offline")
        if connected and self.status_label.text() == "Waiting for League client":
            self.status_label.setText("Ready for queue")
            self.phase_label.setText("League client connected and ready.")
        elif not connected:
            self.status_label.setText("Waiting for League client")
            self.phase_label.setText("Waiting for League client.")
        if connected:
            self._pulse_timer.start()
        else:
            self._pulse_timer.stop()
            self.connection_chip.setProperty("pulsing", False)
        self._repolish(self.connection_chip)

    def _pulse_connection(self) -> None:
        self._pulse_on = not self._pulse_on
        self.connection_chip.setProperty("pulsing", self._pulse_on)
        self._repolish(self.connection_chip)

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def allow_close(self) -> None:
        self._allow_close = True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            event.accept()
            return
        self.close_requested.emit()
        event.ignore()
