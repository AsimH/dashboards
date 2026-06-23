"""Markets tracker dashboard — global ETF universe across three tabs
(Markets / Sectors / Bonds), each showing a 9-window return matrix with
heatmap coloring and 1-month sparkline. Designed to feel editorial-print
rather than spreadsheet-dense: larger fonts, Cormorant Garamond for
display, JetBrains Mono for numerics.

Tabs are pure CSS (radio + sibling selector) — no JS needed.

Run:    uv run python dashboards/markets_tracker.py
Output: output/markets_tracker.html
"""

import html
from datetime import datetime
from pathlib import Path

import pandas as pd

from dashlib.fetchers import fetch_yfinance_panel
from dashlib.transforms import pct_return

# ─────────────────────────────────────────────────────────────────────
# 1. UNIVERSE
# ─────────────────────────────────────────────────────────────────────
# Three tabs, each a list of (section_header, [(name, ticker, sub), ...])
# Tickers are yfinance-format. HK tickers convert XHKG:NNNN → NNNN.HK.
# Frankfurt-listed get .DE suffix; rest are US-listed (no suffix needed).

TABS = {
    "U.S. Markets": [
        ("U.S. Markets", [
            ("S&P 500",         "VOO",   "Vanguard S&P 500"),
            ("US Growth",       "VUG",   "Vanguard Growth"),
            ("US Value",        "VTV",   "Vanguard Value"),
            ("S&P MidCap 400",  "IVOO",  "Vanguard S&P Mid"),
            ("S&P SmallCap 600","VIOO",  "Vanguard S&P Small"),
            ("Nasdaq",          "QQQ",   "Invesco QQQ"),
            ("MAGS",            "MAGS",  "Roundhill Mag 7"),
            ("Berkshire B",     "BRK-B", "BRK.B (yfin uses dash)"),
        ]),
        ("US Major Sectors", [
            ("Information Tech",       "XLK",  "Tech Sel Sector"),
            ("Financials",             "XLF",  "Fin Sel Sector"),
            ("Health Care",            "XLV",  "HC Sel Sector"),
            ("Consumer Disc.",         "XLY",  "ConsDisc Sel Sector"),
            ("Comm Services",          "XLC",  "ComS Sel Sector"),
            ("Industrials",            "XLI",  "Ind Sel Sector"),
            ("Cons. Staples",          "XLP",  "ConsStpl Sel Sector"),
            ("Energy",                 "XLE",  "Enrgy Sel Sector"),
            ("Utilities",              "XLU",  "Utl Sel Sector"),
            ("Materials",              "XLB",  "Mat Sel Sector"),
            ("Real Estate",            "XLRE", "RE Sel Sector"),
        ]),
        ("US Sectors of Interest", [
            ("MAGS",            "MAGS", "Roundhill Mag 7"),
            ("Semiconductors",  "SOXX", "iShares Semiconductor"),
            ("Aero & Defense",  "ITA",  "iShares US Aero&Def"),
            ("Metals & Mining", "XME",  "SPDR S&P Metals&Mng"),
        ]),
    ],
    "Developed Markets": [
        ("Developed", [
            ("World ex-US",       "VXUS", "Vanguard Total Intl"),
            ("Developed Value",   "IVLU", "iShares MSCI Intl Val"),
            ("Developed Growth",  "JIG",  "JPMorgan Intl Growth"),
            ("Dev SC Value",      "DISV", "DFA Intl SmCap Value"),
            ("Ex-US Small Cap",   "VSS",  "Vanguard FTSE ExUS SC"),
        ]),
        ("Europe", [
            ("UK Market",     "EWU", "iShares MSCI UK"),
            ("Europe Market", "VGK", "Vanguard FTSE Europe"),
            ("Germany",       "EWG", "iShares MSCI Germany"),
            ("France",        "EWQ", "iShares MSCI France"),
        ]),
        ("Asia", [
            ("China Market", "MCHI", "iShares MSCI China"),
            ("Hong Kong",    "EWH",  "iShares MSCI HK"),
            ("Taiwan",       "EWT",  "iShares MSCI Taiwan"),
            ("South Korea",  "EWY",  "iShares MSCI S Korea"),
            ("Singapore",    "EWS",  "iShares MSCI Singapore"),
        ]),
        ("Japan", [
            ("Japan Market",    "EWJ",  "iShares MSCI Japan"),
            ("Japan Small Cap", "DFJ",  "WisdomTree Jpn SC Div"),
            ("Japan Value",     "EWJV", "iShares MSCI Jpn Value"),
        ]),
    ],
    "Emerging Markets": [
        ("Emerging Broad", [
            ("EM",                "VWO",  "Vanguard EM"),
            ("EM ex-China",       "EMXC", "iShares MSCI EM ex Chn"),
            ("EM Value",          "DFEV", "DFA EM Value"),
            ("Latin America",     "ILF",  "iShares Lat Am 40"),
        ]),
        ("HK Listed / China", [
            ("Hang Seng Tech",       "2837.HK", "Global X HS Tech"),
            ("China Internet",       "2812.HK", "SS CSI China Dragon Int"),
            ("China Cloud",          "2826.HK", "Global X CN Cloud"),
            ("China Semi",           "3191.HK", "Global X CN Semi"),
            ("China Robot & AI",     "2807.HK", "Global X CN Robot&AI"),
            ("China EV & Battery",   "2845.HK", "Global X CN EV&Batt"),
            ("China New Economy",    "3182.HK", "W.I.S.E. NasdaqChNwEcCo"),
            ("China Cons Brand",     "2806.HK", "Global X China Cons Brd"),
            ("China Biotech",        "2820.HK", "Global X China Biotech"),
            ("Healthcare Disrup HK", "3174.HK", "CSOP HS Biotech"),
        ]),
        ("EM Countries", [
            ("Argentina",    "ARGT", "Global X MSCI Argentina"),
            ("Mexico",       "EWW",  "iShares MSCI Mexico"),
            ("Turkey",       "TUR",  "iShares MSCI Turkey"),
            ("South Africa", "EZA",  "iShares MSCI S Africa"),
            ("Brazil",       "EWZ",  "iShares MSCI Brazil"),
            ("Poland",       "EPOL", "iShares MSCI Poland"),
            ("Thailand",     "THD",  "iShares MSCI Thailand"),
        ]),
        ("Middle East", [
            ("Saudi Arabia", "KSA", "iShares MSCI S Arabia"),
            ("UAE",          "UAE", "iShares MSCI UAE"),
            ("Qatar",        "QAT", "iShares MSCI Qatar"),
        ]),
    ],
    "Bonds": [
        ("U.S. Govt / Quasi-Govt", [
            ("20+ Year Treasury",   "TLT",  "iShares 20+ Tr Bd"),
            ("Intermediate Treas",  "VGIT", "Vanguard Int Tr"),
            ("Short Term Treas",    "VGSH", "Vanguard ST Tr"),
            ("Mortgage Bonds",      "VMBS", "Vanguard Mtg-Bk Idx"),
            ("TIPS",                "VTIP", "Vanguard ST IPSI"),
        ]),
        ("U.S. Corporate", [
            ("Corp Long Term",      "VCLT", "Vanguard LT Corp"),
            ("Corp Interm Term",    "VCIT", "Vanguard Int Corp"),
            ("Corp Short Term",     "VCSH", "Vanguard ST Corp"),
            ("Corp HY",             "HYG",  "iShares iBoxx HY"),
        ]),
        ("EM Bonds", [
            ("EM USD Bonds",        "EMB",  "iShares JPM USD EM"),
            ("EM LC Bonds",         "EMLC", "VanEck JPM EM LC"),
            ("EM Active",           "ELD",  "WisdomTree EM Local Dbt"),
            ("EM Sovereign Active", "PCY",  "Invesco EM Sov Dbt"),
            ("China Bonds",         "CBON", "VanEck China Bond"),
            ("EM Corp Bonds",       "CEMB", "iShares JPM EM Corp Bd"),
        ]),
    ],
    "Interesting": [
        ("Semis", [
            ("NVIDIA Corp",   "NVDA",  "NVIDIA Corp"),
            ("ASML Holdings NV",  "ASML", "ASML Holdings NV"),
            ("Broadcom Inc",    "AVGO", "Broadcom Inc"),
            ("Advanced Micro Devices Inc",      "AMD", "Advanced Micro Devices Inc"),
            ("Taiwan Semiconductor Manufacturing Co Ltd",                "TSM", "Taiwan Semiconductor Manufacturing Co Ltd"),
            ("ARM Holdings PLC", "ARM", "ARM Holdings PLC"),
            ("Analog Devices Inc", "ADI", "Analog Devices Inc"),
            ("Micron Technology Inc", "MU", "Micron Technology Inc"),
            ("Qualcomm Inc", "QCOM", "Qualcomm Inc"),
        ]),
        ("MAG 7", [
            ("Roundhill Mag 7",            "MAGS", "Roundhill Mag 7"),
            ("Apple Inc",            "AAPL", "Apple Inc"),
            ("Microsoft Corp",            "MSFT", "Microsoft Corp"),
            ("Alphabet Inc",            "GOOG", "Alphabet Inc"),
            ("Amazon.com Inc",            "AMZN", "Amazon.com Inc"),
            ("Tesla Inc",            "TSLA", "Tesla Inc"),
            ("Meta Platforms Inc",            "META", "Meta Platforms Inc"),
            ("NVIDIA Corp",            "NVDA", "NVIDIA Corp"),
        ]),
        ("Energy", [
            ("Energy Select Sector SPDR Fund",            "XLE", "Energy Select Sector SPDR Fund"),
            ("Natural Gas ETF",            "FCG", "Natural Gas ETF"), 
            ("Exxon Mobil Corp",            "XOM", "Exxon Mobil Corp"),
            ("Chevron Corp",            "CVX", "Chevron Corp"),
            ("ConocoPhillips",            "COP", "ConocoPhillips"),
            ("Schlumberger Ltd",            "SLB", "Schlumberger Ltd"),
        ]),
        ("Clean Energy", [
            ("iShares MSCI Clean Energy Tech",            "ICLN", "iShares MSCI Clean Energy Tech"),
            ("Clean Energy Fund",            "CNRG", "Clean Energy Fund"),
            ("Renewable Energy Fund",            "RNRG", "Renewable Energy Fund"),
            ("Invesco Solar ETF",            "TAN", "Invesco Solar ETF"),
            ("Glbl X Lith and Batteries ETF",            "LIT", "Glbl X Lith and Batteries ETF"),
            ("Invesco Global Clean Power ETF",            "PBD", "Invesco Global Clean Power ETF"),
        ]),
    ],
    }

# Columns shown in each row, in display order. (label, window_key)
# YTD's position is dynamic — it slots in between the windows whose
# elapsed days bracket the year-to-date count. See build_return_cols().
_BASE_COLS = [
    ("1D",   "1d"),
    ("1W",   "1w"),
    ("MTD",  "mtd"),
    ("1M",   "1m"),
    ("3M",   "3m"),
    ("6M",   "6m"),
    ("1Y",   "1y"),
]
# Approx calendar-day offsets used to slot YTD into the right spot.
_COL_DAYS = {"1d": 1, "1w": 7, "mtd": 0, "1m": 30, "3m": 90, "6m": 180, "1y": 365}


def build_return_cols(asof: datetime | None = None) -> list[tuple[str, str]]:
    """Build the column list with YTD inserted at its date-appropriate spot.
    On Jan 15: YTD (~15 days) lands between 1W and 1M.
    On May 19: YTD (~140 days) lands between 3M and 6M.
    On Oct 1:  YTD (~270 days) lands between 6M and 1Y.
    """
    asof = asof or datetime.today()
    ytd_days = (asof - asof.replace(month=1, day=1)).days
    out: list[tuple[str, str]] = []
    inserted = False
    for label, key in _BASE_COLS:
        # Skip the slot-zero windows when comparing — MTD has no fixed
        # span so we anchor to its position rather than its day-count.
        if not inserted and key in ("3m", "6m", "1y") and ytd_days < _COL_DAYS[key]:
            out.append(("YTD", "ytd"))
            inserted = True
        out.append((label, key))
    if not inserted:                                             # late in year
        out.append(("YTD", "ytd"))
    return out


RETURN_COLS = build_return_cols()

SPARK_DAYS = 21          # ~ 1 month
HEATMAP_CAP = 0.15       # color saturation cap (±15%)


# ─────────────────────────────────────────────────────────────────────
# 2. LOAD
# ─────────────────────────────────────────────────────────────────────

def all_tickers() -> list[str]:
    out = []
    for sections in TABS.values():
        for _, rows in sections:
            for _, t, _ in rows:
                out.append(t)
    return list(dict.fromkeys(out))


def load_prices() -> pd.DataFrame:
    tickers = all_tickers()
    print(f"  Fetching {len(tickers)} unique tickers from yfinance...")
    # 3-year period so we have a clean 2y return + buffer for weekends/holidays
    return fetch_yfinance_panel(tickers, period="3y")


# ─────────────────────────────────────────────────────────────────────
# 3. EXTRA RETURN WINDOWS (MTD, 2y)
# ─────────────────────────────────────────────────────────────────────
# pct_return in transforms.py already handles 1d/1w/1m/3m/6m/ytd/1y.
# We need MTD and 2y on top — add them here without touching transforms,
# so transforms stays minimal and reusable.

def pct_return_mtd(series: pd.Series) -> float:
    s = series.dropna()
    if len(s) < 2:
        return float("nan")
    month_start = s.index[-1].replace(day=1)
    prior = s.loc[:month_start]
    if prior.empty:
        return float("nan")
    return float(s.iloc[-1] / prior.iloc[-1] - 1)


def returns_for(series: pd.Series) -> dict[str, float]:
    out = {}
    for _, key in RETURN_COLS:
        if key == "mtd":
            out[key] = pct_return_mtd(series)
        else:
            out[key] = pct_return(series, key)
    return out


# ─────────────────────────────────────────────────────────────────────
# 4. ROW BUILDING
# ─────────────────────────────────────────────────────────────────────

def build_row(name: str, ticker: str, sub: str, prices: pd.DataFrame) -> dict | None:
    if ticker not in prices.columns:
        return None
    s = prices[ticker].dropna()
    if len(s) < 2:
        return None
    return dict(
        name=name, ticker=ticker, sub=sub,
        returns=returns_for(s),
        sparkline=list(s.iloc[-SPARK_DAYS:].values),
    )


def build_tab(tab_name: str, sections: list, prices: pd.DataFrame) -> list[dict]:
    """Returns a list of section dicts, each with rows."""
    out = []
    for section_name, items in sections:
        rows = []
        for name, ticker, sub in items:
            r = build_row(name, ticker, sub, prices)
            if r:
                rows.append(r)
            else:
                print(f"  ⚠ {tab_name} / {section_name}: missing {ticker}")
        out.append(dict(name=section_name, rows=rows))
    return out


# ─────────────────────────────────────────────────────────────────────
# 5. RENDERING — heatmap palette
# ─────────────────────────────────────────────────────────────────────

def heatmap_color(val: float) -> str:
    """Diverging palette matching the commodities dashboard:
    rust below zero, green above, beige at zero. Saturation capped at ±15%.
    Slightly more muted than commodities since there are far more cells here.
    """
    if pd.isna(val):
        return "transparent"
    pct = max(-HEATMAP_CAP, min(HEATMAP_CAP, val)) / HEATMAP_CAP
    if pct >= 0:
        r = int(243 - pct * (243 - 92))
        g = int(238 - pct * (238 - 142))
        b = int(225 - pct * (225 - 78))
    else:
        r = int(243 - (-pct) * (243 - 192))
        g = int(238 - (-pct) * (238 - 90))
        b = int(225 - (-pct) * (225 - 60))
    return f"rgb({r},{g},{b})"


def heatmap_text_color(val: float) -> str:
    if pd.isna(val):
        return "#9c9588"
    return "#1a1815" if abs(val) < 0.08 else "#faf8f3"


def fmt_pct(val: float) -> str:
    if pd.isna(val):
        return "—"
    return f"{val*100:+.1f}%"


def svg_sparkline(values, color="#3a3a3a", width=120, height=32) -> str:
    if not values or len(values) < 2:
        return ''
    pad = 2
    vmin, vmax = min(values), max(values)
    span = (vmax - vmin) or 1
    n = len(values)
    pts = [
        f"{pad + (k/(n-1))*(width-2*pad):.1f},{pad + (1-(v-vmin)/span)*(height-2*pad):.1f}"
        for k, v in enumerate(values)
    ]
    # color stroke based on net direction
    direction_color = "#588a4e" if values[-1] >= values[0] else "#b8472a"
    return f'''
<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%">
  <polyline points="{' '.join(pts)}" fill="none" stroke="{direction_color}" stroke-width="1.6"
            stroke-linejoin="round" stroke-linecap="round"/>
</svg>
'''


# ─────────────────────────────────────────────────────────────────────
# 6. RENDERING — tables
# ─────────────────────────────────────────────────────────────────────

def render_row(row: dict) -> str:
    cells = []
    for _, key in RETURN_COLS:
        v = row["returns"][key]
        bg = heatmap_color(v)
        fg = heatmap_text_color(v)
        cells.append(
            f'<span class="mt-c" style="background:{bg};color:{fg}">{fmt_pct(v)}</span>'
        )
    cells_html = "".join(cells)

    return f'''
<div class="mt-row">
  <span class="mt-name">{html.escape(row["name"])}</span>
  <span class="mt-ticker">{html.escape(row["ticker"])}</span>
  <span class="mt-spark">{svg_sparkline(row["sparkline"])}</span>
  {cells_html}
</div>
'''


def render_section(section: dict) -> str:
    rows_html = "\n".join(render_row(r) for r in section["rows"])
    return f'''
<div class="mt-section">
  <h3 class="mt-section-name">{html.escape(section["name"])}</h3>
  {rows_html}
</div>
'''


def render_tab(tab_name: str, sections: list[dict], tab_idx: int) -> str:
    sections_html = "\n".join(render_section(s) for s in sections)
    header_cells = "".join(
        f'<span class="mt-h">{label}</span>' for label, _ in RETURN_COLS
    )
    return f'''
<section class="mt-tab" id="tab-{tab_idx}">
  <div class="mt-table">
    <div class="mt-row mt-headers">
      <span class="mt-h-name">Index / ETF</span>
      <span class="mt-h-ticker">Ticker</span>
      <span class="mt-h-spark">1M trend</span>
      {header_cells}
    </div>
    {sections_html}
  </div>
</section>
'''


# ─────────────────────────────────────────────────────────────────────
# 7. PAGE
# ─────────────────────────────────────────────────────────────────────

def render_html(tab_data: dict[str, list[dict]]) -> str:
    today = datetime.today().strftime("%B %-d, %Y")

    # Render the radio inputs (one per tab, first checked by default)
    radios = "\n".join(
        f'<input type="radio" name="mt-tabs" id="mt-radio-{i}" '
        f'class="mt-radio" {"checked" if i == 0 else ""}>'
        for i in range(len(tab_data))
    )

    # The visible tab buttons (labels for the radios)
    tab_labels = "\n".join(
        f'<label for="mt-radio-{i}" class="mt-tab-btn">{html.escape(name)}</label>'
        for i, name in enumerate(tab_data.keys())
    )

    # The tab content panels
    tabs_html = "\n".join(
        render_tab(name, sections, i)
        for i, (name, sections) in enumerate(tab_data.items())
    )

    # Build the CSS rules that show the right tab based on which radio is checked.
    # For each radio i, when checked, show tab i and highlight button i.
    tab_show_rules = "\n".join(
        f'#mt-radio-{i}:checked ~ .mt-tab-content #tab-{i} {{ display: block; }}'
        for i in range(len(tab_data))
    )
    tab_btn_rules = "\n".join(
        f'#mt-radio-{i}:checked ~ .mt-tab-bar label[for="mt-radio-{i}"] {{'
        f' color: var(--ink); border-bottom-color: var(--ink); }}'
        for i in range(len(tab_data))
    )

    total_tickers = sum(
        sum(len(s["rows"]) for s in sections) for sections in tab_data.values()
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Markets tracker · {today}</title>
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
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: var(--bg); color: var(--ink);
  font-family: 'Inter', sans-serif; font-size: 15px; line-height: 1.5;
  padding: 48px 56px 64px; max-width: 1400px; margin: 0 auto;
  -webkit-font-smoothing: antialiased;
}}

/* ─── masthead ────────────────────────────────────────────────── */
.masthead {{
  display: grid; grid-template-columns: 1fr auto;
  align-items: baseline; gap: 32px;
  padding-bottom: 22px; border-bottom: 1.5px solid var(--ink); margin-bottom: 6px;
}}
.masthead h1 {{
  font-family: 'Cormorant Garamond', serif; font-weight: 600;
  font-size: 44px; letter-spacing: -0.01em; line-height: 1;
}}
.masthead .date {{
  font-family: 'JetBrains Mono', monospace; font-size: 12px;
  color: var(--ink-soft); letter-spacing: 0.08em; text-transform: uppercase;
}}
.subhead {{
  display: flex; justify-content: space-between;
  font-family: 'JetBrains Mono', monospace; font-size: 11px;
  color: var(--ink-soft); letter-spacing: 0.12em; text-transform: uppercase;
  padding: 10px 0 32px; border-bottom: 0.5px solid var(--rule); margin-bottom: 32px;
}}

/* ─── tabs ────────────────────────────────────────────────────── */
.mt-radio {{ display: none; }}
.mt-tab-bar {{
  display: flex; gap: 4px; margin-bottom: 28px;
  border-bottom: 0.5px solid var(--rule);
}}
.mt-tab-btn {{
  font-family: 'Cormorant Garamond', serif; font-weight: 500;
  font-size: 22px; letter-spacing: -0.005em;
  padding: 12px 28px 14px; cursor: pointer;
  color: var(--ink-soft);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.15s ease;
}}
.mt-tab-btn:hover {{ color: var(--ink); }}
{tab_btn_rules}

.mt-tab-content > .mt-tab {{ display: none; }}
{tab_show_rules}

/* ─── table layout ────────────────────────────────────────────── */
.mt-table {{ display: flex; flex-direction: column; gap: 32px; }}

.mt-section {{ display: flex; flex-direction: column; gap: 2px; }}

.mt-section-name {{
  font-family: 'Cormorant Garamond', serif; font-weight: 600; font-style: italic;
  font-size: 22px; letter-spacing: -0.005em;
  padding: 12px 0 14px; margin-top: 8px;
  border-bottom: 0.5px solid var(--rule);
  color: var(--ink);
}}
.mt-section:first-child .mt-section-name {{ margin-top: 0; }}

/*  Columns:
    name  ticker  spark  N × return
    240   60      130    N × 1fr            */
.mt-row {{
  display: grid;
  grid-template-columns: 240px 60px 130px repeat({len(RETURN_COLS)}, 1fr);
  gap: 6px; align-items: center;
  padding: 7px 0;
  border-bottom: 0.5px solid var(--rule-soft);
}}
.mt-row:last-child {{ border-bottom: none; }}
.mt-row.mt-headers {{
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  color: var(--ink-soft); letter-spacing: 0.14em; text-transform: uppercase;
  padding: 14px 0 10px;
  border-bottom: 1px solid var(--rule);
  position: sticky; top: 0;
  background: var(--bg);
  z-index: 2;
}}
.mt-row.mt-headers .mt-h,
.mt-row.mt-headers .mt-h-ticker,
.mt-row.mt-headers .mt-h-spark {{
  text-align: center;
}}
.mt-row.mt-headers .mt-h-name {{ text-align: left; }}

/* row cells */
.mt-name {{
  font-family: 'Cormorant Garamond', serif; font-size: 18px; font-weight: 500;
  letter-spacing: -0.005em;
}}
.mt-ticker {{
  font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600;
  color: var(--ink-soft); letter-spacing: 0.04em; text-align: center;
}}
.mt-spark {{ height: 32px; display: flex; align-items: center; }}
.mt-c {{
  font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600;
  text-align: center; padding: 8px 0; border-radius: 3px;
  display: flex; align-items: center; justify-content: center;
  font-feature-settings: "tnum";
}}

/* ─── colophon ────────────────────────────────────────────────── */
.colophon {{
  margin-top: 64px; padding-top: 22px; border-top: 1.5px solid var(--ink);
  display: flex; justify-content: space-between;
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  color: var(--ink-soft); letter-spacing: 0.1em; text-transform: uppercase;
}}
</style>
</head>
<body>

<header class="masthead">
  <h1>Markets Tracker</h1>
  <span class="date">{today}</span>
</header>

<div class="subhead">
  <span>Global ETF universe · {total_tickers} tickers · returns across {len(RETURN_COLS)} windows</span>
  <span>Heatmap saturated at ±15% · 1m sparkline</span>
</div>

{radios}

<div class="mt-tab-bar">
  {tab_labels}
</div>

<div class="mt-tab-content">
  {tabs_html}
</div>

<footer class="colophon">
  <span>Source · Yahoo Finance via yfinance · daily closes, auto-adjusted</span>
  <span>Generated {today}</span>
</footer>

</body>
</html>
'''


# ─────────────────────────────────────────────────────────────────────
# 8. ENTRY
# ─────────────────────────────────────────────────────────────────────

def main(out_path: str = "output/markets_tracker.html") -> None:
    print("Loading markets tracker data...")
    prices = load_prices()

    tab_data = {
        name: build_tab(name, sections, prices)
        for name, sections in TABS.items()
    }

    print()
    for tab_name, sections in tab_data.items():
        n = sum(len(s["rows"]) for s in sections)
        print(f"  {tab_name:10s} {n:3d} tickers rendered")
    print()

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(tab_data), encoding="utf-8")
    print(f"Saved → {out_path}")


if __name__ == "__main__":
    main()
