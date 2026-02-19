from __future__ import annotations

import numpy as np
from backtesting import Strategy


class MultiSignalLongOnly(Strategy):
    """Combined entry: momentum pullback + cluster breakout, both regime-gated.

    Only trades when price > 2400-bar SMA (bullish regime).
    """

    def init(self):
        pass

    def next(self):
        df = self.data.df
        i = len(df) - 1
        if i < 1 or self.position:
            return

        # Regime gate: must be above long SMA
        if "Regime_SMA" in df.columns:
            sma_val = df["Regime_SMA"].iat[i]
            if not np.isfinite(sma_val) or df["Close"].iat[i] <= sma_val:
                return

        # Signal A: momentum pullback (primary)
        momentum = bool(df["Momentum_Pullback_Long"].iat[i]) if "Momentum_Pullback_Long" in df.columns else False

        # Signal B: cluster breakout (rare)
        cluster = bool(df["Stoch_Cluster_LongBreak"].iat[i]) if "Stoch_Cluster_LongBreak" in df.columns else False

        if momentum:
            sl_mult, tp_mult = 1.5, 2.5
        elif cluster:
            sl_mult, tp_mult = 2.0, 3.0
        else:
            return

        atr = float(df["ATR"].iat[i])
        if not np.isfinite(atr) or atr <= 0:
            return

        entry = float(df["Close"].iat[i])
        self.buy(sl=entry - sl_mult * atr, tp=entry + tp_mult * atr)
