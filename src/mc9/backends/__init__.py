"""MC9 drivers. `create(name)` picks the backend: Windows native, or Linux + Wine sandbox."""
from __future__ import annotations

import sys

from ..config import config
from .base import Driver


def create(name: str) -> Driver:
    kind = config.backend
    if kind == "auto":
        kind = "windows" if sys.platform == "win32" else "wine"
    if kind == "windows":
        from .windows import WindowsDriver
        return WindowsDriver(name)
    if kind == "wine":
        from .linux_wine import LinuxWineDriver
        return LinuxWineDriver(name)
    raise ValueError(f"unknown backend {kind!r} (use 'auto', 'wine' or 'windows')")
