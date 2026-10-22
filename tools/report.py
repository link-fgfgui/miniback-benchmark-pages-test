#!/usr/bin/env python3
"""Render a study directory into report.html and report.md.

Reads study.json plus one CSV set per run (versions/families/regions/changes/skipped).
Everything is inline SVG and inline CSS: the HTML works offline and can be shipped alone.
"""
from __future__ import annotations

import csv
import gzip
import html
import lzma
import json
import math
import re
import statistics
import sys
from pathlib import Path

# ---------------------------------------------------------------- formatting

INK = "#1b2430"
MUTED = "#6c7888"
GRID = "#e5eaf0"
ACCENT = "#2f6df6"
GREEN = "#0f9d68"
AMBER = "#e08a00"
RED = "#d93a41"
PURPLE = "#7b5cff"
TEAL = "#0c8f9e"
SERIES = [ACCENT, GREEN, AMBER, RED, PURPLE, TEAL]
BT = chr(96)  # backtick, kept out of string literals so this file stays shell-safe


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def mb(value, digits=2) -> str:
    value = num(value)
    if abs(value) >= 1e12:
        return f"{value / 1e12:.{digits}f} TB"
    if abs(value) >= 1e9:
        return f"{value / 1e9:.{digits}f} GB"
    if abs(value) >= 1e6:
        return f"{value / 1e6:.{digits}f} MB"
    if abs(value) >= 1e3:
        return f"{value / 1e3:.{digits}f} kB"
    return f"{value:.0f} B"


def mb_num(value) -> float:
    return num(value) / 1e6


def pct(a, b, digits=2) -> str:
    b = num(b)
    return "n/a" if b == 0 else f"{100.0 * num(a) / b:.{digits}f}%"


def count(value) -> str:
    return f"{int(num(value)):,}"


def short_label(label: str) -> str:
    match = re.search(r"(\d{4})(\d{2})(\d{2})-?(\d{2})(\d{2})(\d{2})", label)
    if match:
        return (f"{match.group(2)}-{match.group(3)} "
                f"{match.group(4)}:{match.group(5)}")
    return label if len(label) <= 18 else label[:17] + "..."


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else "..." + text[-(limit - 3):]


def file_label(path: str) -> str:
    """Compact a world-relative path for a rotated heatmap column label."""
    parts = [p for p in path.split("/")
             if p not in ("region", "entities", "poi", "dimensions")]
    if len(parts) > 2:
        parts = parts[-2:]
    return truncate("/".join(parts), 24)


def nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    exponent = 10 ** int(math.floor(math.log10(value)))
    for factor in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if value <= factor * exponent:
            return factor * exponent
    return 10 * exponent


def label_step(n: int, max_labels: int = 14) -> int:
    return max(1, (n + max_labels - 1) // max_labels)


def sample_indices(n: int, limit: int) -> list[int]:
    """Evenly spaced indices, always keeping the first and last point."""
    if n <= limit or limit < 2:
        return list(range(n))
    step = (n - 1) / (limit - 1)
    picked = sorted({round(i * step) for i in range(limit)})
    picked[0], picked[-1] = 0, n - 1
    return picked


def downsample(labels: list[str], series: list[dict], limit: int) -> tuple[list[str], list[dict]]:
    if len(labels) <= limit:
        return labels, series
    idx = sample_indices(len(labels), limit)
    return ([labels[i] for i in idx],
            [{**item, "values": [item["values"][i] for i in idx]} for item in series])


# ---------------------------------------------------------------- svg charts

def _svg_open(width: int, height: int, title: str) -> list[str]:
    return [
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" '
        f'aria-label="{esc(title)}" xmlns="http://www.w3.org/2000/svg">',
        f'<title>{esc(title)}</title>',
        '<style>'
        f'.axis{{stroke:{GRID};stroke-width:1}}'
        f'.tick{{fill:{MUTED};font:11px ui-monospace,SFMono-Regular,Menlo,monospace}}'
        f'.lbl{{fill:{INK};font:11.5px ui-sans-serif,system-ui,sans-serif}}'
        f'.grid{{stroke:{GRID};stroke-width:1;stroke-dasharray:2 3}}'
        '.bar:hover,.dot:hover{opacity:.78}'
        f'.legend{{fill:{INK};font:11.5px ui-sans-serif,system-ui,sans-serif}}'
        '</style>',
    ]


def _legend(x: int, y: int, series: list[dict], gap: int = 150) -> list[str]:
    out = []
    for i, item in enumerate(series):
        cx = x + i * gap
        dash = ' stroke-dasharray="5 3"' if item.get("dash") else ""
        out.append(f'<line x1="{cx}" y1="{y - 4}" x2="{cx + 15}" y2="{y - 4}" '
                   f'stroke="{item["color"]}" stroke-width="2.5"{dash}/>')
        out.append(f'<text class="legend" x="{cx + 21}" y="{y}">{esc(item["name"])}</text>')
    return out


def line_chart(labels: list[str], series: list[dict], *, height: int = 330,
               y_fmt=lambda v: f"{v:,.0f}", y_title: str = "", log: bool = False,
               width: int = 980, max_points: int = 260) -> str:
    labels, series = downsample(labels, series, max_points)
    left, right, top, bottom = 74, 22, 34, 56
    pw, ph = width - left - right, height - top - bottom
    n = max(1, len(labels))
    values = [v for s in series for v in s["values"]]
    vmax = max(values) if values else 1
    if log:
        positives = [v for v in values if v > 0]
        floor = min(positives) if positives else 1
        lo = 10 ** math.floor(math.log10(floor))
        hi = 10 ** math.ceil(math.log10(max(vmax, lo)))
        if hi == lo:
            hi = lo * 10
        ticks = []
        exp = math.log10(lo)
        while 10 ** exp <= hi * 1.0001:
            ticks.append(10 ** exp)
            exp += 1
        span = math.log10(hi) - math.log10(lo)
        ymap = lambda v: top + ph - (math.log10(max(v, lo)) - math.log10(lo)) / span * ph \
            if v > 0 else top + ph
    else:
        hi = nice_max(vmax * 1.05)
        ticks = [hi * i / 4 for i in range(5)]
        ymap = lambda v: top + ph - v / hi * ph if hi > 0 else top + ph

    def xmap(i: int) -> float:
        return left + (pw / 2 if n == 1 else i * pw / (n - 1))

    out = _svg_open(width, height, y_title or "chart")
    out += _legend(left, 16, series)
    for tick in ticks:
        y = ymap(tick)
        out.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + pw}" y2="{y:.1f}"/>')
        out.append(f'<text class="tick" x="{left - 8}" y="{y + 4:.1f}" '
                   f'text-anchor="end">{esc(y_fmt(tick))}</text>')
    out.append(f'<line class="axis" x1="{left}" y1="{top + ph}" '
               f'x2="{left + pw}" y2="{top + ph}"/>')
    step = label_step(n)
    for i, label in enumerate(labels):
        if i % step and i != n - 1:
            continue
        out.append(f'<text class="tick" x="{xmap(i):.1f}" y="{top + ph + 20}" '
                   f'text-anchor="middle">{esc(short_label(label))}</text>')
    for item in series:
        points = " ".join(f"{xmap(i):.1f},{ymap(v):.1f}" for i, v in enumerate(item["values"]))
        if item.get("area"):
            out.append(f'<polygon points="{xmap(0):.1f},{top + ph} {points} '
                       f'{xmap(n - 1):.1f},{top + ph}" fill="{item["color"]}" opacity=".08"/>')
        dash = ' stroke-dasharray="6 4"' if item.get("dash") else ""
        out.append(f'<polyline points="{points}" fill="none" stroke="{item["color"]}" '
                   f'stroke-width="2.2"{dash} stroke-linejoin="round"/>')
        for i, v in enumerate(item["values"]):
            out.append(f'<circle class="dot" cx="{xmap(i):.1f}" cy="{ymap(v):.1f}" r="3.2" '
                       f'fill="#fff" stroke="{item["color"]}" stroke-width="2">'
                       f'<title>{esc(item["name"])}: {esc(y_fmt(v))}</title></circle>')
    if y_title:
        out.append(f'<text class="tick" x="{left}" y="{height - 10}">{esc(y_title)}</text>')
    out.append("</svg>")
    return "".join(out)


def bar_chart(labels: list[str], series: list[dict], *, height: int = 330,
              y_fmt=lambda v: f"{v:,.0f}", y_title: str = "", log: bool = False,
              width: int = 980, overlay: dict | None = None, max_points: int = 260) -> str:
    labels, series = downsample(labels, series, max_points)
    if overlay and overlay.get("values"):
        if len(overlay["values"]) != len(labels):
            idx = sample_indices(len(overlay["values"]), max_points)
            overlay = {**overlay, "values": [overlay["values"][i] for i in idx]}
    left, right, top, bottom = 74, 48, 34, 56
    pw, ph = width - left - right, height - top - bottom
    n = max(1, len(labels))
    values = [v for s in series for v in s["values"]]
    vmax = max(values) if values else 1
    if log:
        positives = [v for v in values if v > 0]
        floor = min(positives) if positives else 1
        lo = 10 ** math.floor(math.log10(floor))
        hi = 10 ** math.ceil(math.log10(max(vmax, lo)))
        if hi == lo:
            hi = lo * 10
        ticks = []
        exp = math.log10(lo)
        while 10 ** exp <= hi * 1.0001:
            ticks.append(10 ** exp)
            exp += 1
        span = math.log10(hi) - math.log10(lo)
        ymap = lambda v: top + ph - ((math.log10(max(v, lo)) - math.log10(lo)) / span) * ph \
            if v > 0 else top + ph
    else:
        hi = nice_max(vmax * 1.05)
        ticks = [hi * i / 4 for i in range(5)]
        ymap = lambda v: top + ph - v / hi * ph if hi > 0 else top + ph

    step = label_step(n)
    band = pw / n
    out = _svg_open(width, height, y_title or "chart")
    out += _legend(left, 16, series)
    for tick in ticks:
        y = ymap(tick)
        out.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + pw}" y2="{y:.1f}"/>')
        out.append(f'<text class="tick" x="{left - 8}" y="{y + 4:.1f}" '
                   f'text-anchor="end">{esc(y_fmt(tick))}</text>')
    out.append(f'<line class="axis" x1="{left}" y1="{top + ph}" '
               f'x2="{left + pw}" y2="{top + ph}"/>')
    for i, label in enumerate(labels):
        if i % step and i != n - 1:
            continue
        out.append(f'<text class="tick" x="{left + band * (i + .5):.1f}" y="{top + ph + 20}" '
                   f'text-anchor="middle">{esc(short_label(label))}</text>')
    groups = max(1, len(series))
    for gi, item in enumerate(series):
        bar_w = max(2.0, band * 0.72 / groups)
        for i, v in enumerate(item["values"]):
            x = left + band * i + band * 0.14 + gi * bar_w
            y = ymap(v)
            h = max(0.0, top + ph - y)
            out.append(f'<rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{bar_w - 1:.1f}" '
                       f'height="{h:.1f}" rx="2" fill="{item["color"]}">'
                       f'<title>{esc(item["name"])} - {esc(labels[i])}: '
                       f'{esc(y_fmt(v))}</title></rect>')
    if overlay and overlay.get("values"):
        values2 = overlay["values"]
        ohi = max(values2) if max(values2) > 0 else 1
        oy = lambda v: top + ph - (v / ohi) * ph * 0.92
        pts = " ".join(f"{left + band * (i + .5):.1f},{oy(v):.1f}"
                       for i, v in enumerate(values2))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{overlay["color"]}" '
                   f'stroke-width="2" stroke-dasharray="5 3"/>')
        for i, v in enumerate(values2):
            out.append(f'<circle cx="{left + band * (i + .5):.1f}" cy="{oy(v):.1f}" r="2.6" '
                       f'fill="{overlay["color"]}"><title>{esc(overlay["name"])}: '
                       f'{esc(overlay["fmt"](v))}</title></circle>')
        out.append(f'<text class="tick" x="{left + pw}" y="{top + 10}" text-anchor="end" '
                   f'fill="{overlay["color"]}">- {esc(overlay["name"])}</text>')
    if y_title:
        out.append(f'<text class="tick" x="{left}" y="{height - 10}">{esc(y_title)}</text>')
    out.append("</svg>")
    return "".join(out)


def stacked_bars(labels: list[str], series: list[dict], *, height: int = 330,
                 y_fmt=lambda v: f"{v:,.1f}", y_title: str = "", width: int = 980,
                 max_points: int = 260) -> str:
    labels, series = downsample(labels, series, max_points)
    left, right, top, bottom = 74, 22, 34, 56
    pw, ph = width - left - right, height - top - bottom
    n = max(1, len(labels))
    totals = [sum(s["values"][i] for s in series) for i in range(n)]
    hi = nice_max(max(totals) * 1.05)
    ticks = [hi * i / 4 for i in range(5)]
    band = pw / n
    ymap = lambda v: top + ph - v / hi * ph
    step = label_step(n)
    out = _svg_open(width, height, y_title or "chart")
    out += _legend(left, 16, series)
    for tick in ticks:
        y = ymap(tick)
        out.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + pw}" y2="{y:.1f}"/>')
        out.append(f'<text class="tick" x="{left - 8}" y="{y + 4:.1f}" '
                   f'text-anchor="end">{esc(y_fmt(tick))}</text>')
    for i, label in enumerate(labels):
        if i % step and i != n - 1:
            continue
        out.append(f'<text class="tick" x="{left + band * (i + .5):.1f}" y="{top + ph + 20}" '
                   f'text-anchor="middle">{esc(short_label(label))}</text>')
    for i in range(n):
        acc = 0.0
        for item in series:
            v = item["values"][i]
            if v <= 0:
                continue
            y0 = ymap(acc)
            y1 = ymap(acc + v)
            out.append(f'<rect class="bar" x="{left + band * i + band * .16:.1f}" y="{y1:.1f}" '
                       f'width="{band * .68:.1f}" height="{max(0.0, y0 - y1):.1f}" '
                       f'fill="{item["color"]}"><title>{esc(labels[i])} - {esc(item["name"])}: '
                       f'{esc(y_fmt(v))}</title></rect>')
            acc += v
    out.append(f'<line class="axis" x1="{left}" y1="{top + ph}" '
               f'x2="{left + pw}" y2="{top + ph}"/>')
    if y_title:
        out.append(f'<text class="tick" x="{left}" y="{height - 10}">{esc(y_title)}</text>')
    out.append("</svg>")
    return "".join(out)


def heatmap(rows: list[str], cols: list[str], matrix: list[list[float]], *,
            width: int = 980, title: str = "", max_rows: int = 170) -> str:
    row_count = len(rows)
    if row_count > max_rows:
        idx = sample_indices(row_count, max_rows)
        rows = [rows[i] for i in idx]
        matrix = [matrix[i] for i in idx]
    left, top, right, bottom = 104, 118, 56, 30
    cell_w = max(10.0, (width - left - right) / max(1, len(cols)))
    cell_h = 20.0
    height = int(top + bottom + cell_h * max(1, len(rows)))
    # The baseline row is a full write, so it would flatten the colour scale for every later
    # snapshot. Scale on the diff rows and use a log ramp.
    scale_rows = matrix[1:] if len(matrix) > 1 else matrix
    vmax = max((v for row in scale_rows for v in row), default=1) or 1
    ramp = math.log1p(vmax)

    def color(v: float) -> str:
        t = math.log1p(v) / ramp if v > 0 else 0.0
        if v <= 0:
            return "#f4f6f9"
        r = int(235 + (30 - 235) * t)
        g = int(242 + (109 - 242) * t)
        b = int(248 + (246 - 248) * t)
        return f"rgb({r},{g},{b})"

    out = _svg_open(width, height, title or "heatmap")
    for j, col in enumerate(cols):
        x = left + j * cell_w + cell_w / 2
        out.append(f'<text class="tick" transform="translate({x:.1f},{top - 10}) rotate(-60)" '
                   f'text-anchor="start" style="font-size:9.5px">'
                   f'{esc(file_label(col))}<title>{esc(col)}</title></text>')
    for i, row in enumerate(rows):
        y = top + i * cell_h
        out.append(f'<text class="tick" x="{left - 10}" y="{y + 13:.1f}" '
                   f'text-anchor="end">{esc(short_label(row))}</text>')
        for j, v in enumerate(matrix[i]):
            out.append(f'<rect x="{left + j * cell_w:.1f}" y="{y:.1f}" '
                       f'width="{cell_w - 1:.1f}" height="{cell_h - 1:.1f}" rx="1.5" '
                       f'fill="{color(v)}"><title>{esc(row)} / {esc(cols[j])}: '
                       f'{int(v):,}</title></rect>')
    out.append(f'<text class="tick" x="{left}" y="{top + len(rows) * cell_h + 20}" '
               f'text-anchor="start">changed + new targets per file (log colour); '
               f'darkest diff cell = {int(vmax):,}</text>')
    out.append("</svg>")
    return "".join(out)


def horizontal_bars(labels: list[str], values: list[float], *, width: int = 980,
                    height_per_row: int = 30, fmt=mb, color: str = ACCENT,
                    highlight: int | None = None) -> str:
    left, right, top = 300, 190, 10
    height = top + height_per_row * len(labels) + 10
    vmax = max(values) if values else 1
    out = _svg_open(width, height, "comparison")
    for i, (label, value) in enumerate(zip(labels, values)):
        y = top + i * height_per_row
        w = (value / vmax) * (width - left - right) if vmax else 0
        fill = ACCENT if highlight is None or i == highlight else "#9db4dc"
        out.append(f'<text class="lbl" x="{left - 10}" y="{y + height_per_row * .62:.0f}" '
                   f'text-anchor="end">{esc(label)}</text>')
        out.append(f'<rect x="{left}" y="{y + 5}" width="{max(1, w):.1f}" '
                   f'height="{height_per_row - 14}" rx="3" fill="{fill}">'
                   f'<title>{esc(label)}: {esc(fmt(value))}</title></rect>')
        out.append(f'<text class="tick" x="{left + max(1, w) + 8:.1f}" '
                   f'y="{y + height_per_row * .62:.0f}">{esc(fmt(value))}</text>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- data loading

def read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def field(row: dict, *names, default="0") -> str:
    for name in names:
        if name in row and row[name] != "":
            return row[name]
    return default


class Run:
    def __init__(self, entry: dict, root: Path):
        self.id = entry["id"]
        self.level = int(entry.get("level", 0))
        self.long = bool(entry.get("long", False))
        self.dir = root / entry.get("dir", self.id)
        self.elapsed_ms = int(entry.get("elapsed_ms", 0))
        self.versions = read_csv(self.dir / "versions.csv")
        self.families = read_csv(self.dir / "families.csv")
        self.regions_path = self.dir / "regions.csv"
        self.changes_path = self.dir / "changes.csv"
        self.changes_comp = "plain"
        if not self.changes_path.is_file() and (self.dir / "changes.csv.gz").is_file():
            self.changes_path = self.dir / "changes.csv.gz"
            self.changes_comp = "gz"
        elif not self.changes_path.is_file() and (self.dir / "changes.csv.xz").is_file():
            self.changes_path = self.dir / "changes.csv.xz"
            self.changes_comp = "xz"
        self.skipped_path = self.dir / "skipped.csv"
        self.labels = [row["version"] for row in self.versions]

    @property
    def name(self) -> str:
        return f"zstd L{self.level} / {'long' if self.long else 'default'}"

    def series(self, *names) -> list[float]:
        return [num(field(row, *names)) for row in self.versions]

    @property
    def source(self) -> list[float]:
        return self.series("source_bytes", "archive_bytes")

    @property
    def full(self) -> list[float]:
        return self.series("actual_full_total", "full_total")

    @property
    def incr(self) -> list[float]:
        return self.series("actual_incr_total", "incr_total")

    @property
    def vault(self) -> list[float]:
        return self.series("actual_cumulative_min", "cumulative_min")

    @property
    def vault_source(self) -> list[float]:
        return self.series("cumulative_source", "cumulative_rewind")

    def summary(self) -> dict:
        incr = self.incr
        later = incr[1:]
        return {
            "vault": self.vault[-1] if self.vault else 0,
            "source": self.vault_source[-1] if self.vault_source else 0,
            "last_full": self.full[-1] if self.full else 0,
            "first_full": self.full[0] if self.full else 0,
            "sum_incr": sum(incr),
            "median_incr": statistics.median(later) if later else 0,
            "max_incr": max(later) if later else 0,
            "last_incr": incr[-1] if incr else 0,
            "time_ms": sum(num(row.get("total_ms")) for row in self.versions),
            "failures": sum(num(row.get("roundtrip_fail")) for row in self.versions),
            "skipped": sum(num(row.get("skipped_targets")) for row in self.versions),
        }

    def family_totals(self) -> dict:
        out = {}
        last = self.labels[-1] if self.labels else None
        for row in self.families:
            family = row.get("family", "?")
            stats = out.setdefault(family, {"targets": 0, "full": 0, "delta": 0,
                                            "new_full": 0, "incr": 0})
            if row.get("version") == last:
                stats["targets"] = num(row.get("targets"))
                stats["full"] = num(row.get("full_payload"))
                stats["delta"] = num(row.get("delta_payload"))
            stats["new_full"] += num(row.get("new_full_payload"))
            stats["incr"] += num(row.get("incr_total"))
        return out

    def family_series(self, family: str, column: str) -> list[float]:
        index = {row["version"]: row for row in self.families if row.get("family") == family}
        return [num(index[label].get(column)) if label in index else 0 for label in self.labels]

    def top_deltas(self, limit: int = 10) -> list[dict]:
        """Aggregate DELTA rows without keeping the (possibly huge) change log in memory."""
        if not self.changes_path.is_file():
            return []
        totals: dict[str, dict] = {}
        opener = {"gz": gzip.open, "xz": lzma.open}.get(self.changes_comp, open)
        with opener(self.changes_path, "rt", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("mode") != "DELTA":
                    continue
                key = row.get("key", "")
                entry = totals.setdefault(key, {"key": key, "family": row.get("family", ""),
                                                "count": 0, "full": 0.0, "delta": 0.0})
                entry["count"] += 1
                entry["full"] += num(row.get("full_bytes"))
                entry["delta"] += num(row.get("delta_bytes"))
        rows = sorted(totals.values(), key=lambda row: row["delta"], reverse=True)
        return rows[:limit]

    def heatmap_data(self, top_n: int = 18):
        """Two streaming passes: rank files, then collect the matrix for the busiest ones."""
        if not self.regions_path.is_file():
            return [], [], []
        totals: dict[str, float] = {}
        with self.regions_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                path = row.get("file", "")
                totals[path] = totals.get(path, 0.0) + num(row.get("changed")) + num(row.get("new"))
        top = [path for path, _ in sorted(totals.items(), key=lambda kv: kv[1],
                                          reverse=True)[:top_n]]
        if not top:
            return [], [], []
        keep = set(top)
        matrix_map: dict[tuple[str, str], float] = {}
        with self.regions_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                path = row.get("file", "")
                if path in keep:
                    matrix_map[(row.get("version", ""), path)] = (
                        num(row.get("changed")) + num(row.get("new")))
        matrix = [[matrix_map.get((label, path), 0.0) for path in top] for label in self.labels]
        return self.labels, top, matrix

    def skipped_counts(self) -> list[tuple[str, int]]:
        if not self.skipped_path.is_file():
            return []
        counts: dict[str, int] = {}
        with self.skipped_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                reason = row.get("reason", "?")
                counts[reason] = counts.get(reason, 0) + 1
        return sorted(counts.items(), key=lambda kv: -kv[1])


# ---------------------------------------------------------------- html blocks

def kpi(label: str, value: str, note: str = "", tone: str = "") -> str:
    return (f'<div class="kpi {tone}"><div class="kpi-label">{esc(label)}</div>'
            f'<div class="kpi-value">{esc(value)}</div>'
            f'<div class="kpi-note">{esc(note)}</div></div>')


def card(title: str, body: str, note: str = "") -> str:
    note_html = f'<p class="note">{note}</p>' if note else ""
    return f'<section class="card"><h2>{esc(title)}</h2>{body}{note_html}</section>'


def render_table(headers: list[str], rows: list[list[str]], *,
                 numeric_from: int = 0) -> str:
    head = "".join(f'<th class="{"num" if i >= numeric_from else ""}">{esc(h)}</th>'
                   for i, h in enumerate(headers))
    body = []
    for row in rows:
        cells = "".join(f'<td class="{"num" if i >= numeric_from else ""}">{cell}</td>'
                        for i, cell in enumerate(row))
        body.append(f"<tr>{cells}</tr>")
    return (f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def bar_cell(value: float, peak: float, text: str) -> str:
    width = 0 if peak <= 0 else max(0.02, min(1.0, value / peak))
    return (f'<div class="barcell"><span class="bar" style="width:{width * 100:.1f}%"></span>'
            f'<span class="bartext">{esc(text)}</span></div>')


# ---------------------------------------------------------------- report

def build(study_dir: Path) -> tuple[str, str]:
    study = json.loads((study_dir / "study.json").read_text(encoding="utf-8"))
    runs = [Run(entry, study_dir) for entry in study.get("runs", [])]
    runs = [run for run in runs if run.versions]
    if not runs:
        raise SystemExit("no run with versions.csv found")
    primary = runs[0]
    labels = primary.labels
    s = primary.summary()
    env = study.get("environment", {})
    dataset = study.get("dataset", {})
    git = dataset if dataset.get("kind") == "git" else None
    repo_bytes = num(dataset.get("repo_bytes")) if git else 0
    source_total = dataset.get("total_source_bytes") or s["source"]

    mb_series = lambda values: [mb_num(v) for v in values]
    ratio = lambda a, b: 100.0 * a / b if b else 0.0
    incr_peak = max(mb_series(primary.incr)[1:] or [1])

    later = primary.incr[1:]
    peak_index = max(range(1, len(labels)), key=lambda i: primary.incr[i]) if later else 0
    peak_row = primary.versions[peak_index] if primary.versions else {}
    baseline = primary.incr[0] if primary.incr else 0
    if git:
        first_finding = (
            f"The vault holds all {len(labels)} restore points in <b>{mb(s['vault'])}</b>: "
            f"{ratio(s['vault'], source_total):.2f}% of the {mb(source_total)} of uncompressed "
            f"working trees, {pct(s['vault'], repo_bytes)} of the {mb(repo_bytes)} git "
            f"repository, and {num(s['vault']) / max(1, s['last_full']):.2f}x one full snapshot."
        )
    else:
        first_finding = (
            f"The vault holds all {len(labels)} restore points in <b>{mb(s['vault'])}</b>: "
            f"{ratio(s['vault'], source_total):.2f}% of the {mb(source_total)} it would cost to "
            f"keep one full copy per point, and "
            f"{num(s['vault']) / max(1, s['last_full']):.2f}x a single full snapshot."
        )
    findings = [
        first_finding,
        f"The baseline wrote <b>{mb(baseline)}</b> "
        f"({ratio(baseline, s['vault']):.1f}% of the vault); the other {len(labels) - 1} "
        f"restore points added {mb(s['sum_incr'] - baseline)} in total.",
        f"Median append after the baseline is <b>{mb(s['median_incr'])}</b> "
        f"({pct(s['median_incr'], s['last_full'])} of a full snapshot). The largest is "
        f"snapshot {peak_index + 1} ({esc(peak_row.get('version', ''))}) at "
        f"{mb(primary.incr[peak_index] if primary.incr else 0)}, with "
        f"{count(peak_row.get('new'))} new and {count(peak_row.get('changed'))} changed "
        f"targets.",
    ]
    if len(runs) > 1:
        best = min(runs, key=lambda run: run.summary()["vault"])
        best_vault = best.summary()["vault"]
        findings.append(
            f"Smallest vault across {len(runs)} configurations: <b>{best.name}</b> at "
            f"{mb(best_vault)} ({pct(best_vault, s['vault'])} of the primary "
            f"{primary.name} vault).")
    findings.append(
        "All FULL and DELTA blocks round-tripped byte-for-byte."
        if s["failures"] == 0 else
        f"<b>{int(s['failures'])} round-trip failures</b> — results are not trustworthy.")
    findings_html = '<ul class="findings">' + "".join(
        f"<li>{item}</li>" for item in findings) + "</ul>"

    if git:
        kpis = [
            kpi("Vault after all commits", mb(s["vault"]),
                f"{len(labels)} restore points", "big"),
            kpi("Full working trees", mb(source_total),
                "uncompressed checkout per commit"),
            kpi("Vault / full trees", f"{ratio(s['vault'], source_total):.2f}%",
                f"{source_total / s['vault']:.1f}x smaller" if s["vault"] else "n/a", "good"),
            kpi("Git repository on disk", mb(repo_bytes), "all commits, packed"),
            kpi("Vault / git repository", pct(s["vault"], repo_bytes),
                f"{repo_bytes / s['vault']:.2f}x the vault" if s["vault"] else "n/a",
                "good" if repo_bytes > s["vault"] else ""),
            kpi("Vault / last full snapshot",
                f"{num(s['vault']) / s['last_full']:.3f}x" if s["last_full"] else "n/a",
                f"last full = {mb(s['last_full'])}"),
            kpi("Median append", mb(s["median_incr"]), "per commit after baseline"),
            kpi("Correctness", f"{int(s['failures'])} failures",
                f"{int(s['skipped'])} skipped targets",
                "good" if s["failures"] == 0 else "bad"),
        ]
    else:
        kpis = [
            kpi("Vault after all snapshots", mb(s["vault"]),
                f"{len(labels)} restore points", "big"),
            kpi("Full copies on disk", mb(source_total), "one complete save per point"),
            kpi("Vault / full copies", f"{ratio(s['vault'], source_total):.2f}%",
                f"{source_total / s['vault']:.1f}x smaller" if s["vault"] else "n/a", "good"),
            kpi("Vault / last full snapshot",
                f"{num(s['vault']) / s['last_full']:.3f}x" if s["last_full"] else "n/a",
                f"last full = {mb(s['last_full'])}"),
            kpi("Median append", mb(s["median_incr"]), "per snapshot after baseline"),
            kpi("Correctness", f"{int(s['failures'])} failures",
                f"{int(s['skipped'])} skipped targets",
                "good" if s["failures"] == 0 else "bad"),
        ]

    last_full = s["last_full"] or 1
    storage_series = [
        {"name": "Vault (engine)", "values": [v / last_full for v in primary.vault],
         "color": ACCENT, "area": True},
        {"name": "One full snapshot", "values": [1.0 for _ in labels], "color": GREEN,
         "dash": True},
    ]
    if git:
        if repo_bytes:
            storage_series.append({"name": "Git repository (.git)",
                                   "values": [repo_bytes / last_full for _ in labels],
                                   "color": PURPLE, "dash": True})
    else:
        storage_series.insert(0, {"name": "Full copy per snapshot",
                                  "values": [v / last_full for v in primary.vault_source],
                                  "color": AMBER, "dash": True})
    cumulative = line_chart(
        labels, storage_series,
        y_fmt=lambda v: f"{v:.1f}x", y_title="storage in units of one full snapshot "
                                             f"({mb(last_full)})", height=350)

    overlay = {
        "name": "% of a full snapshot",
        "values": [100.0 * num(field(row, "actual_incr_total", "incr_total")) /
                   max(1.0, num(field(row, "actual_full_total", "full_total")))
                   for row in primary.versions],
        "color": RED, "fmt": lambda v: f"{v:.2f}%",
    }
    increments = bar_chart(
        labels,
        [{"name": "Append per snapshot", "values": mb_series(primary.incr), "color": ACCENT}],
        y_fmt=lambda v: f"{v:,.2f}" if v < 10 else f"{v:,.0f}", log=True,
        y_title="MB appended (log scale); dashed line = append / full snapshot",
        overlay=overlay, height=350)

    composition = stacked_bars(
        labels[1:],
        [
            {"name": "New-target FULL", "color": ACCENT,
             "values": mb_series(primary.series("new_full_payload"))[1:]},
            {"name": "Changed-target DELTA", "color": GREEN,
             "values": mb_series(primary.series("delta_payload"))[1:]},
            {"name": "Block headers", "color": AMBER,
             "values": mb_series(primary.series("incr_headers"))[1:]},
            {"name": "Block index cache", "color": PURPLE,
             "values": mb_series(primary.series("cache_bytes"))[1:]},
        ],
        y_fmt=lambda v: f"{v:,.1f}", y_title="MB per append (baseline omitted)", height=350)

    flow = stacked_bars(
        labels,
        [
            {"name": "Changed", "color": GREEN, "values": primary.series("changed")},
            {"name": "New", "color": ACCENT, "values": primary.series("new")},
            {"name": "Deleted", "color": RED, "values": primary.series("deleted")},
        ],
        y_fmt=lambda v: f"{v:,.0f}", y_title="targets per snapshot", height=310)

    heat = ""
    heat_rows = 0
    heat_cols = 0
    heat_labels, heat_files, heat_matrix = primary.heatmap_data(18)
    if heat_files:
        heat_rows = len(heat_labels)
        heat_cols = len(heat_files)
        heat = heatmap(heat_labels, heat_files, heat_matrix, width=980,
                       title="changed and new targets per file, over time")

    family_chart = bar_chart(
        labels[1:],
        [
            {"name": "chunk", "color": ACCENT,
             "values": mb_series(primary.family_series("chunk", "incr_total"))[1:]},
            {"name": "file", "color": AMBER,
             "values": mb_series(primary.family_series("file", "incr_total"))[1:]},
        ],
        y_fmt=lambda v: f"{v:,.2f}" if v < 10 else f"{v:,.0f}", log=True,
        y_title="MB per append by target family (log scale, baseline omitted)", height=300)

    cost_rows = []
    activity_rows = []
    for i, row in enumerate(primary.versions):
        incr = num(field(row, "actual_incr_total", "incr_total"))
        cost_rows.append([
            str(i + 1), esc(row["version"]),
            mb(field(row, "source_bytes", "archive_bytes")),
            mb(field(row, "actual_full_total", "full_total")),
            bar_cell(incr, incr_peak * 1e6, mb(incr)),
            pct(field(row, "actual_incr_total", "incr_total"),
                field(row, "actual_full_total", "full_total")),
            mb(field(row, "actual_cumulative_min", "cumulative_min")),
            f"{num(row.get('total_ms')) / 1000:.2f}",
        ])
        activity_rows.append([
            str(i + 1), esc(row["version"]),
            mb(row.get("world_bytes")),
            count(row.get("targets")),
            count(row.get("new")), count(row.get("changed")), count(row.get("deleted")),
            count(row.get("unchanged")), mb(row.get("logical_bytes")),
        ])
    version_table = (
        render_table(["#", "Version", "Source", "Full snapshot", "Append", "Append/Full",
                      "Vault", "Time s"], cost_rows, numeric_from=2)
        + '<h3 class="subhead">Target activity</h3>'
        + render_table(["#", "Version", "World", "Targets", "New", "Changed", "Deleted",
                        "Unchanged", "Logical"], activity_rows, numeric_from=2))

    family_rows = []
    for family, stats in primary.family_totals().items():
        family_rows.append([
            esc(family), count(stats["targets"]), mb(stats["full"]),
            mb(stats["delta"]), pct(stats["delta"], stats["full"]),
            mb(stats["new_full"]), mb(stats["incr"]),
        ])
    family_table = render_table(
        ["Family", "Targets (last)", "Full payload (last)", "DELTA payload (last)",
         "DELTA / FULL", "NEW FULL total", "Append total"],
        family_rows, numeric_from=1)

    top_rows = []
    for row in primary.top_deltas(10):
        n = max(1, row["count"])
        avg_full = row["full"] / n
        avg_delta = row["delta"] / n
        top_rows.append([
            f'<span title="{esc(row["key"])}">'
            f'{esc(truncate(row["key"], 78))}</span>',
            esc(row["family"]),
            count(row["count"]),
            mb(avg_full), mb(avg_delta), mb(row["delta"]),
            f"{100.0 * avg_delta / avg_full:.1f}%" if avg_full else "n/a",
        ])
    top_table = render_table(
        ["Target", "Family", "Changes", "Avg FULL", "Avg DELTA", "DELTA total",
         "Avg DELTA / FULL"],
        top_rows, numeric_from=2)

    comparison_html = card(
        "Codec comparison",
        '<p class="empty">Only one configuration in this study. Re-run with '
        '<code>--levels 3,9 --long off,on</code> to compare codecs.</p>')
    if len(runs) > 1:
        rows = []
        for run in runs:
            rs = run.summary()
            rows.append([
                esc(run.name), mb(rs["first_full"]), mb(rs["last_full"]), mb(rs["vault"]),
                f"{ratio(rs['vault'], source_total):.2f}%", mb(rs["median_incr"]),
                mb(rs["sum_incr"]), f"{rs['time_ms'] / 1000:.1f}",
                str(int(rs["failures"])),
            ])
        table = render_table(
            ["Configuration", "First full", "Last full", "Vault", "Vault / copies",
             "Median append", "Sum of appends", "Time s", "Failures"],
            rows, numeric_from=1)
        chart = horizontal_bars([run.name for run in runs],
                                [run.summary()["vault"] for run in runs],
                                highlight=0, width=980)
        comparison_html = card(
            "Codec comparison", chart + table,
            "Same snapshots, different zstd settings. Byte counts are deterministic; timings "
            "are single-run wall clock.")

    skipped_html = ""
    skipped_counts = primary.skipped_counts()
    if skipped_counts:
        skipped_html = card(
            "Skipped records",
            render_table(["Reason", "Count"],
                         [[esc(k), count(v)] for k, v in skipped_counts],
                         numeric_from=1),
            "Records rejected by the engine's own Anvil/NBT validation. They are not targets.")

    argv = " ".join(study.get("argv", []))
    engine = study.get("engine", {})
    archive_method = ""
    if dataset.get("kind") == "archive":
        archive_method = f"""
    <p><b>Archive input.</b> {count(len(labels))} complete saves from
    <code>{esc(dataset.get('repo', 'mc-backups.zip'))}</code>. Source bytes are the compressed
    tar.gz member sizes, so the full-copy baseline is already compressed.</p>
    """
    git_method = ""
    if git:
        git_method = f"""
    <p><b>Git input.</b> <code>{esc(git.get('repo', ''))}</code> at
    <code>{esc(git.get('branch', ''))}</code>: {count(git.get('commits_total'))} commits,
    {count(git.get('commits_effective'))} effective and {count(git.get('commits_skipped'))}
    skipped. A commit is effective when it changes at least one file the engine tracks; commits
    that only touch README files, logs, <code>session.lock</code> or
    <code>level.dat_old</code> are skipped. Each effective commit is materialised into one live
    directory by <code>tools/git_materialize.py</code> immediately before it is scanned, and the
    preparation time is reported separately (<code>prepare_ms</code>). Source bytes are the sum
    of working-tree file sizes at that commit, i.e. an uncompressed checkout; the git repository
    size is the packed size reported by <code>git count-objects</code>. World roots:
    <code>{esc(', '.join(git.get('roots', [])))}</code>.</p>
    """
    method = f"""
    <p><b>Model.</b> Every snapshot is a complete world copy. Each is scanned into the targets
    the engine tracks: every non-empty chunk in <code>region/</code>, <code>entities/</code> and
    <code>poi/</code> <code>.mca</code> files (including custom dimensions), plus
    <code>level.dat</code>, <code>playerdata/*.dat</code> and every <code>data/</code>
    <code>.dat</code>. All {len(labels)} versions are compared with the previous one by
    canonical NBT bytes, and the checkpoint policy is replayed: the first version writes a FULL
    baseline; a changed target appends a DELTA against its previous visible block; a new target
    appends FULL + an ABSENT marker; a deleted target appends an ABSENT marker; an unchanged
    target appends nothing. Every block is decompressed and byte-compared
    (<code>roundtrip_fail</code>).</p>
    <p><b>Accounting.</b> The 42-byte block header, the per-block index cache entry and the
    28-byte per-file cache header are included. Filesystem block rounding and
    <code>index.properties</code> are not. "Full snapshot" is the cost of writing every current
    target as FULL with the same cache, i.e. what one independent full backup would cost.</p>
    <p><b>Caveats.</b> Diff is content-based, not write-capture: a target is "changed" only when
    its canonical bytes differ, so a server that rewrites identical data would append a small
    delta in production that is not charged here (the incremental numbers are a lower bound).
    Files outside the tracked NBT scope (datapacks, JSON, configs) are counted in "World" but not
    stored in the vault. Append-only, no GC or keyframes. Timings are a single warm-cache run on
    this machine, so treat them as indicative; byte counts are deterministic.</p>
    <p><b>Engine.</b> <code>{esc(engine.get('project', ''))}</code> at
    <code>{esc(str(engine.get('source_sha256', ''))[:16])}</code>...,
    {esc(engine.get('source_count', ''))} source files.</p>
    {git_method}
    {archive_method}
    <p><b>Reproduce.</b> <code>{esc(argv)}</code></p>
    """

    # ------------------------------------------------------------ markdown
    md = []
    md.append(f"# Differential backup benchmark - {study.get('name', study_dir.name)}")
    md.append("")
    md.append(f"**Created:** {study.get('created', '')}  ")
    md.append(f"**Snapshots:** {len(labels)}  ")
    if git:
        md.append(f"**Repository:** {git.get('repo', '')} at {git.get('branch', '')}  ")
        md.append(f"**Commits:** {count(git.get('commits_total'))} total, "
                  f"{count(git.get('commits_effective'))} effective, "
                  f"{count(git.get('commits_skipped'))} skipped  ")
    md.append(f"**Configuration:** {primary.name}  ")
    md.append(f"**Engine:** {BT}{engine.get('project', '')}{BT} "
              f"(sha256 {str(engine.get('source_sha256', ''))[:12]}...)  ")
    md.append(f"**Machine:** {env.get('cpu', '')}, {env.get('cores', '')} cores, "
              f"{env.get('java', '')}")
    md.append("")
    md.append("## Headline")
    md.append("")
    md.append("| Metric | Value |")
    md.append("| --- | ---: |")
    md.append(f"| Vault after {len(labels)} snapshots | **{mb(s['vault'])}** |")
    md.append(f"| Full {'working trees' if git else 'copies on disk'} | {mb(source_total)} |")
    md.append(f"| Vault / full {'trees' if git else 'copies'} | "
              f"**{ratio(s['vault'], source_total):.2f}%** |")
    if git:
        md.append(f"| Git repository on disk | {mb(repo_bytes)} |")
        md.append(f"| Vault / git repository | **{pct(s['vault'], repo_bytes)}** |")
    md.append(f"| Vault / last full snapshot | "
              f"{num(s['vault']) / s['last_full']:.3f}x |" if s["last_full"]
              else "| Vault / last full snapshot | n/a |")
    md.append(f"| Median append per snapshot | {mb(s['median_incr'])} |")
    md.append(f"| Largest append | {mb(s['max_incr'])} |")
    md.append(f"| Round-trip failures | {int(s['failures'])} |")
    md.append(f"| Skipped records | {int(s['skipped'])} |")
    md.append("")
    md.append("## Findings")
    md.append("")
    md.append(f"* Vault after {len(labels)} restore points: **{mb(s['vault'])}** "
              f"({ratio(s['vault'], source_total):.2f}% of {mb(source_total)} of "
              f"{'working trees' if git else 'full copies'}, "
              f"{pct(s['vault'], repo_bytes) + ' of the git repository, ' if git else ''}"
              f"{num(s['vault']) / max(1, s['last_full']):.2f}x one full snapshot).")
    md.append(f"* Baseline: {mb(baseline)} ({ratio(baseline, s['vault']):.1f}% of the vault); "
              f"the other {len(labels) - 1} snapshots added {mb(s['sum_incr'] - baseline)}.")
    md.append(f"* Median append after the baseline: {mb(s['median_incr'])} "
              f"({pct(s['median_incr'], s['last_full'])} of a full snapshot). Largest: "
              f"snapshot {peak_index + 1} ({esc(peak_row.get('version', ''))}) at "
              f"{mb(primary.incr[peak_index] if primary.incr else 0)}.")
    if len(runs) > 1:
        md.append(f"* Smallest vault: {best.name} at {mb(best_vault)} "
                  f"({pct(best_vault, s['vault'])} of {primary.name}).")
    md.append("")
    md.append("## Per-snapshot results")
    md.append("")
    md.append("| # | Version | Source | World | Targets | New | Chg | Del | Logical | "
              "Full | Append | Append/Full | Vault | Time s |")
    md.append("| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
              "---: | ---: | ---: |")
    for i, row in enumerate(primary.versions, 1):
        md.append("| " + " | ".join([
            str(i), f"{BT}{row['version']}{BT}",
            mb(field(row, "source_bytes", "archive_bytes")),
            mb(row.get("world_bytes")), count(row.get("targets")),
            count(row.get("new")), count(row.get("changed")), count(row.get("deleted")),
            mb(row.get("logical_bytes")),
            mb(field(row, "actual_full_total", "full_total")),
            mb(field(row, "actual_incr_total", "incr_total")),
            pct(field(row, "actual_incr_total", "incr_total"),
                field(row, "actual_full_total", "full_total")),
            mb(field(row, "actual_cumulative_min", "cumulative_min")),
            f"{num(row.get('total_ms')) / 1000:.2f}",
        ]) + " |")
    if len(runs) > 1:
        md.append("")
        md.append("## Codec comparison")
        md.append("")
        md.append("| Configuration | First full | Last full | Vault | Vault/copies | "
                  "Median append | Time s | Failures |")
        md.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for run in runs:
            rs = run.summary()
            md.append(f"| {run.name} | {mb(rs['first_full'])} | {mb(rs['last_full'])} | "
                      f"{mb(rs['vault'])} | {ratio(rs['vault'], source_total):.2f}% | "
                      f"{mb(rs['median_incr'])} | {rs['time_ms'] / 1000:.1f} | "
                      f"{int(rs['failures'])} |")
    md.append("")
    md.append("## Method and caveats")
    md.append("")
    md.append("* Content-hash diff, not write capture: incremental numbers are a lower bound "
              "for a server that rewrites unchanged data.")
    md.append("* Only the NBT pipeline is stored; JSON/datapack/config bytes are outside the "
              "vault.")
    md.append("* Append-only: no GC, keyframes or compaction.")
    md.append("* 42-byte block headers and the block index cache are charged; filesystem "
              "rounding is not.")
    md.append("* Timings are indicative single-run wall clock; byte counts are deterministic.")
    if git:
        md.append(f"* Git input: {count(git.get('commits_total'))} commits, "
                  f"{count(git.get('commits_effective'))} effective; the rest only changed "
                  f"files the engine ignores (docs, logs, session.lock, level.dat_old). Each "
                  f"commit was materialised before scanning; prepare time is excluded from the "
                  f"scan columns.")
        md.append("* Source bytes for a commit are an uncompressed working-tree checkout; the "
                  "git repository size is packed, so the two baselines measure different things.")
    md.append("")
    md.append(f"The self-contained visual report is {BT}report.html{BT} in this directory.")
    md.append("")

    # ------------------------------------------------------------ html
    heat_note = ("Each column is one region/entity/poi file or tracked .dat; the 18 most active "
                 "files are shown. Colour = changed + new targets in that snapshot. Vertical "
                 "stripes show where the world actually moved.")
    if heat_rows > 170:
        heat_note += f" Rows are sampled: 170 of {heat_rows} commits."
    heat_block = card("File activity over time", heat, heat_note) if heat else ""

    if git:
        storage_note = ("Everything is expressed in units of one full snapshot of the last "
                        "version. Blue: the engine's append-only vault. Purple: the git "
                        "repository holding the same commits. Green: one full snapshot.")
        lede = (f"{len(labels)} effective commits out of {count(git.get('commits_total'))} "
                f"from <code>{esc(git.get('repo', ''))}</code>, replayed through the engine's "
                f"real checkpoint policy. Every number below is measured, not modelled from a "
                f"sample.")
        chips = [
            esc(git.get("repo", "")), f"branch {esc(git.get('branch', ''))}",
            f"{len(labels)} / {count(git.get('commits_total'))} commits",
            f"{mb(source_total)} of working trees", f"{mb(repo_bytes)} git repository",
            esc(", ".join(git.get("roots", []))), esc(primary.name),
            esc(env.get("cpu", "unknown CPU")), esc(study.get("created", "")),
        ]
    else:
        storage_note = ("Everything is expressed in units of one full snapshot of the last "
                        "version. Orange: keeping one complete copy per snapshot. Blue: the "
                        "engine's append-only vault. Green: the cost of a single full snapshot.")
        lede = (f"{len(labels)} progressive full saves replayed through the engine's real "
                f"checkpoint policy. Every number below is measured, not modelled from a "
                f"sample.")
        chips = [esc(primary.name), f"{len(labels)} snapshots",
                 f"{mb(source_total)} of full copies", esc(env.get("cpu", "unknown CPU")),
                 esc(env.get("java", "")), esc(study.get("created", ""))]
    chips_html = "".join(f"<span>{chip}</span>" for chip in chips)

    raw_links = []
    for run in runs:
        rel = run.dir.relative_to(study_dir).as_posix()
        links = []
        for name in ("versions.csv", "families.csv", "regions.csv", "changes.csv",
                     "skipped.csv"):
            if (run.dir / name).is_file():
                links.append(f'<a href="{rel}/{name}">{name}</a>')
            elif (run.dir / (name + ".gz")).is_file():
                links.append(f'<a href="{rel}/{name}.gz">{name}.gz</a>')
            elif (run.dir / (name + ".xz")).is_file():
                links.append(f'<a href="{rel}/{name}.xz">{name}.xz</a>')
        raw_links.append(f'<li><b>{esc(run.name)}</b>: ' + " · ".join(links) + "</li>")
    raw_card = (f'<section class="card"><h2>Raw data</h2>'
                f'<p class="note">Every number in this report comes from these files. They are '
                f'plain CSV and can be opened in any spreadsheet; <code>changes.csv</code> lists '
                f'each new, changed and deleted target.</p>'
                f'<ul class="raw">{"".join(raw_links)}</ul></section>')

    body = f"""
<header>
  <div class="eyebrow">minimal-backup / differential storage benchmark</div>
  <h1>{esc(study.get('name', study_dir.name))}</h1>
  <p class="lede">{lede}</p>
  <div class="chips">{chips_html}</div>
</header>

<div class="kpis">{''.join(kpis)}</div>
{findings_html}

{card("Storage over time", cumulative, storage_note)}

{card("What each snapshot costs", increments,
      "Bars use a log scale because the baseline is two orders of magnitude larger than "
      "steady state. The dashed line is the same append as a percentage of a full snapshot.")}

{card("Where the append goes", composition,
      "Stacked bytes per append: new targets must be written in full; changed targets pay only "
      "a delta; headers and the block index cache are fixed overhead. The baseline is omitted "
      "because it is entirely new-target FULL payload.")}

{card("Target churn", flow,
      "Changed, new and deleted targets per snapshot. The baseline has no diff by definition.")}

{heat_block}

{card("Target families", family_chart,
      "Chunk versus whole-file appends per snapshot, log scale, baseline omitted. A family "
      "that is persistently high is where tuning pays off.")}

{comparison_html}

{card("Per-snapshot detail", version_table)}

{card("Family totals", family_table)}

{card("Largest deltas across all snapshots", top_table,
            "Targets aggregated across every snapshot, ranked by total DELTA bytes. Small "
      "DELTA/FULL ratios mean alignment and the delta coder are doing their job.")}

{skipped_html}

{raw_card}

<section class="card prose"><h2>Method, accounting and caveats</h2>{method}</section>

<footer>Generated by <code>tools/report.py</code>. All charts are inline SVG; this file
has no external dependencies.</footer>
"""

    css = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:#f7f9fc;color:#1b2430;font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:36px 28px 64px}
header{padding:14px 0 28px;border-bottom:1px solid #e3e9f0;margin-bottom:26px}
.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#2f6df6;font-weight:650}
h1{font-size:34px;line-height:1.15;margin:8px 0 6px;letter-spacing:-.02em}
.lede{max-width:760px;color:#4d5a6b;margin:0 0 16px}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chips span{background:#fff;border:1px solid #e3e9f0;border-radius:999px;padding:4px 11px;font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#4d5a6b}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin-bottom:14px}
.findings{margin:0 0 20px;padding:14px 20px 14px 38px;background:#fff;border:1px solid #e3e9f0;border-radius:12px;color:#3c4a5b;font-size:13.5px}
.findings li{margin:5px 0}
.findings li::marker{color:#2f6df6}
.kpi{background:#fff;border:1px solid #e3e9f0;border-radius:12px;padding:14px 16px}
.kpi-label{font-size:11.5px;letter-spacing:.04em;text-transform:uppercase;color:#6c7888;font-weight:600}
.kpi-value{font:600 24px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:3px;letter-spacing:-.02em}
.kpi-note{font-size:12px;color:#7a8797;margin-top:2px}
.kpi.big .kpi-value{color:#2f6df6}
.kpi.good .kpi-value{color:#0f9d68}
.kpi.bad .kpi-value{color:#d93a41}
.card{background:#fff;border:1px solid #e3e9f0;border-radius:14px;padding:20px 22px 18px;margin:0 0 18px;overflow:hidden}
.card h2{font-size:16px;letter-spacing:-.01em;margin:0 0 4px}
.card .note{color:#6c7888;font-size:12.5px;margin:8px 0 0;max-width:900px}
.card svg{display:block;margin-top:8px}
.table-wrap{overflow:auto;margin-top:12px;border:1px solid #edf1f6;border-radius:10px}
.subhead{font-size:11.5px;color:#6c7888;margin:20px 0 0;font-weight:650;letter-spacing:.06em;text-transform:uppercase}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{padding:7px 9px;border-bottom:1px solid #edf1f6;white-space:nowrap}
th{position:sticky;top:0;background:#f9fbfe;font-weight:650;color:#4d5a6b;text-align:left;z-index:1}
td.num,th.num{text-align:right;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
tbody tr:hover{background:#f7faff}
.barcell{position:relative;min-width:110px;height:16px;display:flex;align-items:center;justify-content:flex-end}
.barcell .bar{position:absolute;left:0;top:2px;bottom:2px;background:#dbe7ff;border-radius:3px}
.barcell .bartext{position:relative;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.empty{color:#6c7888}
.prose p{margin:8px 0;max-width:980px;color:#3c4a5b;font-size:13.5px}
.raw{margin:10px 0 0;padding-left:18px;font-size:12.5px;color:#3c4a5b}
.raw li{margin:4px 0}
.raw a{color:#2f6df6;text-decoration:none}
.raw a:hover{text-decoration:underline}
code{font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;background:#f1f5fa;padding:1px 5px;border-radius:4px}
footer{color:#7a8797;font-size:12px;margin-top:28px;padding-top:16px;border-top:1px solid #e3e9f0}
@media print{body{background:#fff}.card{break-inside:avoid}header{margin-bottom:12px}}
"""

    doc = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
           f"<title>{esc(study.get('name', study_dir.name))} / backup benchmark</title>"
           f"<style>{css}</style></head><body><div class=\"wrap\">{body}</div></body></html>")
    return doc, "\n".join(md) + "\n"


def main(argv: list[str]) -> int:
    study_dir = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    doc, md = build(study_dir)
    (study_dir / "report.html").write_text(doc, encoding="utf-8")
    (study_dir / "report.md").write_text(md, encoding="utf-8")
    print(f"wrote {study_dir / 'report.html'}")
    print(f"wrote {study_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
