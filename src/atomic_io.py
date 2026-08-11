"""Small filesystem helpers for replacing critical files without partial writes."""

import os
import tempfile
from typing import Any, Callable


def atomic_write(
    path: str,
    writer: Callable[[Any], None],
    *,
    mode: str,
) -> None:
    """Write a file beside its destination, flush it, then replace the destination."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
        dir=directory,
    )
    try:
        if "b" in mode:
            temporary_file = os.fdopen(fd, mode)
        else:
            temporary_file = os.fdopen(fd, mode, encoding="utf-8")
        with temporary_file as stream:
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = ""
    finally:
        if temporary_path:
            try:
                os.remove(temporary_path)
            except OSError:
                pass
