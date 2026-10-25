"""MC9 session logic (flows) on top of an OS driver: run analyses, cursors, screenshots."""
from __future__ import annotations

from PIL import Image, ImageChops

from . import backends, workspace
from .config import config
from .layout import L
from .results import EXT


class AnalysisError(RuntimeError):
    """MC9 did not produce results (error dialog, invalid circuit, ...). A screenshot is saved for diagnosis."""


class MC9:
    """One running MC9 instance on a circuit. Use through `mc9.Circuit`."""

    def __init__(self, name: str):
        workspace.path(name)       # validates the name
        self.name = name
        self.d = backends.create(name)
        self.mode = "schematic"
        self.maximized = False

    # ---- analyses with a plot window (numeric output is read from the file MC9 writes)
    def run(self, analysis: str, timeout: int | None = None) -> str:
        """Open the analysis, press Run, wait for MC9's numeric output file; returns its path."""
        a = analysis.lower()
        timeout = timeout or config.run_timeout
        out = workspace.exchange() / f"{self.name}.{EXT[a]}"
        out.unlink(missing_ok=True)
        self.d.open_analysis(a)
        self.d.press_run()
        first = min(30, timeout)
        if not self.d.wait_output(out, first):
            self.d.press_run()                           # the dialog may not have been ready: press Run once more
            self.d.wait_output(out, timeout)
        self.d.sleep(3)
        if not out.exists() or out.stat().st_size == 0:
            dbg = f"{self.name}_{a}_FAILED.png"
            self.screenshot(dbg, "window", trim=False)
            raise AnalysisError(f"{a} produced no output file; see screenshot {workspace.exchange() / dbg}")
        self.mode = a
        self.maximized = config.maximize_plots   # window state is forced in the .cir (see Circuit._flush)
        return str(out)

    # ---- dynamic analyses (settings come from the .cir [Limits] so the dialog only needs OK)
    def dynamic_dc(self) -> None:
        self.d.open_analysis("dynamic_dc")
        self.d.confirm_dynamic("dynamic_dc")
        self.mode = "dynamic_dc"

    def dynamic_ac(self) -> None:
        self.d.open_analysis("dynamic_ac")
        self.d.confirm_dynamic("dynamic_ac")
        self.mode = "dynamic_ac"

    def optimize(self, analysis: str, timeout: float = 600) -> dict:
        """Run the analysis once, then MC9's optimizer on it (native engine); returns what the optimizer reports."""
        self.run(analysis)
        return self.d.optimize(timeout)

    # ---- plot tools
    def cursors(self, left: str, right: str | None = None) -> None:
        """MC9 measurement cursors at X values (SI suffixes ok: 23.01k)."""
        self.d.set_cursors(left, right)

    def exit_analysis(self) -> None:
        self.d.exit_analysis()
        self.mode, self.maximized = "schematic", False

    # ---- screenshots (native MC9 pixels)
    def screenshot(self, out_name: str, region: str = "plot", trim: bool = True, margin: int = 8,
                   crop: tuple | None = None) -> str:
        self.d.prepare_capture(self.mode in ("schematic", "dynamic_dc", "dynamic_ac"))
        box = {"window": L.region_window, "schematic": L.region_schematic,
               "plot": L.region_plot_max if self.maximized else L.region_plot}[region]
        img = self.d.grab().crop(crop if crop else box)
        if trim and not crop:
            bbox = ImageChops.difference(img, Image.new("RGB", img.size, (255, 255, 255))).getbbox()
            if bbox:
                l, t, r, b = bbox
                img = img.crop((max(l - margin, 0), max(t - margin, 0),
                                min(r + margin, img.width), min(b + margin, img.height)))
        dst = workspace.exchange() / out_name
        img.save(dst)
        return str(dst)

    def close(self) -> None:
        self.d.close()
