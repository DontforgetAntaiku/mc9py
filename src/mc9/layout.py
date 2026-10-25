"""Pixel layout of the MC9 window (window = 1900x980 at screen origin).

Menu/dialog coordinates are used only by the Linux/Wine driver and were calibrated on the Russian GUAP Edition at
2000x1100. Toolbar positions and capture regions are language independent and shared by all drivers.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Layout:
    window: tuple = (1900, 980)
    # --- Linux/Wine driver only (menus/dialogs depend on language and window size)
    menu_analysis: tuple = (305, 37)
    item_x: int = 420
    first_item_y: int = 57
    item_dy: int = 17
    run_button: tuple = (598, 130)
    plot_focus: tuple = (1000, 330)
    cursor_field: tuple = (1445, 118)
    cursor_left: tuple = (1613, 177)
    cursor_right: tuple = (1693, 177)
    cursor_close: tuple = (1775, 177)
    dyndc_ok: tuple = (851, 545)
    dynac_ok: tuple = (993, 639)
    # --- shared (toolbar icons and capture regions)
    select_tool: tuple = (213, 94)
    blank_canvas: tuple = (420, 860)
    park_mouse: tuple = (1960, 1090)
    title_bar: tuple = (900, 12)
    region_window: tuple = (0, 0, 1900, 980)
    region_plot: tuple = (5, 140, 1895, 930)
    region_plot_max: tuple = (5, 139, 1893, 905)
    region_schematic: tuple = (205, 112, 1870, 905)


L = Layout()
ANALYSIS_ITEM = {"transient": 0, "ac": 1, "dc": 2, "dynamic_dc": 3, "dynamic_ac": 4, "distortion": 7}
ANALYSIS_KEYS = {"transient": "alt+1", "ac": "alt+2", "dc": "alt+3", "dynamic_dc": "alt+4", "dynamic_ac": "alt+5",
                 "distortion": "alt+8"}      # MC9 accelerators (language independent), used by the Windows driver
