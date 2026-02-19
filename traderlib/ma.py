from __future__ import annotations

import pandas as pd


def add_sma(df: pd.DataFrame, length: int, col: str) -> pd.DataFrame:
    out = df.copy()
    out[col] = out["Close"].rolling(length, min_periods=length).mean()
    return out
