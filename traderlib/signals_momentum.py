from __future__ import annotations

import pandas as pd


def detect_momentum_pullback(
    df: pd.DataFrame,
    pullback_level: float = 45.0,
    recovery_level: float = 50.0,
    regime_sma: int = 2400,
) -> pd.DataFrame:
    """Momentum pullback-continuation entry for trending markets.

    Logic (long only):
    1. Price above regime_sma SMA (bullish regime — ~200 bars on 1h equiv)
    2. EMA8 > EMA13 > EMA21 (bullish trend)
    3. D9 dipped below pullback_level recently (pullback into trend)
    4. D9 crosses back above recovery_level (recovery)
    5. D40 > 40 (slow stoch confirms trend)
    6. ADX > 18 (trending, not choppy)

    Adds columns: Regime_SMA, Momentum_Pullback_Long
    """
    data = df.copy()

    d9 = data["STOCH_D_9"]
    d40 = data["STOCH_D_40"]

    # Regime filter: price above long SMA
    data["Regime_SMA"] = data["Close"].rolling(regime_sma, min_periods=regime_sma).mean()
    regime_bull = data["Close"] > data["Regime_SMA"]

    # Bullish EMA stack
    ema_bull = (data["EMA_8"] > data["EMA_13"]) & (data["EMA_13"] > data["EMA_21"])

    # D9 dipped below pullback level in last 5 bars
    dipped = (d9 < pullback_level).rolling(5, min_periods=1).max().astype(bool)

    # D9 recovers above recovery level
    recovered = (d9 > recovery_level) & (d9.shift(1) <= recovery_level)

    # Slow stoch confirms
    slow_ok = d40 > 40

    # ADX confirms trending
    adx_ok = data["ADX"] > 18

    data["Momentum_Pullback_Long"] = regime_bull & ema_bull & dipped & recovered & slow_ok & adx_ok

    return data
