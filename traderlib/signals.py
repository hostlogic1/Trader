from __future__ import annotations

import pandas as pd


def detect_multi_stoch_breakout(
    df: pd.DataFrame,
    consolidation_bars: int = 5,
    oversold_level: float = 20.0,
    overbought_level: float = 80.0,
) -> pd.DataFrame:
    """Notebook-aligned baseline breakout:

    - All 4 D-lines are below oversold (or above overbought)
    - condition holds for N consecutive bars
    - breakout is when current bar is no longer all-oversold/all-overbought

    Adds columns:
      All_Oversold, All_Overbought,
      Oversold_Consecutive, Overbought_Consecutive,
      Stoch_Breakout_Buy, Stoch_Breakout_Sell, Stoch_Avg
    """
    data = df.copy()

    d9 = data["STOCH_D_9"]
    d14 = data["STOCH_D_14"]
    d40 = data["STOCH_D_40"]
    d60 = data["STOCH_D_60"]

    data["All_Oversold"] = (d9 < oversold_level) & (d14 < oversold_level) & (d40 < oversold_level) & (d60 < oversold_level)
    data["All_Overbought"] = (d9 > overbought_level) & (d14 > overbought_level) & (d40 > overbought_level) & (d60 > overbought_level)

    data["Oversold_Consecutive"] = (
        data["All_Oversold"].rolling(window=consolidation_bars, min_periods=consolidation_bars).sum()
    )
    data["Overbought_Consecutive"] = (
        data["All_Overbought"].rolling(window=consolidation_bars, min_periods=consolidation_bars).sum()
    )

    data["Stoch_Breakout_Buy"] = (data["Oversold_Consecutive"].shift(1) >= consolidation_bars) & (~data["All_Oversold"])
    data["Stoch_Breakout_Sell"] = (data["Overbought_Consecutive"].shift(1) >= consolidation_bars) & (~data["All_Overbought"])

    data["Stoch_Avg"] = (d9 + d14 + d40 + d60) / 4.0

    return data
