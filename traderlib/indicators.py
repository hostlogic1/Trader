from __future__ import annotations

import pandas as pd
import pandas_ta as ta


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Baseline indicator set approximating the notebook.

    Uses pandas_ta (not TA-Lib) for portability.

    Required columns: Open, High, Low, Close, Volume
    Returns a copy with indicators and drops rows with NaNs.
    """
    data = df.copy()

    # EMAs
    data["EMA_8"] = ta.ema(data["Close"], length=8)
    data["EMA_13"] = ta.ema(data["Close"], length=13)
    data["EMA_21"] = ta.ema(data["Close"], length=21)

    # ADX + DI
    adx = ta.adx(data["High"], data["Low"], data["Close"], length=14)
    # pandas_ta uses columns like ADX_14, DMP_14, DMN_14
    data["ADX"] = adx.get("ADX_14")
    data["DI_Plus"] = adx.get("DMP_14")
    data["DI_Minus"] = adx.get("DMN_14")

    # MFI
    data["MFI"] = ta.mfi(data["High"], data["Low"], data["Close"], data["Volume"], length=14)

    # ATR
    data["ATR"] = ta.atr(data["High"], data["Low"], data["Close"], length=14)

    # Stochastic D lines (fastk_period ~ length; smooth_k=3; smooth_d=3)
    def _stoch_d(length: int) -> pd.Series:
        st = ta.stoch(data["High"], data["Low"], data["Close"], k=length, d=3, smooth_k=3)
        # columns: STOCHk_{k}_{d}_{smooth_k}, STOCHd_{k}_{d}_{smooth_k}
        dcol = [c for c in st.columns if c.startswith("STOCHd_")][0]
        return st[dcol]

    for length in (9, 14, 40, 60):
        data[f"STOCH_D_{length}"] = _stoch_d(length)

    data = data.dropna().copy()
    return data
