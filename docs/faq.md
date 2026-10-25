# FAQ and gotchas

## Does it modify my circuits?
No. `mc9.open()` copies the file into the work folder; `Circuit.export()` writes to a new path and refuses to overwrite.

## My band edge differs from what I read with MC9's cursors.
With MC9's default AC `Sweep type = Auto` the numeric table is coarse and linear, and cursors interpolate between its points - band
edges can be off by more than 10 %. `mc9` always sweeps logarithmically with 401+ points. Double `points` to confirm convergence.

## "Node has no DC path to ground" / "label not found" / "model missing"
These are MC9's own error dialogs. When a run fails the library saves `<circuit>_<analysis>_FAILED.png`; read the dialog in it.
Typical causes: a node connected only through capacitors; a curve like `v(Out)` for a node that is not named; a model name that
is not in MC9's library.

## Why are voltage boxes overlapping each other in my schematic screenshot?
MC9 draws them (centred on a pin of each node) and AC boxes are ~12 grid units wide. Space voltage nodes >= 14 grid units apart and
build with `labels="ac"`. `Schematic.audit("ac")` lists the collisions before you run anything.

## Why is THD computed by a DFT and not taken from MC9's Distortion analysis?
MC9's distortion *numeric* table is a corrupted FFT buffer under Wine. The Distortion *window* is fine, so `c.distortion()` plus
`c.shot()` gives MC9's own figure, while `measure.thd` gives numbers.

## Cursor tables are cut off at the bottom.
MC9 clips the lowest table when plots are stacked. Use one plot per page for figures with cursors.

## Can I use it without a display / on a server?
On Linux yes - the display is virtual (Xvfb). On Windows MC9 needs a desktop session.

## Does it work with the standard English MC9?
The Windows backend does not depend on the language. The Linux backend needs a one-time calibration for editions other than the
Russian GUAP build; see [Supporting other MC9 editions](internals/calibration.md). Reports are welcome.

## Is it legal to automate MC9?
`mc9py` only drives your own licensed copy through its normal user interface and files. It contains no MC9 code or binaries.
The component definitions in `mc9/templates/base.cir` are the small shape/pin descriptions that MC9 itself writes into every circuit it saves.
