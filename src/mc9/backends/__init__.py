"""MC9 drivers. `create(name)` picks the engine and the platform.

Two engines that never mix inside one session:
  * ``native`` - `mc9hook.dll` inside MC9: commands and dialog messages, no mouse/keyboard (backends/native.py);
  * ``clicks`` - mouse and keyboard only: `LinuxWineDriver` (Wine sandbox) or `WindowsDriver` (backends/linux_wine.py, windows.py).
``engine="auto"`` uses native and falls back to clicks only if the hook cannot be started at all.
"""
from __future__ import annotations

import sys
import warnings

from ..config import config
from .base import Driver


def _clicks(name: str) -> Driver:
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


def create(name: str) -> Driver:
    engine = config.engine
    if engine not in ("auto", "native", "clicks"):
        raise ValueError(f"unknown engine {engine!r} (use 'auto', 'native' or 'clicks')")
    if engine == "clicks":
        return _clicks(name)
    from .native import NativeDriver
    try:
        return NativeDriver(name)
    except Exception as e:  # noqa: BLE001 - any failure to bring the hook up
        if engine == "native":
            raise
        warnings.warn(f"native engine unavailable ({e}); using the click engine", stacklevel=2)
        return _clicks(name)
