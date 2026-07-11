#!/usr/bin/env python3
"""
build_prices.py — turn the PSX "Symbol Price (Upper/Lower)" daily file into a
small prices.json that the portfolio page reads.

The PSX file is a single-day snapshot with these columns:
    MARKET_CODE, SYMBOL_CODE, SYMBOL_NAME, SETTLEMENT_TYPE,
    ORDER_REJECT_UPPER_PRICE, ORDER_REJECT_LOWER_PRICE, LAST_DAY_CLOSE_PRICE
Rows are '\\r'-delimited and quoted with single quotes. We keep only the REG
(regular market) segment and take LAST_DAY_CLOSE_PRICE as the price.

Two input modes:
  * --file  path/to/202609jul.zip|.txt      (a file you already have)
  * --url-base https://dps.psx.com.pk/...    (directory the daily file lives in;
                                              filename is rebuilt from the date)

With --url-base the script builds "{base}/{YYYY}{DD}{mon}.zip" for the target
date and, if that day has no file (weekend/holiday), walks back up to
--lookback days to the most recent available file.

No third-party dependencies — stdlib only.
"""
import argparse, io, json, re, sys, zipfile, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

PKT = timezone(timedelta(hours=5))              # Pakistan has no DST
MONTHS = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]

# --- parsing -----------------------------------------------------------------

REG_RE = re.compile(r"^'REG','([^']+)','(.*)','[^']+',([\d.]+),([\d.]+),([\d.]+)$")

def parse_reg(text):
    """Return (prices, names) dicts from the REG segment of a Symbol Price file."""
    prices, names = {}, {}
    for row in re.split(r"[\r\n]+", text):
        if not row.startswith("'REG'"):
            continue
        m = REG_RE.match(row)
        if not m:
            continue
        sym, name, _up, _lo, close = m.groups()
        prices[sym] = float(close)
        names[sym] = name
    return prices, names

def read_any(raw_bytes, hint_name=""):
    """Accept a .zip (take first .txt inside) or a raw .txt; return decoded text."""
    if raw_bytes[:2] == b"PK":                  # zip magic
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
            txt = next((n for n in z.namelist() if n.lower().endswith(".txt")), z.namelist()[0])
            return z.read(txt).decode("utf-8", "replace")
    return raw_bytes.decode("utf-8", "replace")

# --- dates -------------------------------------------------------------------

def parse_asof_from_name(name):
    """202609jul -> (iso 2026-07-09, label '09 Jul 2026'). None if it doesn't match."""
    m = re.search(r"(\d{4})(\d{2})([a-z]{3})", name.lower())
    if not m:
        return None
    yyyy, dd, mon = m.group(1), m.group(2), m.group(3)
    if mon not in MONTHS:
        return None
    mm = MONTHS.index(mon) + 1
    iso = f"{yyyy}-{mm:02d}-{int(dd):02d}"
    label = f"{int(dd):02d} {mon.capitalize()} {yyyy}"
    return iso, label

def dated_filename(d):
    """date -> 202609jul style stem."""
    return f"{d.year}{d.day:02d}{MONTHS[d.month-1]}"

# --- fetching ----------------------------------------------------------------

def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "psx-portfolio-monitor/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def fetch_latest(url_base, target, lookback, ext):
    """Try target date then walk back to the newest file that exists."""
    base = url_base.rstrip("/")
    last_err = None
    for i in range(lookback + 1):
        d = target - timedelta(days=i)
        if d.weekday() >= 5:                     # skip Sat/Sun outright
            continue
        stem = dated_filename(d)
        url = f"{base}/{stem}.{ext}"
        try:
            data = http_get(url)
            if data and (data[:2] == b"PK" or b"'REG'" in data[:4000]):
                return data, stem, url
            last_err = f"{url} -> unexpected content"
        except urllib.error.HTTPError as e:
            last_err = f"{url} -> HTTP {e.code}"
        except Exception as e:                    # noqa
            last_err = f"{url} -> {e}"
    raise SystemExit(f"No PSX file found in the last {lookback} days. Last try: {last_err}")

# --- main --------------------------------------------------------------------

def build(text, source_name, out_path, source_label):
    prices, names = parse_reg(text)
    if len(prices) < 50:
        raise SystemExit(f"Only {len(prices)} REG symbols parsed — refusing to overwrite prices.json.")
    asof = parse_asof_from_name(source_name)
    if asof:
        iso, label = asof
    else:                                         # fall back to today (PKT)
        now = datetime.now(PKT)
        iso, label = now.strftime("%Y-%m-%d"), now.strftime("%d %b %Y")
    payload = {
        "as_of": iso,
        "as_of_label": label,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source_label,
        "count": len(prices),
        "prices": dict(sorted(prices.items())),
        "names": dict(sorted(names.items())),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)
    print(f"[ok] {out_path}: {len(prices)} symbols, close {label} (from {source_name})")
    return payload

def main():
    ap = argparse.ArgumentParser(description="Build prices.json from a PSX Symbol Price file.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="local .zip or .txt already downloaded")
    src.add_argument("--url-base", help="directory URL the daily file lives in")
    ap.add_argument("--date", help="target date YYYY-MM-DD for --url-base (default: today PKT)")
    ap.add_argument("--lookback", type=int, default=5, help="days to walk back over holidays")
    ap.add_argument("--ext", default="zip", help="daily file extension (zip or txt)")
    ap.add_argument("--out", default="prices.json", help="output path")
    a = ap.parse_args()

    label_src = "PSX Symbol Price (Upper/Lower), REG segment"
    if a.file:
        with open(a.file, "rb") as f:
            raw = f.read()
        text = read_any(raw, a.file)
        build(text, a.file, a.out, label_src)
    else:
        target = datetime.strptime(a.date, "%Y-%m-%d").date() if a.date else datetime.now(PKT).date()
        raw, stem, url = fetch_latest(a.url_base, target, a.lookback, a.ext)
        print(f"[fetch] {url}")
        text = read_any(raw, stem)
        build(text, stem, a.out, label_src + f" via {url}")

if __name__ == "__main__":
    main()
