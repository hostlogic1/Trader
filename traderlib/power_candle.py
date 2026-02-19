from __future__ import annotations

import pandas as pd


def add_power_candle_flags(
    df: pd.DataFrame,
    lookback: int = 7,
    close_near_top: float = 0.25,
    body_ratio_min: float = 0.65,
) -> pd.DataFrame:
    """Adds a bullish power candle flag.

    Definitions (5m):
    - range_pct = (H-L)/Close
    - power if range_pct is the rolling max over `lookback`
    - bullish close (C>O)
    - close near the high
    - body dominates range (minimal wick)

    Returns df copy with:
      RangePct, BodyRatio, CloseNearTop, CloseNearBot, BullPower, BearPower
    """
    data = df.copy()

    rng = (data["High"] - data["Low"]).astype(float)
    close = data["Close"].astype(float)
    body = (data["Close"] - data["Open"]).abs().astype(float)

    data["RangePct"] = rng / close
    data["BodyRatio"] = body / rng.replace(0, pd.NA)

    # how close to high the close is (0=at high, 1=at low)
    data["CloseNearTop"] = (data["High"] - data["Close"]) / rng.replace(0, pd.NA)
    data["CloseNearBot"] = (data["Close"] - data["Low"]) / rng.replace(0, pd.NA)

    roll_max = data["RangePct"].rolling(lookback, min_periods=lookback).max()
    is_largest = data["RangePct"] >= roll_max

    bullish = data["Close"] > data["Open"]
    bearish = data["Close"] < data["Open"]

    strong_close_bull = data["CloseNearTop"] <= close_near_top
    strong_close_bear = data["CloseNearBot"] <= close_near_top

    clean_body = data["BodyRatio"] >= body_ratio_min

    data["BullPower"] = (is_largest & bullish & strong_close_bull & clean_body).fillna(False)
    data["BearPower"] = (is_largest & bearish & strong_close_bear & clean_body).fillna(False)

    return data
