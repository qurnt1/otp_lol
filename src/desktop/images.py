"""Thread-safe image conversion helpers for PyQt6 widgets."""

from typing import Any

from PyQt6.QtGui import QImage, QPixmap


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
