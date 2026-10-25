"""Global settings. Change before opening circuits:  ``mc9.config.screen = "2000x1100"``."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Config:
    backend: str = "auto"          # "auto" | "wine" (Linux sandbox) | "windows" (native)
    home: str | None = None        # data/work directory (default: $MC9_HOME, ./sandbox in a checkout, or the user data dir)
    mc9_exe: str | None = None     # path to mc9.exe (Windows path inside the Wine prefix, or a native Windows path)
    screen: str = "2000x1100"      # virtual screen of the Linux backend (MC9's window is 1900x980)
    start_timeout: int = 120       # seconds to wait for MC9 to start
    run_timeout: int = 120         # default seconds to wait for an analysis to finish
    maximize_plots: bool = True    # open analysis windows maximized so tall plot stacks are not cut off
    dialog_wait: float = 1.0       # pause after opening MC9 dialogs (raise on a slow machine)


config = Config()
