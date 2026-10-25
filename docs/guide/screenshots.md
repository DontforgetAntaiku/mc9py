# Cursors and screenshots

All pictures are **MC9's own pixels** - plots with MC9's grid, fonts and cursor tables, schematics with MC9's voltage boxes.
Nothing is re-rendered, so they look like the ones students and teachers expect.

## Cursors

```python
c.ac(1, 2e7, 801, ["db(v(Ua)/v(Ue))"])
c.cursors(169.1, "23.01k")        # left and right cursor at these X values (SI suffixes allowed)
c.shot("fig_ac.png")
```

The library drives MC9's *Go to X* dialog, so MC9 itself draws the yellow labels and the Left / Right / Delta / Slope table.
Combine with the data helpers to put cursors on measured points:

```python
f_low, f_high = r.cross(g, g0 - 3)
c.cursors(f_low, f_high)
```

!!! tip "One plot per window for cursor figures"
    MC9 shows a cursor table under every plot but clips the lowest one when several plots are stacked. Put the curve you
    want to annotate on its own page, or take two figures.

## Screenshots

```python
c.shot("fig.png")                          # the plot window, cropped tightly (default region="plot")
c.shot("sch.png", "schematic")             # the schematic; the crop comes from the builder's own geometry
c.shot("win.png", "window", trim=False)    # the whole MC9 window - useful for debugging
```

Files are written to `mc9.exchange_dir()` and the `Path` is returned. Before a schematic capture the library leaves
component-placement mode, clears hover highlights and parks the mouse, so you do not get stray tooltips or "ghost" parts.

## Dynamic analyses on the schematic

```python
c.dynamic_dc(25)                  # node voltages
c.shot("dc.png", "schematic")
c.dynamic_ac(2224)                # amplitude and phase at 2224 Hz
c.shot("ac.png", "schematic")
c.show(voltages=True, currents=False)    # which quantities MC9 draws
```

If boxes overlap each other or your labels, the circuit needs more room: see
[Building schematics](schematics.md) - `Schematic.audit()` predicts exactly this before you run anything.

## When a run fails

MC9 reports problems in modal dialogs ("node has no DC path to ground", "label not found", "model missing"). When a run
produces no output the library saves `<circuit>_<analysis>_FAILED.png` - a screenshot of what MC9 shows - and raises
`AnalysisError` with its path. Read the dialog in the picture; that is the real diagnosis.
