from __future__ import annotations

import pandas as pd


def _slope(s: pd.Series, n: int = 1) -> pd.Series:
    return s.diff(n)


def detect_cluster_sequence_breakout(
    df: pd.DataFrame,
    cluster_spread: float = 8.0,
    consolidation_bars: int = 5,
    extreme_level: float = 20.0,
    seq_window: int = 4,
    slope_th: float = 0.0,
) -> pd.DataFrame:
    """User-aligned multi-stoch trigger (long-side) with:

    1) Cluster/compression: max(Ds)-min(Ds) <= cluster_spread for consolidation_bars
    2) Prefer cluster is below extreme_level (20; prefer 10)
    3) Breakout sequence (soft):
       - D9 slope turns positive (> slope_th)
       - within seq_window, D14 slope also positive
       - D40 or D60 slope non-negative (trend participation)

    Adds:
      Stoch_Cluster, Stoch_Cluster_Extreme,
      Stoch_Cluster_LongBreak
    """
    data = df.copy()

    d9 = data["STOCH_D_9"]
    d14 = data["STOCH_D_14"]
    d40 = data["STOCH_D_40"]
    d60 = data["STOCH_D_60"]

    mx = pd.concat([d9, d14, d40, d60], axis=1).max(axis=1)
    mn = pd.concat([d9, d14, d40, d60], axis=1).min(axis=1)

    data["Stoch_Cluster"] = (mx - mn) <= cluster_spread
    data["Stoch_Cluster_Consec"] = data["Stoch_Cluster"].rolling(consolidation_bars, min_periods=consolidation_bars).sum()
    data["Stoch_Cluster_Extreme"] = (data["Stoch_Cluster_Consec"] >= consolidation_bars) & (mx <= extreme_level)

    s9 = _slope(d9)
    s14 = _slope(d14)
    s40 = _slope(d40)
    s60 = _slope(d60)

    # D9 turns up after being in extreme cluster on prior bar
    lead = (data["Stoch_Cluster_Extreme"].shift(1).fillna(False)) & (s9 > slope_th)

    # D14 confirms within window
    conf = s14.rolling(seq_window, min_periods=1).max() > slope_th

    # Slow lines not falling
    slow_ok = (s40 >= 0) | (s60 >= 0)

    data["Stoch_Cluster_LongBreak"] = lead & conf & slow_ok

    return data
