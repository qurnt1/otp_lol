"""PySide6 visual tokens for the OTP LOL League Companion shell."""

_BASE = """
QWidget { font-family: \"Segoe UI\"; font-size: 10pt; }
QLabel, QCheckBox { background: transparent; }
QLabel#brandName { font-size: 18pt; font-weight: 700; }
QLabel#brandVersion, QLabel#footerNote { font-size: 9pt; }
QLabel#pageTitle { font-size: 22pt; font-weight: 700; }
QLabel#pageSectionTitle { font-size: 18pt; font-weight: 700; }
QLabel#heroTitle { font-size: 18pt; font-weight: 700; }
QLabel#cardTitle, QLabel#sectionTitle { font-weight: 650; }
QLabel#eyebrow { font-size: 9pt; font-weight: 700; letter-spacing: 1px; }
QLabel#activityTime, QLabel#activityLevel, QLabel#shortcutKey { font-size: 9pt; }
QLabel#shortcutKey { padding: 6px 10px; border-radius: 6px; }
QLabel#statePill { padding: 3px 8px; border-radius: 8px; font-size: 8pt; font-weight: 700; }
QLabel#connectionChip { padding: 8px 0; border-radius: 8px; font-weight: 650; }
QPushButton { min-height: 34px; padding: 0 13px; border-radius: 7px; font-weight: 600; }
QPushButton#navButton { min-height: 42px; padding: 0 13px; text-align: left; border-radius: 7px; }
QPushButton#primaryButton { min-height: 38px; padding: 0 18px; }
QPushButton#secondaryButton { min-height: 34px; }
QPushButton#linkButton { min-height: 28px; padding: 0 5px; border: 0; }
QPushButton:disabled { color: #727c88; }
QCheckBox::indicator { width: 34px; height: 18px; border-radius: 9px; }
QScrollArea { border: 0; }
QStatusBar { min-height: 28px; }
QLineEdit, QComboBox, QKeySequenceEdit { min-height: 34px; padding: 0 9px; border-radius: 6px; }
QListWidget, QTreeWidget, QTextBrowser { border-radius: 7px; padding: 4px; }
QTabWidget::pane { border-radius: 8px; top: -1px; }
QTabBar::tab { min-width: 120px; padding: 10px 14px; font-weight: 650; }
QGroupBox { margin-top: 15px; padding-top: 14px; border-radius: 8px; font-weight: 700; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
QToolTip { padding: 6px; border-radius: 4px; }
"""

DARK_STYLESHEET = _BASE + """
QWidget { background: #0e131b; color: #eef3f8; }
QMainWindow, QWidget#desktopRoot, QWidget#contentArea, QWidget#page { background: #10161f; }
QLabel, QCheckBox { background: transparent; }
QWidget#sidebar { background: #151d28; border-right: 1px solid #2b3745; }
QLabel#brandName { color: #f2f5f8; }
QLabel#brandVersion, QLabel#footerNote, QLabel[secondary=\"true\"] { color: #9aaabd; }
QPushButton#navButton { background: transparent; color: #c2ccd8; border: 1px solid transparent; }
QPushButton#navButton:hover { background: #202a36; color: #f4f7fa; border-color: #3a4a5b; }
QPushButton#navButton:checked { background: #30232d; color: #ff9c8d; border-color: #7c4a4a; }
QFrame#panel, QFrame#matchPanel, QFrame#activePresetPanel, QFrame#automationSummary,
QFrame#quickAccessPanel, QFrame#activityPanel, QFrame#shortcutsPanel, QFrame#newsPanel,
QFrame#historyListPanel, QFrame#settingSummary, QFrame#accountPanel, QFrame#automationCard,
QFrame#presetCard, QFrame#rankPanel, QFrame#automationSwitchRow, QFrame#connectionPanel { background: #18212c; border: 1px solid #2a3949; border-radius: 11px; }
QFrame#matchPanel { background: #1b2935; }
QLabel#eyebrow { color: #ff8977; }
QFrame#connectionPanel { background: #2d2223; border-color: #61393b; }
QFrame#connectionPanel[connected=\"true\"] { background: #162d22; border-color: #2c7345; }
QLabel#connectionChip { color: #e3a3a3; }
QLabel#connectionChip[connected=\"true\"] { color: #77e19b; }
QLabel#connectionDot { background: #8b5a60; border-radius: 5px; }
QLabel#connectionDot[connected=\"true\"] { background: #35c98a; }
QLabel#statePill, QLabel#statePill[state=\"on\"] { background: #30232a; color: #ffab9c; }
QLabel#statePill[state=\"off\"] { background: #1c2733; color: #8594a4; }
QLabel#activityTime, QLabel#activityLevel { color: #93a2b2; }
QLabel#shortcutKey { background: #202a36; border: 1px solid #364858; color: #d5dee8; }
QFrame#quickAccessItem { background: #202a36; border: 1px solid #354858; border-radius: 7px; color: #dbe4ec; }
QFrame#activityRow { background: #151d28; border: 1px solid #293b4d; border-radius: 7px; }
QPushButton { background: #202a36; color: #e7edf2; border: 1px solid #3a4d60; }
QPushButton:hover { background: #293746; border-color: #607487; }
QPushButton:pressed { background: #18242f; }
QPushButton#primaryButton { background: #ed725f; color: #241518; border-color: #ff9c8d; }
QPushButton#primaryButton:hover { background: #ff8876; border-color: #ffb2a5; }
QPushButton#primaryButton:disabled { background: #4a4b43; color: #a5a79c; border-color: #5a5c54; }
QPushButton#secondaryButton { background: #202a36; }
QPushButton#riotClientButton { padding: 0 14px; background: #202a36; }
QPushButton#riotClientButton:hover { background: #293746; border-color: #607487; }
QPushButton#linkButton { background: transparent; color: #ff9c8d; }
QPushButton#linkButton:hover { color: #ffb5aa; }
QPushButton:focus, QCheckBox:focus, QLineEdit:focus, QComboBox:focus, QKeySequenceEdit:focus { border: 2px solid #ff9c8d; }
QCheckBox::indicator { background: #273746; border: 1px solid #4b6275; }
QCheckBox::indicator:checked { background: #d0a843; border-color: #f1cf69; }
QCheckBox::indicator:checked:hover { background: #e1bb55; }
QLabel#activityLevel[level=\"success\"], QLabel#activityLevel[action=\"pick\"], QLabel#activityLevel[action=\"skin\"] { color: #77e19b; font-weight: 700; }
QLabel#activityLevel[action=\"ban\"], QLabel#activityLevel[level=\"error\"] { color: #ff8f8f; font-weight: 700; }
QLabel#activityLevel[level=\"warning\"] { color: #ffcf7a; font-weight: 700; }
QStatusBar { background: #151d28; color: #9aaabd; border-top: 1px solid #2b3745; }
QScrollBar:vertical { background: #121a23; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: #3a4d60; min-height: 32px; border-radius: 5px; }
QLineEdit, QComboBox, QKeySequenceEdit, QListWidget, QTreeWidget, QTextBrowser { background: #151d28; color: #eef3f8; border: 1px solid #364858; }
QListWidget::item:selected, QTreeWidget::item:selected { background: #3b2933; color: #fff1ee; }
QTabWidget::pane, QGroupBox { border: 1px solid #364858; }
QTabBar::tab { background: #18212c; border: 1px solid #364858; color: #aebdca; }
QTabBar::tab:selected { background: #3b2933; color: #ffab9c; }
QToolTip { color: #eef3f8; background: #202a36; border: 1px solid #607487; }
"""

LIGHT_STYLESHEET = _BASE + """
QWidget { background: #f1f3f5; color: #202832; }
QMainWindow, QWidget#desktopRoot, QWidget#contentArea, QWidget#page { background: #f1f3f5; }
QLabel, QCheckBox { background: transparent; }
QWidget#sidebar { background: #e5e9ed; border-right: 1px solid #c5cdd5; }
QLabel#brandName { color: #202832; }
QLabel#brandVersion, QLabel#footerNote, QLabel[secondary=\"true\"] { color: #64717d; }
QPushButton#navButton { background: transparent; color: #465563; border: 1px solid transparent; }
QPushButton#navButton:hover { background: #d8e0e8; color: #202832; border-color: #bcc7d1; }
QPushButton#navButton:checked { background: #fff8f6; color: #a64d40; border-color: #e4aaa0; }
QFrame#panel, QFrame#matchPanel, QFrame#activePresetPanel, QFrame#automationSummary,
QFrame#quickAccessPanel, QFrame#activityPanel, QFrame#shortcutsPanel, QFrame#newsPanel,
QFrame#historyListPanel, QFrame#settingSummary, QFrame#accountPanel, QFrame#automationCard,
QFrame#presetCard, QFrame#rankPanel, QFrame#automationSwitchRow, QFrame#connectionPanel { background: #fffdfb; border: 1px solid #c8d0d7; border-radius: 11px; }
QFrame#matchPanel { background: #f8fafb; }
QLabel#eyebrow { color: #b55243; }
QFrame#connectionPanel { background: #f5e4e2; border-color: #d5aaa6; }
QFrame#connectionPanel[connected=\"true\"] { background: #e0f1e4; border-color: #9ec8a7; }
QLabel#connectionChip { color: #8d3631; }
QLabel#connectionChip[connected=\"true\"] { color: #28663b; }
QLabel#connectionDot { background: #bc7c78; border-radius: 5px; }
QLabel#connectionDot[connected=\"true\"] { background: #2fbf7f; }
QLabel#statePill, QLabel#statePill[state=\"on\"] { background: #fbe5e1; color: #a64d40; }
QLabel#statePill[state=\"off\"] { background: #e6ebef; color: #71808c; }
QLabel#activityTime, QLabel#activityLevel { color: #697886; }
QLabel#shortcutKey { background: #edf1f4; border: 1px solid #ccd5dc; color: #43515e; }
QFrame#quickAccessItem { background: #f3f6f8; border: 1px solid #d0d8df; border-radius: 7px; color: #31404c; }
QFrame#activityRow { background: #f6f8fa; border: 1px solid #d9e0e5; border-radius: 7px; }
QPushButton { background: #fffdfb; color: #202832; border: 1px solid #b9c3cc; }
QPushButton:hover { background: #fff1ee; border-color: #8d9aa5; }
QPushButton:pressed { background: #e5e9ed; }
QPushButton#primaryButton { background: #e96b57; color: #2d1714; border-color: #c85545; }
QPushButton#primaryButton:hover { background: #f17b68; border-color: #b94b3d; }
QPushButton#primaryButton:disabled { background: #d2d2c8; color: #7b807c; border-color: #b7bab4; }
QPushButton#linkButton { background: transparent; color: #b55243; }
QPushButton#linkButton:hover { color: #8f3f34; }
QPushButton:focus, QCheckBox:focus, QLineEdit:focus, QComboBox:focus, QKeySequenceEdit:focus { border: 2px solid #d56857; }
QCheckBox::indicator { background: #d7dde2; border: 1px solid #aab6bf; }
QCheckBox::indicator:checked { background: #c4962e; border-color: #8b6517; }
QLabel#activityLevel[level=\"success\"], QLabel#activityLevel[action=\"pick\"], QLabel#activityLevel[action=\"skin\"] { color: #1e8c5a; font-weight: 700; }
QLabel#activityLevel[action=\"ban\"], QLabel#activityLevel[level=\"error\"] { color: #c0393b; font-weight: 700; }
QLabel#activityLevel[level=\"warning\"] { color: #a76700; font-weight: 700; }
QStatusBar { background: #e2e7ec; color: #64717d; border-top: 1px solid #c5cdd5; }
QScrollBar:vertical { background: #e7ebee; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: #b9c3cc; min-height: 32px; border-radius: 5px; }
QLineEdit, QComboBox, QKeySequenceEdit, QListWidget, QTreeWidget, QTextBrowser { background: #fffdfb; color: #202832; border: 1px solid #b9c3cc; }
QListWidget::item:selected, QTreeWidget::item:selected { background: #fbe5e1; color: #202832; }
QTabWidget::pane, QGroupBox { border: 1px solid #c5cdd5; }
QTabBar::tab { background: #e8edf1; border: 1px solid #c5cdd5; color: #52616e; }
QTabBar::tab:selected { background: #fff8f6; color: #a64d40; }
QToolTip { color: #202832; background: #fffdfb; border: 1px solid #aab6bf; }
"""


def stylesheet_for(theme_name: str) -> str:
    return LIGHT_STYLESHEET if theme_name == "flatly" else DARK_STYLESHEET
