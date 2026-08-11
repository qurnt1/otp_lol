"""PySide6 League Companion shell and operational desktop pages.

THESIS: Show connection, active preset, automation, and health at a glance; refuse
the crowded settings wall.
OWN-WORLD: Midnight navy surfaces, coral actions, green connection state,
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

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSignalBlocker,
    QSize,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QCloseEvent, QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsOpacityEffect,
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

from src.config import (
    APP_ICON_FILES,
    APP_IMAGE_FILES,
    CURRENT_VERSION,
    HOTKEY_SITE_LABELS,
    PHASE_DISPLAY_MAP,
    PICK_SLOT_LABELS,
    PICK_SLOT_ORDER,
    STATS_SITE_LABELS,
    WEBSITE_LOGO_FILES,
    resource_path,
)
from src.core.events import (
    ChampionBanned,
    ChampionPicked,
    Connected,
    Disconnected,
    PhaseChanged,
    PlayAgainSucceeded,
    ProfileUpdated,
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


_NAV_ICON_PATHS = {key: APP_ICON_FILES[key] for key in ("home", "presets", "automation", "history", "settings")}
_VISUAL_ICON_PATHS = {
    "champion": APP_ICON_FILES["champion_select"],
    "spells": APP_ICON_FILES["spells"],
    "runes": APP_ICON_FILES["runes"],
    "skin": APP_ICON_FILES["skin"],
    "rank": APP_ICON_FILES["rank_placeholder"],
    "activity": APP_ICON_FILES["activity"],
    "shortcuts": APP_ICON_FILES["shortcuts"],
    "news": APP_ICON_FILES["news"],
}

_LOCAL_NEWS_HIGHLIGHTS = (
    "Home dashboard with live preset and automation state.",
    "Real champion, spell, rune, skin, rank, and activity icons.",
    "Improved League client lifecycle feedback and shortcuts.",
)


def _resource_icon(relative_path: str, fallback: str | None = None) -> QIcon:
    icon = QIcon(resource_path(relative_path))
    if icon.isNull() and fallback:
        icon = QIcon(resource_path(fallback))
    return icon


def _icon_label(size: int, object_name: str = "assetIcon") -> QLabel:
    label = QLabel()
    label.setObjectName(object_name)
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setScaledContents(True)
    return label


def _set_icon_label(label: QLabel, icon: QIcon, size: int) -> None:
    label.setPixmap(icon.pixmap(QSize(size, size)))


def _set_qimage_label(label: QLabel, image: Any, size: int, fallback_key: str) -> None:
    pixmap = qpixmap_from_image(image)
    if not pixmap.isNull():
        scaled = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        label.setPixmap(scaled)
        return
    fallback = _resource_icon(_VISUAL_ICON_PATHS[fallback_key], APP_IMAGE_FILES["icon_webp"])
    _set_icon_label(label, fallback, size)


class ToggleSwitch(QCheckBox):
    """Small accessible switch matching the Home reference controls."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(36, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = self.rect().adjusted(1, 3, -1, -3)
        painter.setPen(QColor("#f1cf69" if self.isChecked() else "#4b6275"))
        painter.setBrush(QColor("#d0a843" if self.isChecked() else "#273746"))
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        knob_x = track.right() - 15 if self.isChecked() else track.left() + 3
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#fffaf0" if self.isChecked() else "#b8c2cc"))
        painter.drawEllipse(knob_x, track.top() + 3, 12, 12)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor("#ff9c8d"))
            painter.drawRoundedRect(self.rect().adjusted(0, 1, -1, -2), 5, 5)


class Panel(QFrame):
    """Reusable bordered surface for the shell pages."""

    def __init__(self, object_name: str = "panel") -> None:
        super().__init__()
        self.setObjectName(object_name)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)


class AutomationCard(Panel):
    toggled = Signal(str, bool)

    def __init__(
        self,
        key: str,
        title: str,
        description: str,
        enabled: bool,
        *,
        compact: bool = False,
    ) -> None:
        super().__init__("automationSwitchRow" if compact else "automationCard")
        self.key = key
        layout = QHBoxLayout(self) if compact else QVBoxLayout(self)
        if compact:
            layout.setContentsMargins(10, 7, 10, 7)
        else:
            layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8 if compact else 7)
        title_label = _label(title, "cardTitle")
        self.switch = ToggleSwitch()
        self.switch.setAccessibleName("Pick presets" if key == "presets_enabled" else title)
        self.switch.setToolTip(description)
        self.switch.setChecked(enabled)
        self.switch.toggled.connect(partial(self.toggled.emit, key))
        if compact:
            layout.addWidget(title_label, 1)
            layout.addWidget(self.switch)
            self.setToolTip(description)
        else:
            header = QHBoxLayout()
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
        _set_icon_label(self.icon, _resource_icon(_VISUAL_ICON_PATHS["champion"]), 54)
        self.champion = _label("None", "cardTitle")
        self.champion.setAccessibleName(f"{PICK_SLOT_LABELS[slot_key]} champion")
        identity.addWidget(self.icon)
        identity.addWidget(self.champion)
        identity.addStretch()
        layout.addLayout(identity)

        self.visuals = QHBoxLayout()
        self.visuals.setSpacing(6)
        self.spell_icon_labels = [_icon_label(28), _icon_label(28)]
        self.rune_icon_label = _icon_label(28)
        self.skin_icon_label = _icon_label(40)
        for icon_label, fallback_key in (
            (self.spell_icon_labels[0], "spells"),
            (self.spell_icon_labels[1], "spells"),
            (self.rune_icon_label, "runes"),
            (self.skin_icon_label, "skin"),
        ):
            _set_icon_label(icon_label, _resource_icon(_VISUAL_ICON_PATHS[fallback_key]), icon_label.width())
            self.visuals.addWidget(icon_label)
        self.visuals.addStretch()
        layout.addLayout(self.visuals)

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
    riot_client_requested = Signal()
    stats_requested = Signal()
    changelog_requested = Signal()
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
        self.home_automation_cards: dict[str, AutomationCard] = {}
        self.preset_rows: dict[str, PresetRow] = {}
        self.nav_buttons: dict[str, QPushButton] = {}
        self._page_indexes: dict[str, int] = {}
        self._toast_queue: deque[tuple[str, int]] = deque()
        self._toast_active = False
        self._allow_close = False
        self._icon_generation = 0
        self._profile_generation = 0
        self._rank_icon_generation = 0
        self._rank_icon_tier: str | None = None
        self._profile_icon_id: int | None = None
        self._summoner_level: int | None = None
        self._ranked_entries: tuple[Any, ...] = ()
        self._connected = False
        self._activity_generation = 0
        self._activity_icon_labels: list[QLabel] = []
        self._history_icon_labels: list[QLabel] = []
        self._connection_pulse: QPropertyAnimation | None = None
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

        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand_logo = _icon_label(38, "brandLogo")
        _set_icon_label(brand_logo, QIcon(resource_path(APP_IMAGE_FILES["logo_svg"])), 38)
        brand.addWidget(brand_logo)
        brand_copy = QVBoxLayout()
        brand_copy.setSpacing(2)
        brand_copy.addWidget(_label("OTP LOL", "brandName"))
        brand_copy.addWidget(_label(f"v{CURRENT_VERSION}", "brandVersion", secondary=True))
        brand.addLayout(brand_copy)
        layout.addLayout(brand)
        layout.addSpacing(22)

        for key, label in self._PAGE_TITLES.items():
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setIcon(_resource_icon(_NAV_ICON_PATHS[key], APP_IMAGE_FILES["icon_webp"]))
            button.setIconSize(QSize(18, 18))
            button.setCheckable(True)
            button.setAccessibleName(f"Open {label} page")
            button.clicked.connect(partial(self._navigate_from_sidebar, key))
            self.nav_buttons[key] = button
            layout.addWidget(button)
        layout.addStretch(1)

        account = Panel("accountPanel")
        account_layout = QVBoxLayout(account)
        account_layout.setContentsMargins(12, 12, 12, 12)
        account_identity = QHBoxLayout()
        self.account_avatar = _icon_label(42, "accountAvatar")
        _set_icon_label(
            self.account_avatar,
            _resource_icon(_VISUAL_ICON_PATHS["champion"], APP_IMAGE_FILES["icon_webp"]),
            42,
        )
        account_identity.addWidget(self.account_avatar)
        account_text = QVBoxLayout()
        self.account_name = _label("No Riot ID", "accountName")
        self.account_region = _label("Client offline", secondary=True)
        self.account_status = _label("Offline", "accountStatus")
        account_text.addWidget(self.account_name)
        account_text.addWidget(self.account_region)
        account_text.addWidget(self.account_status)
        account_identity.addLayout(account_text, 1)
        account_layout.addLayout(account_identity)
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

        rank_panel = Panel("rankPanel")
        rank_panel.setFixedHeight(56)
        rank_layout = QHBoxLayout(rank_panel)
        rank_layout.setContentsMargins(10, 8, 10, 8)
        self.rank_icon = _icon_label(38)
        _set_icon_label(self.rank_icon, _resource_icon(_VISUAL_ICON_PATHS["rank"]), 38)
        rank_layout.addWidget(self.rank_icon)
        rank_text = QVBoxLayout()
        self.rank_title = _label("Rank unavailable", "cardTitle")
        self.rank_detail = _label("Connect League client to refresh", secondary=True)
        rank_text.addWidget(self.rank_title)
        rank_text.addWidget(self.rank_detail)
        rank_layout.addLayout(rank_text)
        layout.addWidget(rank_panel)

        self.connection_panel = QFrame()
        self.connection_panel.setObjectName("connectionPanel")
        self.connection_panel.setFixedHeight(56)
        connection_layout = QHBoxLayout(self.connection_panel)
        connection_layout.setContentsMargins(10, 8, 12, 8)
        connection_layout.setSpacing(8)
        self.connection_dot = QLabel()
        self.connection_dot.setObjectName("connectionDot")
        self.connection_dot.setFixedSize(10, 10)
        self.connection_dot.setProperty("connected", False)
        connection_layout.addWidget(self.connection_dot)
        self.connection_chip = _label("Client offline", "connectionChip")
        self.connection_chip.setProperty("connected", False)
        self.connection_chip.setFixedHeight(40)
        self.connection_chip.setAccessibleName("League client connection status")
        connection_layout.addWidget(self.connection_chip)
        layout.addWidget(self.connection_panel)
        self._connection_opacity = QGraphicsOpacityEffect(self.connection_dot)
        self.connection_dot.setGraphicsEffect(self._connection_opacity)
        self._connection_pulse = QPropertyAnimation(self._connection_opacity, b"opacity", self)
        self._connection_pulse.setDuration(1400)
        self._connection_pulse.setStartValue(1.0)
        self._connection_pulse.setKeyValueAt(0.5, 0.35)
        self._connection_pulse.setEndValue(1.0)
        self._connection_pulse.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._connection_pulse.setLoopCount(-1)
        self.riot_client_button = QPushButton("Open League Client")
        self.riot_client_button.setObjectName("riotClientButton")
        self.riot_client_button.setIcon(QIcon(resource_path(APP_IMAGE_FILES["league_client_logo"])))
        self.riot_client_button.setIconSize(QSize(24, 24))
        self.riot_client_button.setFixedHeight(56)
        self.riot_client_button.setAccessibleName("Open League Client")
        self.riot_client_button.setToolTip("Launch League of Legends")
        self.riot_client_button.clicked.connect(self.riot_client_requested.emit)
        layout.addWidget(self.riot_client_button)
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
        self.queue_hint.setIcon(QIcon(resource_path(APP_IMAGE_FILES["league_client_logo"])))
        self.queue_hint.setIconSize(QSize(24, 24))
        self.queue_hint.setAccessibleName("Open League Client")
        self.queue_hint.clicked.connect(self.riot_client_requested.emit)
        self.queue_hint.setToolTip("Launch League of Legends to continue.")
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
        self.active_ban_label = _label("Ban  None", secondary=True)
        layout.addWidget(self.active_preset_title)
        champion_identity = QHBoxLayout()
        self.active_champion_icon = _icon_label(42)
        _set_icon_label(self.active_champion_icon, _resource_icon(_VISUAL_ICON_PATHS["champion"]), 42)
        champion_identity.addWidget(self.active_champion_icon)
        champion_identity.addWidget(self.active_champion_label)
        champion_identity.addStretch()
        layout.addLayout(champion_identity)
        asset_details = QGridLayout()
        asset_details.setHorizontalSpacing(10)
        asset_details.setVerticalSpacing(7)
        self.active_spell_icons = [_icon_label(28), _icon_label(28)]
        self.active_rune_icon = _icon_label(30)
        self.active_skin_icon = _icon_label(42)
        self.active_ban_icon = _icon_label(30)
        for icon_label, fallback_key in (
            (self.active_spell_icons[0], "spells"),
            (self.active_spell_icons[1], "spells"),
            (self.active_rune_icon, "runes"),
            (self.active_skin_icon, "skin"),
            (self.active_ban_icon, "champion"),
        ):
            _set_icon_label(icon_label, _resource_icon(_VISUAL_ICON_PATHS[fallback_key]), icon_label.width())
        spells_visual = QHBoxLayout()
        spells_visual.setSpacing(5)
        for icon_label in self.active_spell_icons:
            spells_visual.addWidget(icon_label)
        asset_details.addLayout(spells_visual, 0, 0)
        asset_details.addWidget(self.active_loadout_label, 0, 1)
        asset_details.addWidget(self.active_rune_icon, 1, 0)
        asset_details.addWidget(self.active_rune_label, 1, 1)
        asset_details.addWidget(self.active_skin_icon, 2, 0)
        asset_details.addWidget(self.active_skin_label, 2, 1)
        asset_details.addWidget(self.active_ban_icon, 3, 0)
        asset_details.addWidget(self.active_ban_label, 3, 1)
        asset_details.setColumnStretch(1, 1)
        layout.addLayout(asset_details)
        layout.addStretch(1)
        edit = QPushButton("Edit presets")
        self.edit_presets_button = edit
        edit.setObjectName("secondaryButton")
        edit.setIcon(_resource_icon(APP_ICON_FILES["presets"]))
        edit.setIconSize(QSize(16, 16))
        edit.setAccessibleName("Edit presets")
        edit.clicked.connect(partial(self._show_page, "presets"))
        layout.addWidget(edit, alignment=Qt.AlignmentFlag.AlignLeft)
        return panel

    def _build_home_automation_panel(self) -> QWidget:
        panel = Panel("automationSummary")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(6)
        layout.addWidget(_label("AUTOMATION", "eyebrow"))
        self.automation_summary = _label("Automation controls", "cardTitle")
        layout.addWidget(self.automation_summary)
        self.automation_summary_detail = _label("Changes apply to the next champion select.", secondary=True)
        self.automation_summary_detail.setWordWrap(True)
        layout.addWidget(self.automation_summary_detail)
        definitions = (
            ("auto_accept_enabled", "Auto Accept", "Accept ready checks automatically."),
            ("auto_pick_enabled", "Auto Pick", "Pick the active preset champion."),
            ("auto_ban_enabled", "Auto Ban", "Ban the configured champion."),
            ("auto_summoners_enabled", "Apply Summoner Spells", "Apply the active spell pair."),
            ("rune_auto_apply", "Apply Runes", "Apply the active rune page."),
            ("auto_play_again_enabled", "Auto Play Again", "Return to the lobby after a game."),
        )
        for key, title, description in definitions:
            card = AutomationCard(key, title, description, False, compact=True)
            card.toggled.connect(self._forward_home_setting)
            self.home_automation_cards[key] = card
            layout.addWidget(card)
        open_page = QPushButton("Configure automation")
        open_page.setObjectName("secondaryButton")
        open_page.setAccessibleName("Configure automation")
        open_page.clicked.connect(partial(self._show_page, "automation"))
        layout.addWidget(open_page, alignment=Qt.AlignmentFlag.AlignTop)
        return panel

    def _build_quick_access_panel(self) -> QWidget:
        panel = Panel("quickAccessPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        layout.addWidget(_label("QUICK ACCESS", "eyebrow"))
        row = QHBoxLayout()
        self.quick_access_labels: list[QLabel] = []
        self.quick_access_icons: dict[str, QLabel] = {}
        for key in ("opgg", "deeplol", "dpm", "leagueofgraphs", "porofessor"):
            item = QFrame()
            item.setObjectName("quickAccessItem")
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(8, 7, 8, 7)
            item_layout.setSpacing(7)
            icon = _icon_label(28)
            logo_path = WEBSITE_LOGO_FILES.get(key)
            if logo_path:
                _set_icon_label(icon, QIcon(resource_path(logo_path)), 28)
            item_layout.addWidget(icon)
            label = _label(STATS_SITE_LABELS.get(key, key), "quickAccessLabel")
            item_layout.addWidget(label, 1)
            self.quick_access_icons[key] = icon
            self.quick_access_labels.append(label)
            row.addWidget(item, 1)
        open_button = QPushButton("Open selected website")
        open_button.setObjectName("secondaryButton")
        open_button.setIcon(_resource_icon(APP_ICON_FILES["external_link"]))
        open_button.setIconSize(QSize(16, 16))
        open_button.setAccessibleName("Open selected stats website")
        self.open_stats_button = open_button
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
        view_all.setIcon(_resource_icon(APP_ICON_FILES["history"]))
        view_all.setIconSize(QSize(16, 16))
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
        for label, shortcut, icon_key in (
            ("Show / hide OTP LOL", "Alt + C", "shortcuts"),
            ("Open stats website", "Alt + P", "activity"),
            ("Start / stop queue", "League client", "champion"),
        ):
            row = QHBoxLayout()
            icon = _icon_label(20)
            _set_icon_label(icon, _resource_icon(_VISUAL_ICON_PATHS[icon_key]), 20)
            row.addWidget(icon)
            text_label = _label(label, secondary=True)
            if label == "Open stats website":
                self.shortcut_site_label = text_label
            row.addWidget(text_label)
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
        heading = QHBoxLayout()
        news_icon = _icon_label(20)
        _set_icon_label(news_icon, _resource_icon(_VISUAL_ICON_PATHS["news"]), 20)
        heading.addWidget(news_icon)
        heading.addWidget(_label("NEWS", "sectionTitle"))
        heading.addStretch()
        layout.addLayout(heading)
        self.news_version_label = _label(f"OTP LOL v{CURRENT_VERSION}", "cardTitle")
        self.news_highlights_label = _label("\n".join(f"• {item}" for item in _LOCAL_NEWS_HIGHLIGHTS), secondary=True)
        self.news_highlights_label.setWordWrap(True)
        layout.addWidget(self.news_version_label)
        layout.addWidget(self.news_highlights_label)
        layout.addStretch(1)
        updates = QPushButton("View Changelog")
        updates.setObjectName("linkButton")
        updates.setAccessibleName("View changelog")
        updates.clicked.connect(self.changelog_requested.emit)
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

    def _navigate_from_sidebar(self, key: str) -> None:
        if key == "settings":
            self._show_page(key)
            self.settings_requested.emit()
            return
        self._show_page(key)

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

    def _forward_home_setting(self, key: str, enabled: bool) -> None:
        if key != "rune_auto_apply":
            self.setting_changed.emit(key, enabled)
            return
        slots = dict(self.settings.get("pick_slots") or {})
        active_slot = dict(slots.get(PICK_SLOT_ORDER[0]) or {})
        active_slot["rune_auto_apply"] = enabled
        slots[PICK_SLOT_ORDER[0]] = active_slot
        self.setting_changed.emit("pick_slots", slots)

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
        for key, card in self.home_automation_cards.items():
            if key == "rune_auto_apply":
                checked = bool(active_slot_data.get(key, True))
            else:
                checked = bool(settings.get(key, False))
            card.set_checked(checked)
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
        selected_ban = str(effective.get("selected_ban") or settings.get("selected_ban") or "None")
        self.active_ban_label.setText(f"Ban  {selected_ban}")
        self.ban_label.setText(f"Ban: {selected_ban}")

        site = str(settings.get("preferred_stats_site") or "opgg")
        self.open_stats_button.setText("Open selected website")
        self.open_stats_button.setToolTip(f"Open {STATS_SITE_LABELS.get(site, site)}")
        hotkey_site = str(settings.get("preferred_hotkey_site") or "porofessor")
        self.shortcut_site_label.setText(f"Open {HOTKEY_SITE_LABELS.get(hotkey_site, hotkey_site)}")
        self._refresh_stats_enabled()
        riot_id = self._current_riot_id().strip()
        region = str(settings.get("auto_detected_region") or settings.get("manual_region") or "euw").upper()
        self.account_name.setText(riot_id or "No Riot ID")
        self.account_region.setText(region)
        self.account_status.setText("Connected" if self._connected else "Offline")
        self._refresh_profile_summary()
        self.settings_theme_value.setText("Light" if settings.get("theme") == "flatly" else "Dark")
        self.settings_account_value.setText("Auto detect" if settings.get("summoner_name_auto_detect", True) else "Manual")
        self.settings_sites_value.setText(STATS_SITE_LABELS.get(site, site))
        active_count = sum(
            bool(active_slot_data.get(key, True) if key == "rune_auto_apply" else settings.get(key, False))
            for key in self.home_automation_cards
        )
        self.automation_summary.setText(f"{active_count} controls enabled")
        self.automation_summary_detail.setText("All systems operational" if active_count else "Automation is disabled")
        self.apply_theme(str(settings.get("theme") or "darkly"))
        self._refresh_activity()
        self._load_champion_icons()
        self._load_profile_icon()

    def _refresh_profile_summary(self) -> None:
        ranked_entry = next(
            (
                entry
                for entry in self._ranked_entries
                if str(getattr(entry, "queue_type", "")).upper() in {"RANKED_SOLO_5X5", "RANKED_FLEX_SR"}
            ),
            None,
        )
        if ranked_entry is None:
            self.rank_title.setText("Rank unavailable")
            level = getattr(self, "_summoner_level", None)
            self.rank_detail.setText(
                f"Level {level} · Ranked stats unavailable" if level else "Connect League client to refresh"
            )
            self._reset_rank_icon()
            return
        queue_label = (
            "Ranked Solo/Duo"
            if str(getattr(ranked_entry, "queue_type", "")).upper() == "RANKED_SOLO_5X5"
            else "Ranked Flex"
        )
        tier = str(getattr(ranked_entry, "tier", "") or "").title()
        division = str(getattr(ranked_entry, "division", "") or "")
        rank_parts = [part for part in (queue_label, tier, division) if part]
        self.rank_title.setText(" ".join(rank_parts) if len(rank_parts) > 1 else "Rank unavailable")
        detail_parts = []
        league_points = getattr(ranked_entry, "league_points", None)
        if league_points is not None:
            detail_parts.append(f"{league_points} LP")
        wins = getattr(ranked_entry, "wins", None)
        losses = getattr(ranked_entry, "losses", None)
        if wins is not None and losses is not None:
            detail_parts.append(f"{wins}W {losses}L")
        self.rank_detail.setText(" · ".join(detail_parts) or "Ranked stats available")
        self._load_rank_icon(tier)

    def _reset_rank_icon(self) -> None:
        self._rank_icon_generation += 1
        self._rank_icon_tier = None
        _set_icon_label(self.rank_icon, _resource_icon(_VISUAL_ICON_PATHS["rank"]), 38)

    def _load_rank_icon(self, tier: str) -> None:
        tier_key = str(tier or "").strip().lower()
        if not tier_key or self._rank_icon_tier == tier_key:
            return
        self._rank_icon_tier = tier_key
        get_rank_icon = getattr(self.data_dragon, "get_rank_icon", None)
        if self.task_runner is None or not callable(get_rank_icon):
            return
        self._rank_icon_generation += 1
        generation = self._rank_icon_generation

        def load() -> dict[str, Any]:
            return {
                "generation": generation,
                "image": pil_to_qimage(get_rank_icon(tier_key), size=(38, 38)),
            }

        self.task_runner.submit(load, guarded_callback(self, "_apply_rank_icon"))

    def _apply_rank_icon(self, payload: Mapping[str, Any]) -> None:
        if payload.get("generation") != self._rank_icon_generation:
            return
        _set_qimage_label(self.rank_icon, payload.get("image"), 38, "rank")

    def _load_profile_icon(self) -> None:
        if self.data_dragon is None or self.task_runner is None or not self._profile_icon_id:
            return
        get_profile_icon = getattr(self.data_dragon, "get_profile_icon", None)
        if not callable(get_profile_icon):
            return
        self._profile_generation += 1
        generation = self._profile_generation
        profile_icon_id = self._profile_icon_id

        def load() -> dict[str, Any]:
            return {
                "generation": generation,
                "image": pil_to_qimage(get_profile_icon(profile_icon_id), size=(42, 42)),
            }

        self.task_runner.submit(load, guarded_callback(self, "_apply_profile_icon"))

    def _apply_profile_icon(self, payload: Mapping[str, Any]) -> None:
        if payload.get("generation") != self._profile_generation:
            return
        _set_qimage_label(self.account_avatar, payload.get("image"), 42, "champion")

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
        self._activity_generation += 1
        generation = self._activity_generation
        activity_labels: list[QLabel] = []
        history_labels: list[QLabel] = []
        for entry in entries:
            row, icon = self._build_activity_row(entry, compact=True)
            activity_labels.append(icon)
            if self.activity_layout is not None:
                self.activity_layout.addWidget(row)
            history_row, history_icon = self._build_activity_row(entry)
            history_labels.append(history_icon)
            if self.history_layout is not None:
                self.history_layout.addWidget(history_row)
        self._activity_icon_labels = activity_labels
        self._history_icon_labels = history_labels
        self._load_activity_images(entries, activity_labels, history_labels, generation)

    def _build_activity_row(self, entry: Mapping[str, Any], *, compact: bool = False) -> tuple[QFrame, QLabel]:
        row = QFrame()
        row.setObjectName("activityRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 6 if compact else 8, 8, 6 if compact else 8)
        activity_icon = _icon_label(28 if compact else 30)
        icon_size = activity_icon.width()
        _set_icon_label(activity_icon, _resource_icon(_VISUAL_ICON_PATHS[self._activity_icon_key(entry)]), icon_size)
        row_layout.addWidget(activity_icon)
        row_layout.addWidget(_label(str(entry.get("time") or "--:--"), "activityTime"))
        activity_level = _label(self._activity_status_label(entry), "activityLevel")
        activity_level.setProperty("level", str(entry.get("level") or "info"))
        activity_level.setProperty("action", self._activity_action(entry))
        self._repolish(activity_level)
        row_layout.addWidget(activity_level)
        detail = QVBoxLayout()
        message = str(entry.get("message") or entry.get("category") or "Event")
        if compact and len(message) > 52:
            message = f"{message[:49].rstrip()}..."
        detail.addWidget(_label(message, "cardTitle"))
        detail.addWidget(_label(str(entry.get("category") or "Runtime"), secondary=True))
        row_layout.addLayout(detail, 1)
        return row, activity_icon

    def _load_activity_images(
        self,
        entries: list[Mapping[str, Any]],
        activity_labels: list[QLabel],
        history_labels: list[QLabel],
        generation: int,
    ) -> None:
        if self.data_dragon is None or self.task_runner is None:
            return

        def load() -> dict[str, Any]:
            return {
                "generation": generation,
                "images": [self._activity_image(entry) for entry in entries],
            }

        self.task_runner.submit(
            load,
            lambda payload: self._apply_activity_images(payload, entries, activity_labels, history_labels),
        )

    def _apply_activity_images(
        self,
        payload: Mapping[str, Any],
        entries: list[Mapping[str, Any]],
        activity_labels: list[QLabel],
        history_labels: list[QLabel],
    ) -> None:
        if payload.get("generation") != self._activity_generation:
            return
        images = payload.get("images", [])
        if not isinstance(images, list):
            return
        for labels in (activity_labels, history_labels):
            for entry, label, image in zip(entries, labels, images, strict=False):
                _set_qimage_label(label, image, label.width(), self._activity_icon_key(entry))

    def _activity_image(self, entry: Mapping[str, Any]) -> Any:
        details = entry.get("details", {})
        if not isinstance(details, Mapping):
            details = {}
        action = self._activity_action(entry)
        if action in {"pick", "ban", "hover"}:
            champion = str(details.get("champion") or details.get("champion_name") or "")
            getter = getattr(self.data_dragon, "get_champion_icon", None)
            if champion and callable(getter):
                return pil_to_qimage(getter(champion), size=(30, 30))
        if action == "skin":
            champion = str(details.get("champion") or "")
            get_url = getattr(self.data_dragon, "get_skin_preview_url", None)
            get_image = getattr(self.data_dragon, "get_remote_image", None)
            if champion and callable(get_url) and callable(get_image):
                skin_url = get_url(
                    champion,
                    skin_name=details.get("skin_name"),
                    skin_id=details.get("skin_id"),
                    skin_num=details.get("skin_num"),
                )
                if skin_url:
                    return pil_to_qimage(
                        get_image(skin_url, cache_key=f"activity_skin_{details.get('skin_id')}_{details.get('skin_num')}"),
                        size=(30, 30),
                    )
        if action == "spells":
            spell = str(details.get("spell_1") or details.get("spell_2") or "")
            getter = getattr(self.data_dragon, "get_summoner_icon", None)
            if spell and callable(getter):
                return pil_to_qimage(getter(spell), size=(30, 30))
        if action == "runes":
            keystone = str(details.get("rune_keystone_path") or "")
            sub_style = str(details.get("rune_sub_style_icon_path") or "")
            composer = getattr(self.data_dragon, "compose_rune_button_icon", None)
            if keystone and callable(composer):
                return pil_to_qimage(composer(keystone, sub_style, size=30), size=(30, 30))
        return None

    @staticmethod
    def _activity_icon_key(entry: Mapping[str, Any]) -> str:
        content = f"{entry.get('category', '')} {entry.get('message', '')}".lower()
        if "spell" in content or "summoner" in content:
            return "spells"
        if "rune" in content:
            return "runes"
        if "skin" in content:
            return "skin"
        if "champion" in content or "pick" in content or "ban" in content:
            return "champion"
        if "connect" in content or "client" in content:
            return "rank"
        return "activity"

    @staticmethod
    def _activity_action(entry: Mapping[str, Any]) -> str:
        action = str(entry.get("action") or entry.get("type") or "").strip().lower()
        if action == "set" and str(entry.get("category") or "").lower() in {"summs", "spells"}:
            return "spells"
        return action

    @classmethod
    def _activity_status_label(cls, entry: Mapping[str, Any]) -> str:
        labels = {
            "ban": "BAN",
            "pick": "PICK",
            "skin": "SKIN",
            "spells": "SUMMS",
            "runes": "RUNES",
        }
        action = cls._activity_action(entry)
        return labels.get(action, str(entry.get("level_label") or "INFO").upper())

    def _load_champion_icons(self) -> None:
        if self.data_dragon is None or self.task_runner is None:
            return
        effective = build_effective_profile_config(self.settings)
        slots = effective.get("pick_slots", {})
        if not isinstance(slots, Mapping):
            return
        self._icon_generation += 1
        generation = self._icon_generation
        selected_ban = str(effective.get("selected_ban") or self.settings.get("selected_ban") or "")

        def load() -> dict[str, Any]:
            assets: dict[str, dict[str, Any]] = {}
            overrides = build_main_skin_overrides(self.settings)
            for slot_key in PICK_SLOT_ORDER:
                slot = slots.get(slot_key, {})
                if not isinstance(slot, Mapping):
                    continue
                champion = str(slot.get("champion") or "")
                if not champion or champion == "(None)":
                    continue
                spell_images = {
                    number: pil_to_qimage(
                        self.data_dragon.get_summoner_icon(str(slot.get(f"spell_{number}") or "")),
                        size=(28, 28),
                    )
                    for number in (1, 2)
                }
                rune_image = None
                keystone = str(slot.get("rune_keystone_path") or "")
                sub_style = str(slot.get("rune_sub_style_icon_path") or "")
                if keystone:
                    rune_image = pil_to_qimage(
                        self.data_dragon.compose_rune_button_icon(keystone, sub_style, size=30),
                        size=(30, 30),
                    )
                skin_image = None
                skin_mode = get_effective_skin_mode_for_slot(slot_key, effective, overrides)
                if skin_mode == "fixed":
                    skin_name = str(slot.get("skin_name") or "")
                    skin_id = slot.get("skin_id")
                    skin_num = slot.get("skin_num")
                elif skin_mode == "random":
                    skin_name = str(slot.get("random_skin_name") or "")
                    skin_id = slot.get("random_skin_id")
                    skin_num = slot.get("random_skin_num")
                else:
                    skin_name = ""
                    skin_id = 0
                    skin_num = 0
                if skin_name or skin_id or skin_num:
                    skin_url = self.data_dragon.get_skin_preview_url(
                        champion,
                        skin_name=skin_name,
                        skin_id=skin_id,
                        skin_num=skin_num,
                    )
                    if skin_url:
                        skin_image = pil_to_qimage(
                            self.data_dragon.get_remote_image(
                                skin_url,
                                cache_key=f"skin_preview_{champion}_{skin_id}_{skin_num}",
                            ),
                            size=(48, 48),
                        )
                assets[slot_key] = {
                    "champion": pil_to_qimage(self.data_dragon.get_champion_icon(champion), size=(54, 54)),
                    "spells": spell_images,
                    "rune": rune_image,
                    "skin": skin_image,
                }
            ban_image = None
            if selected_ban and selected_ban != "(None)":
                ban_image = pil_to_qimage(
                    self.data_dragon.get_champion_icon(selected_ban),
                    size=(30, 30),
                )
            return {
                "generation": generation,
                "assets": assets,
                "ban": ban_image,
            }

        self.task_runner.submit(load, guarded_callback(self, "_apply_champion_icons"))

    def _apply_champion_icons(self, payload: Mapping[str, Any]) -> None:
        if payload.get("generation") != self._icon_generation:
            return
        assets = payload.get("assets", {})
        if not isinstance(assets, Mapping):
            return
        _set_qimage_label(self.active_ban_icon, payload.get("ban"), 30, "champion")
        for slot_key, asset in assets.items():
            if not isinstance(asset, Mapping):
                continue
            if slot_key in self.preset_rows:
                row = self.preset_rows[slot_key]
                _set_qimage_label(row.icon, asset.get("champion"), 54, "champion")
                spell_images = asset.get("spells", {})
                for number, icon_label in enumerate(row.spell_icon_labels, start=1):
                    _set_qimage_label(icon_label, spell_images.get(number), 28, "spells")
                _set_qimage_label(row.rune_icon_label, asset.get("rune"), 28, "runes")
                _set_qimage_label(row.skin_icon_label, asset.get("skin"), 40, "skin")
            if slot_key == PICK_SLOT_ORDER[0]:
                _set_qimage_label(self.active_champion_icon, asset.get("champion"), 42, "champion")
                spell_images = asset.get("spells", {})
                for number, icon_label in enumerate(self.active_spell_icons, start=1):
                    _set_qimage_label(icon_label, spell_images.get(number), 28, "spells")
                _set_qimage_label(self.active_rune_icon, asset.get("rune"), 30, "runes")
                _set_qimage_label(self.active_skin_icon, asset.get("skin"), 42, "skin")

    def _current_riot_id(self) -> str:
        if bool(self.settings.get("summoner_name_auto_detect", True)):
            return str(self.settings.get("auto_detected_riot_id") or "")
        return str(self.settings.get("manual_summoner_name") or "")

    def _refresh_stats_enabled(self) -> None:
        riot_id = self._current_riot_id().strip()
        self.open_stats_button.setEnabled("#" in riot_id and all(riot_id.split("#", 1)))

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
            if event.category.upper() in {
                "BAN", "PICK", "SKIN", "RUNES", "SUMMS", "OK", "GAME_LOADING", "GAME_STARTED", "LOBBY"
            }:
                self._refresh_activity()
        elif isinstance(event, PhaseChanged):
            self.phase_label.setText(PHASE_DISPLAY_MAP.get(event.phase, event.phase))
            if event.phase in {"GameStart", "InProgress", "Lobby"}:
                self._refresh_activity()
        elif isinstance(event, SummonerUpdated):
            self.settings["auto_detected_riot_id"] = event.riot_id or ""
            self.refresh_settings(self.settings)
        elif isinstance(event, ProfileUpdated):
            self.settings["auto_detected_riot_id"] = event.riot_id or ""
            self._profile_icon_id = event.profile_icon_id
            self._summoner_level = event.summoner_level
            self._ranked_entries = event.ranked_entries
            self.refresh_settings(self.settings)
        elif isinstance(event, ChampionPicked):
            self._refresh_activity()
            self.enqueue_toast(f"Picked {event.champion}", 3000)
        elif isinstance(event, ChampionBanned):
            self._refresh_activity()
            self.ban_label.setText(f"Ban: {event.champion}")
        elif isinstance(event, SpellsApplied):
            self._refresh_activity()
            self.spells_label.setText(f"Spells: {event.first} + {event.second}")
            self.active_loadout_label.setText(f"{event.first}  +  {event.second}")
            self.enqueue_toast(f"Spells applied: {event.first} + {event.second}", 3000)
        elif isinstance(event, ReadyCheckAccepted):
            self._refresh_activity()
            self.enqueue_toast("Match accepted", 3000)
        elif isinstance(event, PlayAgainSucceeded):
            self._refresh_activity()
            self.enqueue_toast("Returned to lobby", 2500)
        elif isinstance(event, ToastRequested):
            self.enqueue_toast(event.message, event.duration_ms)
        elif isinstance(event, UpdateAvailable):
            self.statusBar().showMessage(f"Version {event.version} is available")
            self._set_news(event.version, event.highlights)

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
        self.connection_chip.setText("League client connected" if connected else "League client offline")
        self.connection_chip.setProperty("connected", connected)
        self.connection_panel.setProperty("connected", connected)
        self.connection_dot.setProperty("connected", connected)
        self.account_status.setText("Connected" if connected else "Offline")
        if connected and self.status_label.text() == "Waiting for League client":
            self.status_label.setText("Ready for queue")
            self.phase_label.setText("League client connected and ready.")
            self.statusBar().showMessage("League client connected")
        elif not connected:
            self.status_label.setText("Waiting for League client")
            self.phase_label.setText("Waiting for League client.")
            self.statusBar().showMessage("Waiting for the League client")
        self._repolish(self.connection_chip)
        self._repolish(self.connection_panel)
        self._repolish(self.connection_dot)
        if self._connection_pulse is not None:
            if connected:
                self._connection_pulse.start()
            else:
                self._connection_pulse.stop()
                self._connection_opacity.setOpacity(0.65)

    def _set_news(self, version: str, highlights: Any) -> None:
        if isinstance(highlights, (list, tuple)):
            items = [str(item).strip() for item in highlights if str(item).strip()]
        else:
            items = []
            for raw_line in str(highlights or "").splitlines():
                line = raw_line.strip().lstrip("-*• ").strip()
                if line:
                    items.append(line)
        if not items:
            items = list(_LOCAL_NEWS_HIGHLIGHTS)
        self.news_version_label.setText(f"OTP LOL v{version}")
        self.news_highlights_label.setText("\n".join(f"• {item}" for item in items[:4]))

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
