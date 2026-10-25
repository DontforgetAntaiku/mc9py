"""Parse MC9 numeric output (.TNO/.ANO/.DNO)."""
from __future__ import annotations

import re

EXT = {"transient": "TNO", "ac": "ANO", "dc": "DNO", "distortion": "WNO"}
_SI = {"a": 1e-18, "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3,
       "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12}
_NUM = re.compile(r"^([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)(Meg|MEG|[afpnumkKMGT])?$")


def parse_value(tok: str) -> float | None:
    if tok.upper() in ("N/A", "NAN", "-NAN"):
        return float("nan")
    m = _NUM.match(tok)
    if not m:
        return None
    v = float(m.group(1))
    suf = m.group(2)
    if suf:
        v *= 1e6 if suf.lower() == "meg" else _SI[suf]
    return v


def read_text(path: str) -> str:
    with open(path, "rb") as f:
        return f.read().decode("cp1251", errors="replace")


def parse_waveforms(text: str) -> list[dict]:
    """Return a list of tables: {"columns": [...], "units": [...], "rows": [[float,...],...]}."""
    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    tables = []
    i = 0
    header = ""                                   # "Temperature=25 R1=1K": which stepped run the next table belongs to
    while i < len(lines):
        if lines[i].startswith("Temperature="):
            header = lines[i].strip()
        if lines[i].strip() == "Waveform Values":
            j = i + 2  # skip ====
            while j < len(lines) and not lines[j].strip():
                j += 1
            cols = lines[j].split()
            units = lines[j + 1].split() if j + 1 < len(lines) else []
            rows = []
            k = j + 2
            while k < len(lines):
                toks = lines[k].split()
                if not toks:
                    break
                vals = [parse_value(t) for t in toks]
                if None in vals or len(vals) != len(cols):
                    break
                rows.append(vals)
                k += 1
            label = header
            if not label:
                for back in range(i - 1, max(i - 12, -1), -1):
                    t = lines[back].strip()
                    if t and not set(t) <= set("*=-") and "=" in t and not t.startswith("***"):
                        label = t
                        break
            tables.append({"columns": cols, "units": units, "rows": rows, "label": label})
            i = k
        else:
            i += 1
    return tables


def parse_op(text: str) -> dict:
    """Operating point from any numeric output: {'nodes': {name: V}, 'devices': {inst: {param: value}}}."""
    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    nodes: dict[str, float] = {}
    devices: dict[str, dict[str, float]] = {}
    mode, insts = None, []
    i = 0
    while i < len(lines):
        ln = lines[i]
        st = ln.strip()
        if st == "DC Operating Point Voltages":
            mode = "nodes"; i += 3; continue
        if ln.startswith("Operating point for devices of type"):
            mode, insts = "dev", []; i += 2; continue
        if st == "Waveform Values" or ln.startswith("*****") or ln.startswith("Temperature="):
            mode = None
        if mode == "nodes" and st:
            t = st.split()
            for k in range(0, len(t) - 1, 2):
                v = parse_value(t[k + 1])
                if v is not None:
                    nodes[t[k]] = v
        elif mode == "dev" and st:
            if ln.startswith("Instance:"):
                insts = ln.split()[1:]
                for n in insts:
                    devices.setdefault(n, {})
            elif insts and not st.endswith(":") and not ln.startswith("Using"):
                t = st.split()
                if len(t) == len(insts) + 1:
                    for n, tok in zip(insts, t[1:]):
                        v = parse_value(tok.rstrip("(*)"))
                        if v is not None:
                            devices[n][t[0]] = v
        i += 1
    return {"nodes": nodes, "devices": devices}
