#!/usr/bin/env python3
"""Quick backtest of EMA+ADX strategy."""
import json, math, sys
from pathlib import Path
import pandas as pd
from backtesting import Backtest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from traderlib.indicators import calculate_indicators
from traderlib.signals_momentum import detect_momentum_pullback
from traderlib.strategy_ema_adx import EmaAdxLongOnly

def _c(x):
    return None if isinstance(x, float) and (math.isnan(x) or math.isinf(x)) else x

df = pd.read_csv(sys.argv[1] if len(sys.argv)>1 else "data/binanceus_SOL-USDT_5m.csv", parse_dates=[0], index_col=0)
df = df[["Open","High","Low","Close","Volume"]].copy()
df = calculate_indicators(df)
df = detect_momentum_pullback(df)  # for Regime_SMA column

bt = Backtest(df, EmaAdxLongOnly, cash=10_000, commission=0.001)
stats = bt.run()
trades = int(len(stats["_trades"]))
print(json.dumps({
    "trades": trades,
    "pf": _c(float(stats.get("Profit Factor", float("nan")))),
    "ret%": _c(float(stats.get("Return [%]", float("nan")))),
    "maxdd%": _c(float(stats.get("Max. Drawdown [%]", float("nan")))),
    "wr%": _c(float(stats.get("Win Rate [%]", float("nan")))),
    "sharpe": _c(float(stats.get("Sharpe Ratio", float("nan")))),
}, indent=2))
