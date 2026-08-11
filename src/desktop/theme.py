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
QLabel#connectionChip { padding: 8px 12px; border-radius: 8px; font-weight: 650; }
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
QWidget { background: #0b111a; color: #eef3f8; }
QMainWindow, QWidget#desktopRoot, QWidget#contentArea, QWidget#page { background: #0b111a; }
QLabel, QCheckBox { background: transparent; }
QWidget#sidebar { background: #101a26; border-right: 1px solid #233242; }
QLabel#brandName { color: #d0a843; }
QLabel#brandVersion, QLabel#footerNote, QLabel[secondary=\"true\"] { color: #9aaabd; }
QPushButton#navButton { background: transparent; color: #c2ccd8; border: 1px solid transparent; }
QPushButton#navButton:hover { background: #172331; color: #f4f7fa; border-color: #293b4d; }
QPushButton#navButton:checked { background: #1a2938; color: #e0b95d; border-color: #3b4f63; }
QFrame#panel, QFrame#matchPanel, QFrame#activePresetPanel, QFrame#automationSummary,
QFrame#quickAccessPanel, QFrame#activityPanel, QFrame#shortcutsPanel, QFrame#newsPanel,
QFrame#historyListPanel, QFrame#settingSummary, QFrame#accountPanel, QFrame#automationCard,
QFrame#presetCard, QFrame#rankPanel { background: #121e2b; border: 1px solid #26384a; border-radius: 11px; }
QFrame#matchPanel { background: #152331; }
QLabel#eyebrow { color: #d0a843; }
QLabel#connectionChip { background: #2d2223; color: #e3a3a3; border: 1px solid #61393b; }
QLabel#connectionChip[connected=\"true\"] { background: #162d22; color: #77e19b; border-color: #2c7345; }
QLabel#connectionChip[pulsing=\"true\"] { background: #1d3c29; border-color: #4a9c63; }
QLabel#statePill, QLabel#statePill[state=\"on\"] { background: #2b2415; color: #e0b95d; }
QLabel#statePill[state=\"off\"] { background: #1c2733; color: #8594a4; }
QLabel#activityTime, QLabel#activityLevel { color: #93a2b2; }
QLabel#shortcutKey { background: #172331; border: 1px solid #2b4053; color: #d5dee8; }
QFrame#quickAccessItem { background: #172331; border: 1px solid #293d50; border-radius: 7px; color: #dbe4ec; }
QFrame#activityRow { background: #101a26; border: 1px solid #1e3042; border-radius: 7px; }
QPushButton { background: #172331; color: #e7edf2; border: 1px solid #30465a; }
QPushButton:hover { background: #1d2e40; border-color: #506a82; }
QPushButton:pressed { background: #12202d; }
QPushButton#primaryButton { background: #d0a843; color: #151a20; border-color: #e0bd67; }
QPushButton#primaryButton:hover { background: #dfb957; border-color: #f2d283; }
QPushButton#primaryButton:disabled { background: #4a4b43; color: #a5a79c; border-color: #5a5c54; }
QPushButton#secondaryButton { background: #172331; }
QPushButton#linkButton { background: transparent; color: #d7b65e; }
QPushButton#linkButton:hover { color: #f0d68e; }
QPushButton:focus, QCheckBox:focus, QLineEdit:focus, QComboBox:focus, QKeySequenceEdit:focus { border: 2px solid #e0bd67; }
QCheckBox::indicator { background: #273746; border: 1px solid #4b6275; }
QCheckBox::indicator:checked { background: #d0a843; border-color: #e7c56f; }
QCheckBox::indicator:checked:hover { background: #e0b957; }
QStatusBar { background: #101a26; color: #9aaabd; border-top: 1px solid #233242; }
QScrollBar:vertical { background: #0e1722; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: #30465a; min-height: 32px; border-radius: 5px; }
QLineEdit, QComboBox, QKeySequenceEdit, QListWidget, QTreeWidget, QTextBrowser { background: #101a26; color: #eef3f8; border: 1px solid #2b4053; }
QListWidget::item:selected, QTreeWidget::item:selected { background: #2b2415; color: #fff3cf; }
QTabWidget::pane, QGroupBox { border: 1px solid #2b4053; }
QTabBar::tab { background: #121e2b; border: 1px solid #2b4053; color: #aebdca; }
QTabBar::tab:selected { background: #2b2415; color: #e0b95d; }
QToolTip { color: #eef3f8; background: #172331; border: 1px solid #506a82; }
"""

LIGHT_STYLESHEET = _BASE + """
QWidget { background: #eef1f4; color: #1f2933; }
QMainWindow, QWidget#desktopRoot, QWidget#contentArea, QWidget#page { background: #eef1f4; }
QLabel, QCheckBox { background: transparent; }
QWidget#sidebar { background: #e2e7ec; border-right: 1px solid #c5cdd5; }
QLabel#brandName { color: #8a641e; }
QLabel#brandVersion, QLabel#footerNote, QLabel[secondary=\"true\"] { color: #64717d; }
QPushButton#navButton { background: transparent; color: #465563; border: 1px solid transparent; }
QPushButton#navButton:hover { background: #d8e0e8; color: #1f2933; border-color: #bcc7d1; }
QPushButton#navButton:checked { background: #fffdf8; color: #765014; border-color: #c8b88d; }
QFrame#panel, QFrame#matchPanel, QFrame#activePresetPanel, QFrame#automationSummary,
QFrame#quickAccessPanel, QFrame#activityPanel, QFrame#shortcutsPanel, QFrame#newsPanel,
QFrame#historyListPanel, QFrame#settingSummary, QFrame#accountPanel, QFrame#automationCard,
QFrame#presetCard, QFrame#rankPanel { background: #fffdf8; border: 1px solid #c8d0d7; border-radius: 11px; }
QFrame#matchPanel { background: #f8fafb; }
QLabel#eyebrow { color: #8a641e; }
QLabel#connectionChip { background: #f5e4e2; color: #8d3631; border: 1px solid #d5aaa6; }
QLabel#connectionChip[connected=\"true\"] { background: #e0f1e4; color: #28663b; border-color: #9ec8a7; }
QLabel#connectionChip[pulsing=\"true\"] { background: #cce8d2; border-color: #62a974; }
QLabel#statePill, QLabel#statePill[state=\"on\"] { background: #f5ead0; color: #765014; }
QLabel#statePill[state=\"off\"] { background: #e6ebef; color: #71808c; }
QLabel#activityTime, QLabel#activityLevel { color: #697886; }
QLabel#shortcutKey { background: #edf1f4; border: 1px solid #ccd5dc; color: #43515e; }
QFrame#quickAccessItem { background: #f3f6f8; border: 1px solid #d0d8df; border-radius: 7px; color: #31404c; }
QFrame#activityRow { background: #f6f8fa; border: 1px solid #d9e0e5; border-radius: 7px; }
QPushButton { background: #fffdf8; color: #1f2933; border: 1px solid #b9c3cc; }
QPushButton:hover { background: #f3eee3; border-color: #8d9aa5; }
QPushButton:pressed { background: #e5e9ed; }
QPushButton#primaryButton { background: #c49a3c; color: #201a0f; border-color: #a87d20; }
QPushButton#primaryButton:hover { background: #d2aa4e; border-color: #8b6519; }
QPushButton#primaryButton:disabled { background: #d2d2c8; color: #7b807c; border-color: #b7bab4; }
QPushButton#linkButton { background: transparent; color: #8a641e; }
QPushButton#linkButton:hover { color: #5d4214; }
QPushButton:focus, QCheckBox:focus, QLineEdit:focus, QComboBox:focus, QKeySequenceEdit:focus { border: 2px solid #9a7224; }
QCheckBox::indicator { background: #d7dde2; border: 1px solid #aab6bf; }
QCheckBox::indicator:checked { background: #b8892d; border-color: #8a641e; }
QStatusBar { background: #e2e7ec; color: #64717d; border-top: 1px solid #c5cdd5; }
QScrollBar:vertical { background: #e7ebee; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: #b9c3cc; min-height: 32px; border-radius: 5px; }
QLineEdit, QComboBox, QKeySequenceEdit, QListWidget, QTreeWidget, QTextBrowser { background: #fffdf8; color: #1f2933; border: 1px solid #b9c3cc; }
QListWidget::item:selected, QTreeWidget::item:selected { background: #e3d2a8; color: #1f2933; }
QTabWidget::pane, QGroupBox { border: 1px solid #c5cdd5; }
QTabBar::tab { background: #e8edf1; border: 1px solid #c5cdd5; color: #52616e; }
QTabBar::tab:selected { background: #fffdf8; color: #765014; }
QToolTip { color: #1f2933; background: #fffdf8; border: 1px solid #aab6bf; }
"""


def stylesheet_for(theme_name: str) -> str:
    return LIGHT_STYLESHEET if theme_name == "flatly" else DARK_STYLESHEET
