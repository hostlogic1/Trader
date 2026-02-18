from __future__ import annotations

import numpy as np
from backtesting import Strategy


class BaselineStochClusterLongOnly(Strategy):
    """Looser baseline intended to produce trades while staying rule-based.

    Entry gate:
    - Multi-stoch cluster+sequence breakout (Stoch_Cluster_LongBreak)
    - Plus *soft* trend filter: either EMA bullish OR DI+ > DI-

    Exits:
    - ATR-based SL/TP

    This is a stepping stone before adding key levels + market structure.
    """

    stop_loss_atr_multiplier = 2.0
    take_profit_atr_multiplier = 3.0

    require_ema_bullish = False

    def init(self):
        # nothing to precompute yet; required by backtesting.Strategy
        pass

    def next(self):
        df = self.data.df
        i = len(df) - 1
        if i < 1:
            return

        trig = bool(df["Stoch_Cluster_LongBreak"].iat[i])
        if not trig:
            return

        ema_bullish = (df["EMA_8"].iat[i] > df["EMA_13"].iat[i]) and (df["EMA_13"].iat[i] > df["EMA_21"].iat[i])
        di_bullish = df["DI_Plus"].iat[i] > df["DI_Minus"].iat[i]

        trend_ok = ema_bullish or di_bullish
        if self.require_ema_bullish:
            trend_ok = ema_bullish

        if self.position or (not trend_ok):
            return

        atr = float(df["ATR"].iat[i])
        if not np.isfinite(atr) or atr <= 0:
            return

        entry = float(df["Close"].iat[i])
        sl = entry - self.stop_loss_atr_multiplier * atr
        tp = entry + self.take_profit_atr_multiplier * atr
        self.buy(sl=sl, tp=tp)
