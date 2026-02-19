from __future__ import annotations

import pandas as pd


def detect_stoch_bounce(
    df: pd.DataFrame,
    oversold_level: float = 30.0,
    cross_confirm_bars: int = 2,
) -> pd.DataFrame:
    """Higher-frequency long entry: stochastic bounce from oversold.

    Trigger conditions (all must be true):
    1. D9 was below oversold_level within the last cross_confirm_bars
    2. D9 crosses above D14 (current bar: D9 > D14, previous bar: D9 <= D14)
    3. D40 or D60 > 30 (not in deep downtrend on slow timeframe)

    This produces far more signals than cluster+sequence while still
    requiring a meaningful stochastic structure.

    Adds column: Stoch_Bounce_Long
    """
    data = df.copy()

    d9 = data["STOCH_D_9"]
    d14 = data["STOCH_D_14"]
    d40 = data["STOCH_D_40"]
    d60 = data["STOCH_D_60"]

    # D9 was recently oversold
    recently_oversold = (d9 < oversold_level).rolling(
        cross_confirm_bars, min_periods=1
    ).max().astype(bool)

    # D9 crosses above D14
    cross_up = (d9 > d14) & (d9.shift(1) <= d14.shift(1))

    # Slow lines not deeply bearish
    slow_ok = (d40 > 30) | (d60 > 30)

    data["Stoch_Bounce_Long"] = recently_oversold & cross_up & slow_ok

    return data
