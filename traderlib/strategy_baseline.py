from __future__ import annotations

import numpy as np
from backtesting import Strategy


class BaselineStochLongOnly(Strategy):
    """Minimal baseline: long-only entries on multi-stoch breakout with trend filters.

    This is intentionally conservative and matches the notebook spirit:
    - EMA alignment bullish
    - ADX strong + DI+ > DI-
    - MFI not overbought
    - Multi-stoch breakout buy signal

    Exits:
    - ATR-based stop and take profit.
    """

    # Optimizable parameters
    adx_threshold = 20.0
    mfi_high_threshold = 70.0

    stop_loss_atr_multiplier = 2.0
    take_profit_atr_multiplier = 3.0

    use_stoch_filter = True

    def init(self):
        self.atr = self.I(lambda: self.data.df["ATR"].to_numpy())
        self.stoch_buy = self.I(lambda: self.data.df["Stoch_Breakout_Buy"].astype(int).to_numpy())

    def next(self):
        df = self.data.df
        i = len(df) - 1

        if i < 1:
            return

        # Filters
        ema_bullish = (df["EMA_8"].iat[i] > df["EMA_13"].iat[i]) and (df["EMA_13"].iat[i] > df["EMA_21"].iat[i])
        adx_strong = df["ADX"].iat[i] > self.adx_threshold
        di_bullish = df["DI_Plus"].iat[i] > df["DI_Minus"].iat[i]
        mfi_ok = df["MFI"].iat[i] < self.mfi_high_threshold

        stoch_ok = True
        if self.use_stoch_filter:
            stoch_ok = bool(df["Stoch_Breakout_Buy"].iat[i])

        if (not self.position) and ema_bullish and adx_strong and di_bullish and mfi_ok and stoch_ok:
            atr = float(df["ATR"].iat[i])
            if not np.isfinite(atr) or atr <= 0:
                return

            entry = float(df["Close"].iat[i])
            sl = entry - self.stop_loss_atr_multiplier * atr
            tp = entry + self.take_profit_atr_multiplier * atr
            self.buy(sl=sl, tp=tp)
