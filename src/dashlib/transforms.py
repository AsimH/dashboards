"""Series transforms for the dashboards build. Trimmed to what markets_tracker & commodities use."""
import pandas as pd


# ─── return-window helpers (daily price series) ──────────────────────

# Approx business-day counts for common return horizons.
RETURN_WINDOWS = {"1d": 1, "1w": 5, "1m": 21, "3m": 63, "6m": 126, "ytd": None, "1y": 252}


def pct_return(series: pd.Series, window: str) -> float:
    """Percent return over a named window. NaN if not enough history."""
    s = series.dropna()
    if len(s) < 2:
        return float("nan")
    if window == "ytd":
        year_start = s.index[-1].replace(month=1, day=1)
        prior = s.loc[:year_start]
        if prior.empty:
            return float("nan")
        return float(s.iloc[-1] / prior.iloc[-1] - 1)
    n = RETURN_WINDOWS[window]
    if len(s) <= n:
        return float("nan")
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1)


def momentum_score(series: pd.Series, window: int = 252) -> float:
    """Single-number momentum reading: z-score of the trailing 1m return
    against the trailing 252-day distribution of 1m returns.
    Winsorized at ±3 like the regime composites for consistency.
    """
    s = series.dropna()
    if len(s) < window + 21:
        return float("nan")
    monthly = s.pct_change(21)
    recent = monthly.iloc[-1]
    dist = monthly.iloc[-window:]
    mean, std = dist.mean(), dist.std()
    if std == 0 or pd.isna(std):
        return float("nan")
    return float(max(-3, min(3, (recent - mean) / std)))
