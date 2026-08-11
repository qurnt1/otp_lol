"""Thread-safe image conversion and local SVG icon helpers for PySide6 widgets."""

from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from src.config.constants import APP_ICON_FILES
from src.config.paths import resource_path

DEFAULT_APP_ICON_SIZE = 24
DEFAULT_APP_ICON_COLOR = "#F2F5F8"


def app_icon_path(name: str) -> str:
    """Return the bundled path for a named application icon."""
    try:
        relative_path = APP_ICON_FILES[name]
    except KeyError as error:
        raise ValueError(f"Unknown application icon: {name!r}") from error
    return resource_path(relative_path)


def _render_svg_icon(svg: str, *, size: int) -> QIcon:
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def load_app_icon(
    name: str,
    *,
    size: int = DEFAULT_APP_ICON_SIZE,
    color: str | None = None,
) -> QIcon:
    """Load one of the local monochrome SVG icons, optionally tinted."""
    if size <= 0:
        raise ValueError("Icon size must be greater than zero")

    path = Path(app_icon_path(name))
    if color is None:
        return QIcon(str(path))

    tint = QColor(color)
    if not tint.isValid():
        raise ValueError(f"Invalid icon color: {color!r}")

    svg = path.read_text(encoding="utf-8")
    svg = svg.replace(f'stroke="{DEFAULT_APP_ICON_COLOR}"', f'stroke="{tint.name().upper()}"')
    return _render_svg_icon(svg, size=size)


def pil_to_qimage(image: Any, *, size: tuple[int, int] | None = None) -> QImage | None:
    """Copy a Pillow image into an independent QImage."""
    if image is None:
        return None
    try:
        if size:
            from PIL import Image

            image = image.resize(size, Image.Resampling.LANCZOS)
        rgba = image.convert("RGBA")
        width, height = rgba.size
        return QImage(
            rgba.tobytes("raw", "RGBA"),
            width,
            height,
            width * 4,
            QImage.Format.Format_RGBA8888,
        ).copy()
    except Exception:
        return None


def qpixmap_from_image(image: QImage | None) -> QPixmap:
    return QPixmap.fromImage(image) if image is not None and not image.isNull() else QPixmap()
