# Supporting other MC9 editions

The **Windows backend is language independent**. The **Linux backend** presses buttons by pixel position, and the positions in
`mc9/layout.py` were measured on the Russian *GUAP Edition* of MC9 9.0.3 (window 1900x980, virtual screen 2000x1100).
For another edition or UI language:

1. Open a circuit and take a window screenshot: `c.shot("w.png", "window", trim=False)`.
2. In `Layout`, update the Linux-only block: the position of the *Analysis* menu title, the x of its items and the y of the first item,
   the limits-dialog *Run* button, the cursor dialog (field, Left, Right, Close), and the *OK* buttons of the two dynamic dialogs.
   Hover coordinates are easiest to read from a screenshot in any image viewer.
3. Set the Wine locale to your edition's (`LANG` in `backends/linux_wine.py`).
4. Run `MC9_INTEGRATION=1 pytest tests/test_integration.py` to confirm.

The `tools/calib_*.py` scripts show how label geometry and voltage-box placement were measured from screenshots; rerun them if your
edition draws text differently.

!!! tip
    If you only need the Windows backend's approach (keyboard accelerators + dialog classes), it can also drive Wine from
    inside the prefix - that is how the Windows driver is tested, and it avoids calibration entirely.
