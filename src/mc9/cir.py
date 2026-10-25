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

    # ---- analyses ---------------------------------------------------
    def limits(self, analysis: str) -> Section:
        for s in self.sections:
            if s.name == "Limits" and (s.get("Analysis") or "").lower() == analysis.lower():
                return s
        raise KeyError(f"no [Limits] for analysis {analysis!r}")

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
