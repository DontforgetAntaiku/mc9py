"""Driver interface: the few things MC9 automation needs, independent of the operating system."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path


class Driver(ABC):
    """Controls one running MC9 instance that has the circuit open."""

    name: str

    @abstractmethod
    def open_analysis(self, key: str) -> None:
        """Open an analysis (key: transient|ac|dc|distortion|dynamic_dc|dynamic_ac); its limits dialog appears."""

    @abstractmethod
    def press_run(self) -> None:
        """Start the analysis whose limits dialog is open."""

    @abstractmethod
    def confirm_dynamic(self, key: str) -> None:
        """Press OK in the Dynamic DC / Dynamic AC dialog."""

    @abstractmethod
    def set_cursors(self, left: str, right: str | None) -> None:
        """Open MC9's 'go to X' dialog, put the left (and right) cursor there, close it."""

    @abstractmethod
    def exit_analysis(self) -> None:
        """Close the analysis window, back to the schematic."""

    def optimize(self, timeout: float) -> dict:
        """Open MC9's Optimizer (settings come from the file's [Optimize] section), run it, apply the result."""
        raise NotImplementedError("the optimizer needs the native engine (mc9.config.engine = 'native')")

    @abstractmethod
    def prepare_capture(self, schematic: bool) -> None:
        """Remove hover artefacts before a screenshot (leave placement mode, park the mouse)."""

    @abstractmethod
    def grab(self):
        """PIL image of the MC9 window (origin = window top-left, size 1900x980)."""

    @abstractmethod
    def close(self) -> None:
        """Terminate MC9."""

    # ---- shared helpers ------------------------------------------------------------------------
    @staticmethod
    def sleep(seconds: float) -> None:
        time.sleep(seconds)

    @staticmethod
    def wait_output(path: Path, timeout: float, stable_s: int = 4) -> bool:
        """Wait until `path` exists, is non-empty and its size stopped changing for `stable_s` seconds."""
        last, same, t0 = -1, 0, time.time()
        while time.time() - t0 < timeout:
            time.sleep(1)
            sz = path.stat().st_size if path.exists() else -1
            same = same + 1 if (sz > 0 and sz == last) else 0
            last = sz
            if same >= stable_s:
                return True
        return False
