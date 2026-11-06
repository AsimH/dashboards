"""Data loaders for the dashboards build. Trimmed to what markets_tracker & commodities use."""
import pandas as pd


def fetch_yfinance_panel(
    tickers: list[str],
    period: str = "2y",
    start: str | None = None,
    auto_adjust: bool = True,
    ffill: bool = True,
) -> pd.DataFrame:
    """Fetch many tickers in a single network call, return wide DataFrame
    (index = date, columns = tickers). Drops tickers that came back empty.
    `start` (YYYY-MM-DD) overrides `period`; `auto_adjust=False` gives raw
    closes (price return, dividends excluded). `ffill=False` leaves NaN on
    dates a ticker didn't trade (e.g. US tickers on a row created by an HK
    session), so per-ticker `.dropna()` yields only its own sessions.
    """
    import yfinance as yf
    df = yf.download(
        tickers=" ".join(tickers),
        period=None if start else period,
        start=start,
        auto_adjust=auto_adjust,
        progress=False,
        group_by="ticker",
    )
    # When multiple tickers requested, yfinance returns a column MultiIndex
    # (ticker, field). Pull just the Close per ticker.
    closes = {}
    for t in tickers:
        try:
            s = df[t]["Close"] if (t, "Close") in df.columns else df["Close"][t]
            if s.dropna().empty:
                print(f"  ⚠ {t}: no data returned, skipping")
                continue
            closes[t] = s
        except KeyError:
            print(f"  ⚠ {t}: not in yfinance response, skipping")
    out = pd.DataFrame(closes).sort_index()
    return out.ffill() if ffill else out
