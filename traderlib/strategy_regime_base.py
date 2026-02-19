from __future__ import annotations

"""Regime-driven strategy skeleton.

This is a scaffold we can iterate:
- Compute 15m regime per asset (heuristic first)
- Map regime+confidence -> entry mode and risk parameters
- Execute entries on 5m

Note: backtesting.py Strategy expects signals to be computed on the same dataframe.
We'll initially attach regime labels to the 5m dataframe by forward-filling 15m regime.
"""

import numpy as np
import pandas as pd
from backtesting import Strategy


class RegimeDrivenLongOnly(Strategy):
    # Risk base
    base_sl_atr = 1.5
    base_tp_atr = 1.0

    # Confidence scaling
    # Example: widen TP/SL as confidence increases
    sl_conf_mult = 1.0
    tp_conf_mult = 1.5

    min_conf_to_trade = 0.4

    def init(self):
        pass

    def next(self):
        df = self.data.df
        i = len(df) - 1
        if i < 1:
            return

        # required columns
        if "REGIME" not in df.columns or "REGIME_CONF" not in df.columns:
            return

        regime = df["REGIME"].iat[i]
        conf = float(df["REGIME_CONF"].iat[i])

        if not np.isfinite(conf) or conf < self.min_conf_to_trade:
            return

        # Placeholder entry trigger:
        # - RANGING: take stoch bounce/cluster (to be implemented)
        # - TRENDING: take pullback continuation (to be implemented)
        # For now we do nothing until entry modes are wired.
        _ = regime
        _ = conf
        return
