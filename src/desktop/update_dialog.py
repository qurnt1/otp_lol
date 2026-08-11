"""PySide6 update notification dialog."""

import html
import re

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from src.config import CURRENT_VERSION, GITHUB_REPO_URL


class UpdateDialog(QDialog):
    ignored = Signal(str)

    def __init__(
        self,
        version: str,
        highlights: str,
        *,
        release_url: str = "",
        asset_url: str = "",
        asset_name: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.version = version
        self.release_url = release_url or f"{GITHUB_REPO_URL}/releases/latest"
        self.asset_url = asset_url
        self.setWindowTitle("OTP LOL update")
        self.resize(620, 520)
        root = QVBoxLayout(self)
        title = QLabel(f"OTP LOL {version} is available")
        title.setObjectName("dialogTitle")
        root.addWidget(title)
        current = QLabel(f"Installed: {CURRENT_VERSION}  ·  Available: {version}")
        current.setProperty("secondary", True)
        root.addWidget(current)
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setHtml(_render_release_notes(highlights))
        root.addWidget(notes, 1)
        self.do_not_remind = QCheckBox("Do not remind me about this version")
        root.addWidget(self.do_not_remind)

        download_label = f"Download {asset_name}" if asset_name else "Open latest release"
        download = QPushButton(download_label)
        download.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(self.asset_url or self.release_url))
        )
        source = QPushButton("Open repository")
        source.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_REPO_URL)))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.addButton(download, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(source, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def done(self, result: int) -> None:
        if self.do_not_remind.isChecked():
            self.ignored.emit(self.version)
        super().done(result)


def _render_release_notes(markdown: str) -> str:
    """Render the small release-note subset used by the update checker."""
    blocks: list[str] = []
    in_code = False
    for raw_line in str(markdown or "No release highlights supplied.").splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code = not in_code
            blocks.append("<pre>" if in_code else "</pre>")
            continue
        escaped = html.escape(line)
        escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
        if in_code:
            blocks.append(escaped)
        elif line.startswith(("- ", "* ")):
            blocks.append(f"<p>• {escaped[2:]}</p>")
        elif line.startswith("#"):
            blocks.append(f"<h3>{escaped.lstrip('#').strip()}</h3>")
        elif escaped:
            blocks.append(f"<p>{escaped}</p>")
    if in_code:
        blocks.append("</pre>")
    return "".join(blocks)
