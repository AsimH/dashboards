"""Commodities dashboard — pulls daily closes for four commodity baskets
(Precious / Industrial / Energy / Agri), plus the largest listed equities
in each basket, computes returns + momentum, and renders a self-contained
HTML/SVG dashboard in the same visual language as regime.py.

Run:    uv run python dashboards/commodities.py
Output: output/commodities.html
"""

import html
from datetime import datetime
from pathlib import Path

import pandas as pd

from dashlib.fetchers import fetch_yfinance_panel
from dashlib.transforms import momentum_score, pct_return

# ─────────────────────────────────────────────────────────────────────
# 1. CONFIG
# ─────────────────────────────────────────────────────────────────────
# Each category lists futures first (the "underlying"), then the largest
# listed equities and a sector ETF. Tickers are yfinance symbols.
# Equity market caps are approximate, sourced once and refreshed manually;
# they only drive sort order in the panel, not analytics.

CATEGORIES = {
    "Precious": dict(
        color="#c98a1c",                                    # warm gold
        futures=[
            ("Gold",      "GC=F", "$/oz"),
            ("Silver",    "SI=F", "$/oz"),
            ("Platinum",  "PL=F", "$/oz"),
        ],
        equities=[
            ("Barrick",          "GOLD", "miner"),
            ("Newmont",          "NEM",  "miner"),
            ("Alamos Gold",      "AGI",  "miner"),
            ("Franco-Nevada",    "FNV",  "streaming"),
        ],
        etf=("GDX", "Gold Miners ETF"),
    ),
    "Industrial": dict(
        color="#2c5fa3",                                    # cool blue
        futures=[
            ("Copper", "HG=F", "$/lb"),
        ],
        equities=[
            ("BHP",            "BHP",  "diversified"),
            ("Rio Tinto",      "RIO",  "diversified"),
            ("Freeport-McMoRan", "FCX", "copper"),
            ("Southern Copper", "SCCO", "copper"),
            ("Vale",           "VALE", "iron/nickel"),
        ],
        etf=("PICK", "Diversified Miners ETF"),
    ),
    "Energy": dict(
        color="#b8472a",                                    # rust
        futures=[
            ("WTI crude",    "CL=F", "$/bbl"),
            ("Brent crude",  "BZ=F", "$/bbl"),
            ("Nat gas",      "NG=F", "$/MMBtu"),
            ("Gasoline",     "RB=F", "$/gal"),
        ],
        equities=[
            ("ExxonMobile",   "XOM",  "integrated"),          
            ("Chevron",       "CVX",  "integrated"),
            ("ConocoPhillips","COP",  "E&P"),
            ("Schlumberger",  "SLB",  "services"),
            ("HARD Futures ETF", "HARD", "Futures"),
            ("Uranium ETF", "URA", "Uranium"),
        ],
        etf=("XLE", "Energy Select Sector ETF"),
    ),
    "Agri": dict(
        color="#3a7a3a",                                    # field green
        futures=[
            ("Corn",     "ZC=F", "¢/bu"),
            ("Wheat",    "ZW=F", "¢/bu"),
            ("Soybeans", "ZS=F", "¢/bu"),
            ("Coffee",   "KC=F", "¢/lb"),
            ("Sugar",    "SB=F", "¢/lb"),
        ],
        equities=[
            ("Deere",         "DE",   "machinery"),
            ("ADM",           "ADM",  "trading/processing"),
            ("Bunge",         "BG",   "trading/processing"),
        ],
        etf=("MOO", "Agribusiness ETF"),
    ),

}

# Broad-commodity context displayed in the masthead.
BENCHMARK = ("^BCOM", "Bloomberg Commodity Index")

# Sparkline lookback (trading days). Roughly 6 months.
SPARK_DAYS = 126

# Heatmap windows shown at the bottom, in order.
HEATMAP_WINDOWS = ["1d", "1w", "1m", "3m", "ytd", "1y"]


# ─────────────────────────────────────────────────────────────────────
# 2. LOAD
# ─────────────────────────────────────────────────────────────────────

def all_tickers() -> list[str]:
    out = [BENCHMARK[0]]
    for cat in CATEGORIES.values():
        out += [t for _, t, _ in cat["futures"]]
        out += [t for _, t, _ in cat["equities"]]
        out.append(cat["etf"][0])
    return list(dict.fromkeys(out))           # preserve order, dedupe


def load_prices() -> pd.DataFrame:
    """Single batched yfinance call. Returns wide DataFrame of daily closes."""
    tickers = all_tickers()
    print(f"  Fetching {len(tickers)} tickers from yfinance...")
    return fetch_yfinance_panel(tickers, period="2y")


# ─────────────────────────────────────────────────────────────────────
# 3. ANALYSIS
# ─────────────────────────────────────────────────────────────────────

def row_for(ticker: str, name: str, kind: str, sub: str, prices: pd.DataFrame) -> dict | None:
    """Compute analytics row for one ticker; None if data missing."""
    if ticker not in prices.columns:
        return None
    s = prices[ticker].dropna()
    if len(s) < 2:
        return None
    return dict(
        ticker=ticker, name=name, kind=kind, sub=sub,
        last=float(s.iloc[-1]),
        prev=float(s.iloc[-2]),
        returns={w: pct_return(s, w) for w in HEATMAP_WINDOWS},
        momentum=momentum_score(s),
        sparkline=list(s.iloc[-SPARK_DAYS:].values),
    )


def build_category(cat_name: str, cfg: dict, prices: pd.DataFrame) -> dict:
    futures_rows = [
        r for r in (row_for(t, n, "future", unit, prices) for n, t, unit in cfg["futures"])
        if r
    ]
    equity_rows = [
        r for r in (row_for(t, n, "equity", sub, prices) for n, t, sub in cfg["equities"])
        if r
    ]
    etf_row = row_for(cfg["etf"][0], cfg["etf"][1], "etf", "ETF", prices)

    # Category composite = avg momentum of futures (when present) else equities.
    mom_pool = [r["momentum"] for r in (futures_rows or equity_rows) if not pd.isna(r["momentum"])]
    composite_mom = sum(mom_pool) / len(mom_pool) if mom_pool else float("nan")

    # Category 1m return = unweighted avg of futures 1m (or equities 1m as fallback).
    ret_pool = [r["returns"]["1m"] for r in (futures_rows or equity_rows)
                if not pd.isna(r["returns"]["1m"])]
    composite_1m = sum(ret_pool) / len(ret_pool) if ret_pool else float("nan")

    return dict(
        name=cat_name, color=cfg["color"],
        futures=futures_rows, equities=equity_rows, etf=etf_row,
        composite_mom=composite_mom, composite_1m=composite_1m,
    )


# ─────────────────────────────────────────────────────────────────────
# 4. FORMATTING
# ─────────────────────────────────────────────────────────────────────

def fmt_price(val: float, ticker: str) -> str:
    if pd.isna(val):
        return "—"
    if val >= 1000:
        return f"{val:,.0f}"
    if val >= 100:
        return f"{val:.1f}"
    if val >= 10:
        return f"{val:.2f}"
    return f"{val:.3f}"


def fmt_pct(val: float) -> str:
    if pd.isna(val):
        return "—"
    return f"{val*100:+.1f}%"


# ─────────────────────────────────────────────────────────────────────
# 5. SVG HELPERS
# ─────────────────────────────────────────────────────────────────────

def svg_sparkline(values, color, width=110, height=28) -> str:
    if not values or len(values) < 2:
        return '<svg></svg>'
    pad = 2
    vmin, vmax = min(values), max(values)
    span = (vmax - vmin) or 1
    n = len(values)
    pts = [
        f"{pad + (k/(n-1))*(width-2*pad):.1f},{pad + (1-(v-vmin)/span)*(height-2*pad):.1f}"
        for k, v in enumerate(values)
    ]
    return f'''
<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%">
  <polyline points="{' '.join(pts)}" fill="none" stroke="{color}" stroke-width="1.5"
            stroke-linejoin="round" stroke-linecap="round"/>
</svg>
'''


def svg_mom_gauge(value: float, color: str, width=300, height=44) -> str:
    """Same momentum gauge as regime composites: -3 to +3 scale."""
    if pd.isna(value):
        return '<svg></svg>'
    pad_x = 8
    track_y = height / 2 - 4
    track_h = 6
    inner_w = width - 2 * pad_x
    center_x = pad_x + inner_w / 2
    bar_len = abs(value) / 3 * (inner_w / 2)
    bar_x = center_x if value >= 0 else center_x - bar_len
    return f'''
<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">
  <rect x="{pad_x}" y="{track_y}" width="{inner_w}" height="{track_h}" rx="3" fill="#e8e3d6"/>
  <rect x="{bar_x:.1f}" y="{track_y}" width="{bar_len:.1f}" height="{track_h}" rx="3" fill="{color}"/>
  <line x1="{center_x}" y1="{track_y - 2}" x2="{center_x}" y2="{track_y + track_h + 2}" stroke="#9c9588" stroke-width="0.8"/>
  <text x="{pad_x}" y="{height - 2}" font-family="'JetBrains Mono',monospace" font-size="9" fill="#9c9588">−3</text>
  <text x="{center_x}" y="{height - 2}" text-anchor="middle" font-family="'JetBrains Mono',monospace" font-size="9" fill="#9c9588">0</text>
  <text x="{width - pad_x}" y="{height - 2}" text-anchor="end" font-family="'JetBrains Mono',monospace" font-size="9" fill="#9c9588">+3</text>
</svg>
'''


# ─────────────────────────────────────────────────────────────────────
# 6. ROW + PANEL RENDERING
# ─────────────────────────────────────────────────────────────────────

KIND_COLORS = {"future": "#3a3a3a", "equity": "#2c5fa3", "etf": "#c98a1c"}


def render_row(row: dict, panel_color: str) -> str:
    arrow = "▲" if row["last"] > row["prev"] else ("▼" if row["last"] < row["prev"] else "→")
    arrow_color = panel_color if arrow != "→" else "#999"
    kind_color = KIND_COLORS[row["kind"]]
    one_m = row["returns"]["1m"]
    one_m_color = panel_color if (not pd.isna(one_m) and one_m > 0) else (
        "#999" if pd.isna(one_m) or one_m == 0 else "#666")
    return f'''
<div class="ind-row">
  <span class="cls-dot" style="background:{kind_color}"></span>
  <span class="ind-name">{html.escape(row["name"])}</span>
  <span class="ind-ticker">{html.escape(row["ticker"])}</span>
  <span class="ind-values">
    <span class="ind-current">{fmt_price(row["last"], row["ticker"])}</span>
    <span class="ind-previous">←{fmt_price(row["prev"], row["ticker"])}</span>
  </span>
  <span class="ind-arrow" style="color:{arrow_color}">{arrow}</span>
  <span class="ind-1m" style="color:{one_m_color}">{fmt_pct(one_m)}</span>
  <span class="ind-spark">{svg_sparkline(row["sparkline"], panel_color)}</span>
</div>
'''


def render_category(cat: dict) -> str:
    color = cat["color"]
    mom = cat["composite_mom"]
    mom_str = "—" if pd.isna(mom) else f"{mom:+.1f}"
    mom_arrow = "▲" if (not pd.isna(mom) and mom > 0) else "▼"
    one_m = cat["composite_1m"]

    futures_html = "\n".join(render_row(r, color) for r in cat["futures"])
    equities_html = "\n".join(render_row(r, color) for r in cat["equities"])
    etf_html = render_row(cat["etf"], color) if cat["etf"] else ""

    futures_block = (
        f'<div class="sub-label">Futures · underlying</div>{futures_html}'
        if cat["futures"] else ""
    )
    equities_block = (
        f'<div class="sub-label">Equities · listed exposure</div>{equities_html}'
        if cat["equities"] else ""
    )
    etf_block = (
        f'<div class="sub-label">Sector ETF</div>{etf_html}'
        if cat["etf"] else ""
    )

    return f'''
<section class="category-panel">
  <header class="panel-header">
    <span class="cat-name">{html.escape(cat["name"])}</span>
    <span class="cat-comp" style="color:{color}">
      momentum {mom_arrow} <strong>{mom_str}</strong>
      <span class="cat-1m">· 1m {fmt_pct(one_m)}</span>
    </span>
  </header>
  <div class="cat-gauge">{svg_mom_gauge(mom, color)}</div>
  <div class="panel-rows">
    {futures_block}
    {equities_block}
    {etf_block}
  </div>
</section>
'''


# ─────────────────────────────────────────────────────────────────────
# 7. HEATMAP
# ─────────────────────────────────────────────────────────────────────

def heatmap_color(val: float) -> str:
    """Diverging palette: rust (red) below zero, green above, beige at zero.
    Matches the regime monitor's quadrant tint logic.
    """
    if pd.isna(val):
        return "#ece7d8"
    # Saturate at ±15% for the colour ramp.
    pct = max(-0.15, min(0.15, val)) / 0.15
    if pct >= 0:
        # green ramp
        r = int(236 - pct * (236 - 58))
        g = int(231 - pct * (231 - 122))
        b = int(216 - pct * (216 - 58))
    else:
        # rust ramp
        r = int(236 - (-pct) * (236 - 184))
        g = int(231 - (-pct) * (231 - 71))
        b = int(216 - (-pct) * (216 - 42))
    return f"rgb({r},{g},{b})"


def heatmap_text_color(val: float) -> str:
    if pd.isna(val):
        return "#9c9588"
    return "#1a1815" if abs(val) < 0.08 else "#faf8f3"


def render_heatmap(categories: list[dict]) -> str:
    """Performance heatmap: one row per ticker, columns = return windows."""
    header_cells = "".join(
        f'<div class="hm-h">{w.upper()}</div>' for w in HEATMAP_WINDOWS
    )

    sections = []
    for cat in categories:
        rows = []
        all_items = cat["futures"] + cat["equities"] + ([cat["etf"]] if cat["etf"] else [])
        for r in all_items:
            cells = "".join(
                f'<div class="hm-c" style="background:{heatmap_color(r["returns"][w])};'
                f'color:{heatmap_text_color(r["returns"][w])}">{fmt_pct(r["returns"][w])}</div>'
                for w in HEATMAP_WINDOWS
            )
            kind_color = KIND_COLORS[r["kind"]]
            rows.append(f'''
<div class="hm-row">
  <span class="hm-label">
    <span class="cls-dot" style="background:{kind_color}"></span>
    <span class="hm-name">{html.escape(r["name"])}</span>
    <span class="hm-ticker">{html.escape(r["ticker"])}</span>
  </span>
  {cells}
</div>''')
        sections.append(f'''
<div class="hm-section">
  <div class="hm-section-label" style="color:{cat["color"]}">{html.escape(cat["name"])}</div>
  {"".join(rows)}
</div>''')

    return f'''
<section class="heatmap-section">
  <div class="module-label">
    <span>Performance heatmap · % return by window</span>
    <span>green = up · rust = down · saturated at ±15%</span>
  </div>
  <div class="hm-grid">
    <div class="hm-row hm-headers">
      <span class="hm-label hm-label-spacer"></span>
      {header_cells}
    </div>
    {"".join(sections)}
  </div>
</section>
'''


# ─────────────────────────────────────────────────────────────────────
# 8. WHOLE-PAGE RENDERING
# ─────────────────────────────────────────────────────────────────────

def render_html(categories: list[dict], benchmark_row: dict | None) -> str:
    today = datetime.today().strftime("%B %-d, %Y")

    # Headline: dominant category by absolute momentum.
    cats_with_mom = [c for c in categories if not pd.isna(c["composite_mom"])]
    if cats_with_mom:
        leader = max(cats_with_mom, key=lambda c: abs(c["composite_mom"]))
        leader_str = (
            f"{leader['name']} leading "
            f"({'+' if leader['composite_mom'] > 0 else ''}{leader['composite_mom']:.1f}σ)"
        )
        leader_color = leader["color"]
    else:
        leader_str, leader_color = "—", "#9c9588"

    bench_pill = ""
    if benchmark_row and not pd.isna(benchmark_row["returns"]["1m"]):
        bench_1m = benchmark_row["returns"]["1m"]
        bench_ytd = benchmark_row["returns"]["ytd"]
        bench_pill = (
            f'<span class="bench">^BCOM '
            f'<strong>{fmt_pct(bench_1m)}</strong> 1m · '
            f'<strong>{fmt_pct(bench_ytd)}</strong> YTD</span>'
        )

    panels_html = "\n".join(render_category(c) for c in categories)
    heatmap_html = render_heatmap(categories)

    n_tickers = sum(
        len(c["futures"]) + len(c["equities"]) + (1 if c["etf"] else 0)
        for c in categories
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Commodities monitor · {today}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #faf8f3;
  --ink: #1a1815;
  --ink-soft: #4a463f;
  --rule: #d9d3c4;
  --rule-soft: #ece7d8;
  --card-bg: #f3eedf;
  --precious: #c98a1c;
  --industrial: #2c5fa3;
  --energy: #b8472a;
  --agri: #3a7a3a;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: var(--bg); color: var(--ink);
  font-family: 'Inter', sans-serif; font-size: 14px; line-height: 1.5;
  padding: 48px 56px 64px; max-width: 1280px; margin: 0 auto;
  -webkit-font-smoothing: antialiased;
}}
.masthead {{
  display: grid; grid-template-columns: 1fr auto auto;
  align-items: baseline; gap: 32px;
  padding-bottom: 18px; border-bottom: 1.5px solid var(--ink); margin-bottom: 6px;
}}
.masthead h1 {{
  font-family: 'Cormorant Garamond', serif; font-weight: 600;
  font-size: 36px; letter-spacing: -0.01em; line-height: 1;
}}
.masthead .leader-pill {{
  font-family: 'Cormorant Garamond', serif; font-style: italic; font-size: 18px;
  color: {leader_color}; padding: 4px 14px; border: 1px solid {leader_color};
  border-radius: 100px; letter-spacing: 0.01em;
}}
.masthead .date {{
  font-family: 'JetBrains Mono', monospace; font-size: 11px;
  color: var(--ink-soft); letter-spacing: 0.08em; text-transform: uppercase;
}}
.subhead {{
  display: flex; justify-content: space-between;
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  color: var(--ink-soft); letter-spacing: 0.12em; text-transform: uppercase;
  padding: 8px 0 36px; border-bottom: 0.5px solid var(--rule); margin-bottom: 36px;
}}
.subhead .legend {{ display: flex; gap: 24px; }}
.subhead .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
.subhead .legend i {{ width: 8px; height: 8px; border-radius: 2px; display: inline-block; }}
.bench strong {{ color: var(--ink); font-weight: 600; }}

.categories {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 48px; margin-bottom: 52px;
}}
.category-panel {{ display: flex; flex-direction: column; gap: 14px; }}

.panel-header {{
  display: flex; justify-content: space-between; align-items: baseline;
  padding-bottom: 12px; border-bottom: 0.5px solid var(--rule);
}}
.panel-header .cat-name {{
  font-family: 'Cormorant Garamond', serif; font-weight: 600;
  font-size: 22px; letter-spacing: -0.01em;
}}
.panel-header .cat-comp {{
  font-family: 'JetBrains Mono', monospace; font-size: 11px;
  letter-spacing: 0.04em;
}}
.panel-header .cat-comp strong {{
  font-family: 'Cormorant Garamond', serif; font-weight: 600;
  font-size: 18px; margin: 0 2px;
}}
.panel-header .cat-1m {{ color: var(--ink-soft); margin-left: 6px; }}

.cat-gauge {{ max-width: 360px; }}

.sub-label {{
  font-family: 'JetBrains Mono', monospace; font-size: 9.5px;
  color: var(--ink-soft); letter-spacing: 0.14em; text-transform: uppercase;
  padding: 14px 0 4px;
}}
.sub-label:first-child {{ padding-top: 4px; }}

.ind-row {{
  display: grid; grid-template-columns: 10px 1.2fr 38px 78px 16px 52px 90px;
  align-items: center; gap: 10px;
  padding: 10px 0; border-bottom: 0.5px solid var(--rule-soft);
}}
.ind-row:last-child {{ border-bottom: none; }}
.cls-dot {{ width: 8px; height: 8px; border-radius: 2px; display: inline-block; }}
.ind-name {{ font-family: 'Cormorant Garamond', serif; font-size: 16px; font-weight: 500; }}
.ind-ticker {{
  font-family: 'JetBrains Mono', monospace; font-size: 9.5px;
  color: var(--ink-soft); letter-spacing: 0.04em;
}}
.ind-values {{ display: flex; flex-direction: column; text-align: right; align-items: flex-end; }}
.ind-current {{ font-family: 'JetBrains Mono', monospace; font-weight: 600; font-size: 13px; }}
.ind-previous {{ font-family: 'JetBrains Mono', monospace; font-size: 9.5px; color: var(--ink-soft); margin-top: 2px; }}
.ind-arrow {{ font-size: 11px; text-align: center; }}
.ind-1m {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600; text-align: right; }}
.ind-spark {{ height: 28px; display: flex; align-items: center; }}

/* heatmap */
.heatmap-section {{ margin-top: 8px; }}
.module-label {{
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  color: var(--ink-soft); letter-spacing: 0.14em; text-transform: uppercase;
  padding-bottom: 14px; border-bottom: 0.5px solid var(--rule); margin-bottom: 18px;
  display: flex; justify-content: space-between;
}}
.hm-grid {{ display: flex; flex-direction: column; gap: 14px; }}
.hm-section {{ display: flex; flex-direction: column; gap: 2px; }}
.hm-section-label {{
  font-family: 'Cormorant Garamond', serif; font-style: italic; font-weight: 600;
  font-size: 14px; padding: 6px 0 2px;
}}
.hm-row {{
  display: grid; grid-template-columns: 220px repeat({len(HEATMAP_WINDOWS)}, 1fr); gap: 2px;
  align-items: stretch;
}}
.hm-row.hm-headers {{
  font-family: 'JetBrains Mono', monospace; font-size: 9.5px;
  color: var(--ink-soft); letter-spacing: 0.14em;
}}
.hm-headers .hm-h {{
  background: transparent; text-align: center; padding: 6px 0;
}}
.hm-label {{
  display: grid; grid-template-columns: 10px 1fr auto; gap: 8px;
  align-items: center; padding: 0 8px;
  font-family: 'Cormorant Garamond', serif; font-size: 14px;
}}
.hm-label-spacer {{ background: transparent; }}
.hm-name {{ font-weight: 500; }}
.hm-ticker {{
  font-family: 'JetBrains Mono', monospace; font-size: 9.5px;
  color: var(--ink-soft); letter-spacing: 0.04em;
}}
.hm-c {{
  font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600;
  text-align: center; padding: 8px 0; border-radius: 3px;
  display: flex; align-items: center; justify-content: center;
}}

.colophon {{
  margin-top: 56px; padding-top: 20px; border-top: 1.5px solid var(--ink);
  display: flex; justify-content: space-between;
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  color: var(--ink-soft); letter-spacing: 0.1em; text-transform: uppercase;
}}
</style>
</head>
<body>

<header class="masthead">
  <h1>Commodities Monitor</h1>
  <span class="leader-pill">{html.escape(leader_str)}</span>
  <span class="date">{today}</span>
</header>

<div class="subhead">
  <span>Four categories · futures + listed equities · {n_tickers} tickers · 1y momentum z-score</span>
  <span class="legend">
    <span><i style="background:#3a3a3a"></i>Future</span>
    <span><i style="background:#2c5fa3"></i>Equity</span>
    <span><i style="background:#c98a1c"></i>ETF</span>
    {bench_pill}
  </span>
</div>

<div class="categories">
  {panels_html}
</div>

{heatmap_html}

<footer class="colophon">
  <span>Source · Yahoo Finance via yfinance · daily closes, auto-adjusted</span>
  <span>Generated {today}</span>
</footer>

</body>
</html>
'''


# ─────────────────────────────────────────────────────────────────────
# 9. ENTRY POINT
# ─────────────────────────────────────────────────────────────────────

def main(out_path: str = "output/commodities.html") -> None:
    print("Loading commodities data...")
    prices = load_prices()

    categories = [build_category(name, cfg, prices) for name, cfg in CATEGORIES.items()]
    benchmark = row_for(BENCHMARK[0], BENCHMARK[1], "etf", "benchmark", prices)

    print()
    for c in categories:
        mom = c["composite_mom"]
        print(f"  {c['name']:11s} momentum: {mom:+.2f}" if not pd.isna(mom)
              else f"  {c['name']:11s} momentum:    —")
    print()

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(categories, benchmark), encoding="utf-8")
    print(f"Saved → {out_path}")


if __name__ == "__main__":
    main()
