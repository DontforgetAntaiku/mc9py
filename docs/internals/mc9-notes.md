# MC9 file format and geometry

Reference notes collected while building the library. All verified on MC9 9.0.3.

## Circuit file (`.cir`)

INI-like text, Windows-1251, CRLF. Sections repeat (`[Comp]`, `[Attr]`, `[Wire]` ...). Order matters: `[Main]`, `[shapedef]`s,
`[compdef]`s, `[Circuit]`, then the drawing (`[Comp]` followed by its `[Attr]`s, `[Wire]`s, `[Grid Text]`s), then pages and one block per
analysis (`[Transient]`, `[AC]`, `[DC]`, `[Distortion]`, `[Limits]` blocks and `[WaveForm]` curve definitions).

| Item | Format |
|---|---|
| Component | `[Comp] Name=Resistor, Grid=71,23, Rot=2` followed by `[Attr] ONV=dx,dy,PART,R1` / `ONV=dx,dy,RESISTANCE,12k` (+`Style=8192` = visible) |
| Wire | `[Wire] Grids=x1,y1,x2,y2` - axis aligned; **joins only at endpoints** |
| Node name | `[Grid Text] Text="Ue", Grid=x,y, CBorder=NONE` - attaches only at a wire endpoint or pin; same name = same node |
| Analysis limits | `[Limits] Analysis=AC, FRange=2E7,1, NPts=401, Sweep type=Log, ...` (also `DynamicAC`, `DynamicDC`, `Distortion`) |
| Curve | `[WaveForm] Analysis=AC, Plt=1, XExp=F, YExp=db(v(Ua)/v(Ue)), Options=OUTPUT,LINEARY` |
| Numeric output | the `OUTPUT` option on a curve -> table in `<name>.ANO` (`.TNO`, `.DNO`, `.WNO`); the table has exactly `NPts` rows |
| Window state | `Window Placement=0,3,...` (`3` = maximized) in `[Transient]`, `[AC]`, `[DC]`, `[Distortion]` |
| View | `[Page] SB 3=x,y` scroll (design px, never negative), `Scale 3=0.5` zoom (MC9 snaps to 2x or 1x) |

## Geometry

- 1 grid unit = 8 design px; at 2x zoom 16 screen px. Pin positions come from the `Pin="Plus",6,0,...` lines of `[compdef]`.
- `Rot` 0..3: 0/90/180/270 degrees clockwise (y down); 4..7 mirror (y -> -y) before rotating.
- Attribute label offsets are in design px, **not rotated** with the part; the text box starts about (+4, +7) screen px from the
  offset point; at 2x a character is about 13 px wide and the text 18 px high.
- Dynamic DC/AC draw one box per non-ground node, centred on the first pin of the node (component order); a named node's box hangs
  below-right of the name point. Box width ~ `12.5 * chars + 10` screen px, height 29.

## Behaviour worth knowing

- AC `Sweep type=Auto` produces a coarse linear numeric table; use `Log` (see [FAQ](../faq.md)).
- MC9's Distortion numeric table is unusable under Wine; the plots are correct.
- Every node needs a DC path to ground; error dialogs are the only diagnostics.
- `Sine Source` / `Pulse Source` *components* reference library models; the SPICE `Voltage Source` part with `Sin ...` text does not.
- Keyboard accelerators: `Alt+1..8` analyses (Transient, AC, DC, Dynamic DC, Dynamic AC, Sensitivity, Transfer function, Distortion),
  `F2` run, `F3` leave analysis, `Ctrl+Shift+X` go-to-X cursor dialog.
