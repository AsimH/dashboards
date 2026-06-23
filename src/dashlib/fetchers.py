"""Data loaders for the dashboards build. Trimmed to what markets_tracker & commodities use."""
import pandas as pd


def fetch_yfinance_panel(tickers: list[str], period: str = "2y") -> pd.DataFrame:
    """Fetch many tickers in a single network call, return wide DataFrame
    (index = date, columns = tickers). Drops tickers that came back empty.
    """
    import yfinance as yf
    df = yf.download(
        tickers=" ".join(tickers),
        period=period,
        auto_adjust=True,
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
    return pd.DataFrame(closes).sort_index().ffill()
