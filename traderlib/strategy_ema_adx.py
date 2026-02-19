from __future__ import annotations

import numpy as np
from backtesting import Strategy


class EmaAdxLongOnly(Strategy):
    """Simple EMA crossover + ADX trend strategy, regime-gated.

    Entry: EMA8 crosses above EMA21, ADX > 25, DI+ > DI-, price > regime SMA
    Exit: ATR-based SL/TP

    This is a classic trend-following approach that should produce
    decent win rates in trending markets.
    """

    sl_atr = 1.5
    tp_atr = 3.0
    adx_min = 25

    def init(self):
        pass

    def next(self):
        df = self.data.df
        i = len(df) - 1
        if i < 2 or self.position:
            return

        # Regime: price above long SMA
        if "Regime_SMA" in df.columns:
            sma = df["Regime_SMA"].iat[i]
            if not np.isfinite(sma) or df["Close"].iat[i] <= sma:
                return

        # EMA8 crosses above EMA21
        ema8 = df["EMA_8"].iat[i]
        ema21 = df["EMA_21"].iat[i]
        ema8_prev = df["EMA_8"].iat[i-1]
        ema21_prev = df["EMA_21"].iat[i-1]

        cross = (ema8 > ema21) and (ema8_prev <= ema21_prev)
        if not cross:
            return

        # ADX filter
        if df["ADX"].iat[i] < self.adx_min:
            return

        # DI+ > DI-
        if df["DI_Plus"].iat[i] <= df["DI_Minus"].iat[i]:
            return

        atr = float(df["ATR"].iat[i])
        if not np.isfinite(atr) or atr <= 0:
            return

        entry = float(df["Close"].iat[i])
        self.buy(sl=entry - self.sl_atr * atr, tp=entry + self.tp_atr * atr)
