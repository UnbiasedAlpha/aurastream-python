"""Convert AuraStream JSON into pandas objects."""

from __future__ import annotations

from typing import Any, Mapping

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise ImportError("pandas is required for DataFrame helpers: pip install 'aurastream[pandas]'") from exc

_OHLCV = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}


def to_frame(data: Mapping[str, Any], ticker: str | None = None, *, normalize_columns: bool = True) -> "pd.DataFrame":
    """Turn `{ticker: {timestamp: {field: value}}}` into a DataFrame for one ticker.

    - Index: UTC `DatetimeIndex`, sorted, named `timestamp`.
    - Numeric strings (Binance, Bybit, Kraken and Oanda send prices as strings) become floats.
    - With `normalize_columns`, lower-case OHLCV names (Alpaca, Kraken futures) become `Open/High/Low/Close/Volume`.
    """
    if ticker is None:
        if len(data) != 1:
            raise ValueError(f"Response has {len(data)} tickers; pass ticker=... (one of {list(data)})")
        ticker = next(iter(data))
    if ticker not in data:
        raise KeyError(f"{ticker!r} not in response (got {list(data)})")

    rows = data[ticker] or {}
    if not rows:
        return pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC", name="timestamp"))

    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index = pd.to_datetime(df.index, utc=True)
    df.index.name = "timestamp"
    df = df.sort_index()

    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        # Keep text columns (titles, URLs, classifications) as they are.
        if converted.notna().sum() >= df[col].notna().sum():
            df[col] = converted

    if normalize_columns:
        df = df.rename(columns={c: _OHLCV[c] for c in df.columns if c in _OHLCV})
    return df


def to_panel(data: Mapping[str, Any], field: str = "Close") -> "pd.DataFrame":
    """Wide DataFrame with one column per ticker holding `field` (case-insensitive match)."""
    columns = {}
    for ticker in data:
        df = to_frame(data, ticker)
        if df.empty:
            continue
        match = next((c for c in df.columns if str(c).lower() == field.lower()), None)
        if match is None:
            raise KeyError(f"{field!r} not found for {ticker!r}; available: {list(df.columns)}")
        columns[ticker] = df[match]
    return pd.DataFrame(columns).sort_index()
