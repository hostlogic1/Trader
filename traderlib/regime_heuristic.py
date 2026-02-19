from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def efficiency_ratio(close: pd.Series, n: int) -> pd.Series:
    direction = (close - close.shift(n)).abs()
    volatility = close.diff().abs().rolling(n).sum()
    return direction / volatility


@dataclass
class RegimeOutput:
    regime: pd.Series  # TRENDING/RANGING/VOLATILE/UNKNOWN
    confidence: pd.Series  # 0..1
    features: pd.DataFrame


def compute_regime(
    df: pd.DataFrame,
    er_n: int = 50,
    er_trend: float = 0.35,
    er_range: float = 0.25,
    atr_n: int = 14,
    atrp_volatile: float = 0.06,
    conf_smooth: int = 5,
) -> RegimeOutput:
    close = df["Close"].astype(float)

    er = efficiency_ratio(close, er_n)

    tr = pd.concat([
        (df["High"] - df["Low"]).abs(),
        (df["High"] - df["Close"].shift(1)).abs(),
        (df["Low"] - df["Close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_n).mean()
    atrp = atr / close

    regime = pd.Series("UNKNOWN", index=df.index)
    regime[er < er_range] = "RANGING"
    regime[er > er_trend] = "TRENDING"
    regime[atrp > atrp_volatile] = "VOLATILE"

    # Confidence: distance from thresholds, clipped 0..1, smoothed.
    # Trend confidence rises above er_trend; range confidence rises below er_range; volatile above atrp_volatile.
    trend_conf = ((er - er_trend) / max(1e-9, (1 - er_trend))).clip(0, 1)
    range_conf = ((er_range - er) / max(1e-9, er_range)).clip(0, 1)
    vol_conf = ((atrp - atrp_volatile) / max(1e-9, atrp_volatile)).clip(0, 1)

    conf = pd.Series(0.0, index=df.index)
    conf[regime == "TRENDING"] = trend_conf[regime == "TRENDING"]
    conf[regime == "RANGING"] = range_conf[regime == "RANGING"]
    conf[regime == "VOLATILE"] = vol_conf[regime == "VOLATILE"]

    conf = conf.rolling(conf_smooth, min_periods=1).mean()

    feats = pd.DataFrame({
        "ER": er,
        "ATR": atr,
        "ATRp": atrp,
        "TrendConf": trend_conf,
        "RangeConf": range_conf,
        "VolConf": vol_conf,
    }, index=df.index)

    return RegimeOutput(regime=regime, confidence=conf, features=feats)
