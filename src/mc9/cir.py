"""Parse and edit Micro-Cap 9 .CIR files (INI-like, cp1251, CRLF).

Only ever used on copies inside the sandbox exchange folder.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

ENC = "cp1251"
_HDR = re.compile(r"^\[(.+)\]\s*$")


@dataclass
class Section:
    name: str
    lines: list[str] = field(default_factory=list)

    def get(self, key: str) -> str | None:
        p = key + "="
        for ln in self.lines:
            if ln.startswith(p):
                return ln[len(p):]
        return None

    def set(self, key: str, value: str) -> None:
        p = key + "="
        for i, ln in enumerate(self.lines):
            if ln.startswith(p):
                self.lines[i] = p + value
                return
        self.lines.append(p + value)


class Cir:
    def __init__(self, text: str):
        self.eol = "\r\n" if "\r\n" in text else "\n"
        self.sections: list[Section] = []
        for ln in text.splitlines():
            m = _HDR.match(ln)
            if m:
                self.sections.append(Section(m.group(1)))
            elif self.sections:
                self.sections[-1].lines.append(ln)

    @classmethod
    def load(cls, path: str) -> "Cir":
        with open(path, "rb") as f:
            return cls(f.read().decode(ENC, errors="surrogateescape"))

    def dumps(self) -> str:
        out: list[str] = []
        for s in self.sections:
            out.append(f"[{s.name}]")
            out.extend(s.lines)
        return self.eol.join(out) + self.eol

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            f.write(self.dumps().encode(ENC, errors="surrogateescape"))

    # ---- components -------------------------------------------------
    def components(self) -> list[dict]:
        comps: list[dict] = []
        cur = None
        for i, s in enumerate(self.sections):
            if s.name == "Comp":
                cur = {"type": s.get("Name"), "grid": s.get("Grid"), "rot": s.get("Rot"),
                       "attrs": {}, "_attr_idx": {}, "_idx": i}
                comps.append(cur)
            elif s.name == "Attr" and cur is not None:
                onv = s.get("ONV")
                if onv:
                    parts = onv.split(",", 3)
                    if len(parts) == 4:
                        cur["attrs"][parts[2]] = parts[3]
                        cur["_attr_idx"][parts[2]] = i
            else:
                cur = None
        return comps

    def find_part(self, part: str) -> dict:
        for c in self.components():
            if c["attrs"].get("PART", "").lower() == part.lower():
                return c
        raise KeyError(f"part {part!r} not found; have: "
                       + ", ".join(c["attrs"].get("PART", "?") for c in self.components()
                                   if "PART" in c["attrs"]))

    def set_attr(self, part: str, attr: str, value: str) -> str:
        c = self.find_part(part)
        key = next((k for k in c["attrs"] if k.lower() == attr.lower()), None)
        if key is None:
            raise KeyError(f"{part} has no attribute {attr!r}; has: {', '.join(c['attrs'])}")
        sec = self.sections[c["_attr_idx"][key]]
        x, y, _, old = sec.get("ONV").split(",", 3)
        sec.set("ONV", f"{x},{y},{key},{value}")
        return old

    def add_attr(self, part: str, name: str, value: str) -> None:
        """Set an attribute; a missing one is created hidden (no Style line), e.g. a part's MODEL."""
        c = self.find_part(part)
        if any(k.lower() == name.lower() for k in c["attrs"]):
            self.set_attr(part, name, value)
            return
        self.sections.insert(max(c["_attr_idx"].values()) + 1, Section("Attr", [f"ONV=0,0,{name},{value}"]))

    def add_text(self, lines: list[str]) -> None:
        """Append text lines (.MODEL/.DEFINE/.PARAMETERS ...) to the circuit's text page (page 1 of the text areas).

        A ``.MODEL``/``.DEFINE`` line replaces an earlier one that defines the same name."""
        page = next((s for s in self.sections if s.name == "Text Area" and s.get("Page") == "1"), None)
        if page is None:
            header = ["Section=0", "Page=1", "Font=Height=-12,FStyle=0,Color=#000000,Name=Courier New",
                      "Comment Color=#808080", "Background Color=#FFFFFF", "Len=0", ""]
            page = Section("Text Area", header + [""])
            second = Section("Text Area", [h if not h.startswith("Page=") else "Page=2" for h in header[:-2]] + ["Len=0", "", ""])
            pos = next((i for i, x in enumerate(self.sections) if x.name in ("Transient", "AC", "DC", "Distortion")), len(self.sections))
            self.sections[pos:pos] = [page, second]
        k = page.lines.index("")                                  # text starts after the first blank line of the header
        body = [ln for ln in page.lines[k + 1:] if ln]
        for ln in lines:
            toks = ln.split()
            if len(toks) > 1 and toks[0].upper() in (".MODEL", ".DEFINE", ".PARAMETERS", ".PARAM"):
                body = [b for b in body if [t.upper() for t in b.split()[:2]] != [t.upper() for t in toks[:2]]]
            if ln not in body:
                body.append(ln)
        page.lines[k + 1:] = body + [""]
        page.set("Len", str(len("\r\n".join(body)) + 2))      # counts the closing line break

    # ---- analyses ---------------------------------------------------
    def limits(self, analysis: str) -> Section:
        for s in self.sections:
            if s.name == "Limits" and (s.get("Analysis") or "").lower() == analysis.lower():
                return s
        raise KeyError(f"no [Limits] for analysis {analysis!r}")

    # ---- stepping / Monte Carlo (both live in the file, one section per analysis) ----------------
    def _insert_point(self) -> int:
        """Where new per-analysis sections go: before MC9's [Optimize]/[Watch]/... block, else at the end."""
        for i, s in enumerate(self.sections):
            if s.name in ("Optimize", "Watch", "Monte Carlo Options"):
                return i
        return len(self.sections)

    def stepping(self, analysis: str) -> list[dict]:
        out = []
        for s in self.sections:
            if s.name == "Stepping" and (s.get("Analysis") or "").lower() == analysis.lower():
                out.append(dict(ln.split("=", 1) for ln in s.lines if "=" in ln))
        return out

    def set_stepping(self, analysis: str, steps: list, nested: bool = True) -> None:
        """Replace the [Stepping] sections of one analysis (``steps``: list of mc9.stepping.Step; empty = stepping off)."""
        name = {"transient": "Transient", "ac": "AC", "dc": "DC", "distortion": "Distortion"}[analysis.lower()]
        self.sections = [s for s in self.sections
                         if not (s.name == "Stepping" and (s.get("Analysis") or "").lower() == analysis.lower())]
        new = []
        for i, st in enumerate(steps, 1):
            sec = Section("Stepping", [f"Analysis={name}", f"Index={i}"])
            if i == 1 and not nested:
                sec.lines.append("Simultaneous=Yes")
            if st.enabled:
                sec.lines.append("Status=On")
            if st.method != "linear":
                sec.lines.append(f"Method={st.method.capitalize()}")
            sec.lines += [f"Parameter Type={st.kind.capitalize()}", f"Name={st.what}", f"Param={st.param or 'Value'}", f"From={st.start}"]
            if st.method != "list":
                sec.lines += [f"To={st.stop}", f"Value={st.step}"]
            new.append(sec)
        pos = self._insert_point()
        self.sections[pos:pos] = new

    def set_optimize(self, analysis: str, params: list, goals: list, method: str = "Standard_Powell") -> None:
        """Fill the analysis' [Optimize] section: params = [(name, low, high, step)], goals = [(kind, function, to)]."""
        sec = next((s for s in self.sections if s.name == "Optimize" and (s.get("Analysis") or "").lower() == analysis.lower()), None)
        if sec is None:                                   # circuits that were never saved by MC9 have none
            sec = Section("Optimize", [f"Analysis={analysis}", "Format=3", "Method=Standard_Powell", "Update_Plot=False"])
            self.sections.insert(self._insert_point(), sec)
        keep = [ln for ln in sec.lines if ln.split("=", 1)[0].split("[")[0] not in ("Find", "Low", "High", "Step", "That", "Function", "To")]
        lines = []
        for i, (name, lo, hi, step) in enumerate(params):
            lines += [f"Find[{i}]={name}", f"Low[{i}]={lo}", f"High[{i}]={hi}", f"Step[{i}]={step}"]
        for i, (kind, func, to) in enumerate(goals):
            lines += [f"That[{i}]={kind}", f"Function[{i}]={func}"] + ([f"To[{i}]={to}"] if to is not None else [])
        head = [ln for ln in keep if ln.split("=", 1)[0] in ("Analysis", "Format")]
        tail = [ln for ln in keep if ln not in head and not ln.startswith("Method=")]
        sec.lines = head + lines + [f"Method={method}"] + tail

    def monte_carlo(self, analysis: str) -> Section:
        for s in self.sections:
            if s.name == "Monte Carlo Options" and (s.get("Analysis") or "").lower() == analysis.lower():
                return s
        raise KeyError(f"no [Monte Carlo Options] for analysis {analysis!r}")

    def waveform_indices(self, analysis: str) -> list[int]:
        return [i for i, s in enumerate(self.sections)
                if s.name == "WaveForm" and (s.get("Analysis") or "").lower() == analysis.lower()]

    def waveforms(self, analysis: str) -> list[dict]:
        return [{"plot": self.sections[i].get("Plt"), "x": self.sections[i].get("XExp"),
                 "y": self.sections[i].get("YExp"), "options": self.sections[i].get("Options")}
                for i in self.waveform_indices(analysis)]

    def set_waveforms(self, analysis: str, curves: list[dict]) -> None:
        """Replace the analysis' curves. Each: {"y": expr, "x": expr?, "plot": int?}."""
        idx = self.waveform_indices(analysis)
        if not idx:
            raise KeyError(f"no [WaveForm] template for {analysis!r}")
        tmpl = copy.deepcopy(self.sections[idx[0]])
        default_x = tmpl.get("XExp") or "T"
        new = []
        for n, c in enumerate(curves, 1):
            s = copy.deepcopy(tmpl)
            s.set("Plt", str(c.get("plot", n)))
            s.set("AliasID", str(n))
            s.set("XExp", c.get("x", default_x))
            s.set("YExp", c["y"])
            for axis in ("x", "y"):                              # scale: (low, high) or "auto"; log scale; grid spacing
                rng = c.get(f"{axis}range")
                if rng is not None:
                    s.set(f"{axis.upper()}Rng", "AutoAlways" if rng == "auto" else f"{rng[1]:g},{rng[0]:g}")
                if c.get(f"{axis}grid") is not None:
                    s.set(f"Range Grid {axis.upper()}", f"{c[f'{axis}grid']:g}")
                if f"{axis}log" in c:
                    opts = [o for o in (s.get("Options") or "").split(",") if o and o != f"LINEAR{axis.upper()}"]
                    s.set("Options", ",".join(opts + ([] if c[f"{axis}log"] else [f"LINEAR{axis.upper()}"])))
            if c.get("color"):
                s.set("Line Color", c["color"])
                s.set("Text Color", c["color"])
            new.append(s)
        pos = idx[0]
        for i in reversed(idx):
            del self.sections[i]
        self.sections[pos:pos] = new

    def enable_output(self, analysis: str) -> None:
        """Numeric output: add OUTPUT to every curve's Options."""
        for i in self.waveform_indices(analysis):
            s = self.sections[i]
            opts = [o for o in (s.get("Options") or "").split(",") if o]
            if "OUTPUT" not in opts:
                s.set("Options", ",".join(["OUTPUT"] + opts))

    def summary(self) -> dict:
        analyses = {}
        for s in self.sections:
            if s.name == "Limits" and s.get("Analysis"):
                analyses[s.get("Analysis")] = {
                    "limits": dict(ln.split("=", 1) for ln in s.lines if "=" in ln),
                    "curves": self.waveforms(s.get("Analysis")),
                }
        comps = [{"part": c["attrs"].get("PART"), "type": c["type"],
                  "attrs": {k: v for k, v in c["attrs"].items() if k != "PART"}}
                 for c in self.components() if "PART" in c["attrs"]]
        return {"components": comps, "analyses": analyses}
