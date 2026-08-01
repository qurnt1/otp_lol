"""Visual tokens for the PyQt6 desktop interface."""

_BASE = """
QWidget { font-family: "Segoe UI"; font-size: 10pt; }
QLabel, QCheckBox { background: transparent; }
QLabel#brandName { font-size: 18pt; font-weight: 750; }
QLabel#heroTitle, QLabel#dialogTitle { font-size: 22pt; font-weight: 750; }
QLabel[cardTitle="true"], QLabel#sectionTitle { font-weight: 700; }
QLabel#connectionChip { border-radius: 10px; padding: 5px 10px; font-weight: 650; }
QFrame#topBar, QFrame#heroPanel, QFrame[automationCard="true"], QFrame#loadoutPanel,
QFrame[presetRow="true"] { border-radius: 11px; }
QCheckBox::indicator { width: 34px; height: 18px; border-radius: 9px; }
QPushButton { min-height: 34px; padding: 0 14px; border-radius: 7px; font-weight: 600; }
QPushButton:disabled { opacity: 0.55; }
QLineEdit, QComboBox, QKeySequenceEdit {
    min-height: 34px; padding: 0 9px; border-radius: 6px;
}
QListWidget, QTreeWidget, QTextBrowser {
    border-radius: 7px; padding: 4px;
}
QTabWidget::pane { border-radius: 8px; top: -1px; }
QTabBar::tab { min-width: 120px; padding: 10px 14px; font-weight: 650; }
QGroupBox { margin-top: 15px; padding-top: 14px; border-radius: 8px; font-weight: 700; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
QToolTip { padding: 6px; border-radius: 4px; }
"""

DARK_STYLESHEET = _BASE + """
QWidget { background: #171717; color: #f2efe8; }
QMainWindow, QWidget#desktopRoot, QDialog { background: #111111; }
QFrame#topBar, QFrame#heroPanel, QFrame[automationCard="true"], QFrame#loadoutPanel,
QFrame[presetRow="true"] { background: #1d1d1d; border: 1px solid #323232; }
QLabel#brandName { color: #f4c96b; }
QLabel#brandSubtitle, QLabel[secondary="true"] { color: #aaa69d; }
QLabel#connectionChip { background: #2b2020; color: #e8a3a3; border: 1px solid #5b3434; }
QLabel#connectionChip[connected="true"] { background: #17291f; color: #8fd8aa; border-color: #315f42; }
QLabel#connectionChip[pulsing="true"] { background: #20432e; border-color: #58a974; }
QCheckBox::indicator { background: #3a3a3a; border: 1px solid #555555; }
QCheckBox::indicator:checked { background: #c99b45; border-color: #e0b65f; }
QPushButton { background: #272727; color: #f2efe8; border: 1px solid #404040; }
QPushButton:hover { background: #313131; border-color: #777067; }
QPushButton:pressed { background: #202020; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QKeySequenceEdit:focus { border: 2px solid #e0b65f; }
QLineEdit, QComboBox, QKeySequenceEdit { background: #202020; border: 1px solid #414141; }
QListWidget, QTreeWidget, QTextBrowser { background: #181818; border: 1px solid #393939; alternate-background-color: #202020; }
QListWidget::item:selected, QTreeWidget::item:selected { background: #4d4128; color: #fff7e5; }
QTabWidget::pane, QGroupBox { border: 1px solid #353535; }
QTabBar::tab { background: #1c1c1c; border: 1px solid #353535; }
QTabBar::tab:selected { background: #2b2519; color: #f4c96b; }
QStatusBar { background: #111111; color: #aaa69d; border-top: 1px solid #2b2b2b; }
QToolTip { color: #f2efe8; background: #242424; border: 1px solid #555; }
QLabel, QCheckBox { background-color: transparent; }
"""

LIGHT_STYLESHEET = _BASE + """
QWidget { background: #f5f2eb; color: #1e252d; }
QMainWindow, QWidget#desktopRoot, QDialog { background: #ece8df; }
QFrame#topBar, QFrame#heroPanel, QFrame[automationCard="true"], QFrame#loadoutPanel,
QFrame[presetRow="true"] { background: #fffdf8; border: 1px solid #c9c5ba; }
QLabel#brandName { color: #8d641f; }
QLabel#brandSubtitle, QLabel[secondary="true"] { color: #68717a; }
QLabel#connectionChip { background: #f6dfdd; color: #8f302a; border: 1px solid #d5a4a0; }
QLabel#connectionChip[connected="true"] { background: #dcecdf; color: #28623a; border-color: #91bb9c; }
QLabel#connectionChip[pulsing="true"] { background: #c9e6d0; border-color: #5e9d70; }
QCheckBox::indicator { background: #d7d4cc; border: 1px solid #a4a197; }
QCheckBox::indicator:checked { background: #a77625; border-color: #855b17; }
QPushButton { background: #fffdf8; color: #1e252d; border: 1px solid #aaa69b; }
QPushButton:hover { background: #f3eee3; border-color: #77736a; }
QPushButton:pressed { background: #e7e1d6; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QKeySequenceEdit:focus { border: 2px solid #9e701e; }
QLineEdit, QComboBox, QKeySequenceEdit { background: #fffdf8; border: 1px solid #b6b2a8; }
QListWidget, QTreeWidget, QTextBrowser { background: #fffdf8; border: 1px solid #c4c0b5; alternate-background-color: #f3efe6; }
QListWidget::item:selected, QTreeWidget::item:selected { background: #d8c69f; color: #1e252d; }
QTabWidget::pane, QGroupBox { border: 1px solid #c4c0b5; }
QTabBar::tab { background: #e6e1d7; border: 1px solid #c4c0b5; }
QTabBar::tab:selected { background: #fffdf8; color: #765014; }
QStatusBar { background: #ece8df; color: #68717a; border-top: 1px solid #c9c5ba; }
QToolTip { color: #1e252d; background: #fffdf8; border: 1px solid #aaa69b; }
QLabel, QCheckBox { background-color: transparent; }
"""


def stylesheet_for(theme_name: str) -> str:
    return LIGHT_STYLESHEET if theme_name == "flatly" else DARK_STYLESHEET
