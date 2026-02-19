#!/usr/bin/env python3
"""Backtest the multi-signal strategy (cluster + bounce)."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd
from backtesting import Backtest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from traderlib.indicators import calculate_indicators
from traderlib.signals_cluster import detect_cluster_sequence_breakout
from traderlib.signals_bounce import detect_stoch_bounce
from traderlib.signals_momentum import detect_momentum_pullback
from traderlib.strategy_multi import MultiSignalLongOnly


def _clean(x):
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--commission", type=float, default=0.001)
    ap.add_argument("--out", default="reports/multi_backtest.json")
    ap.add_argument("--oversold", type=float, default=30.0)
    args = ap.parse_args()

    df = pd.read_csv(args.csv, parse_dates=[0], index_col=0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df = calculate_indicators(df)
    df = detect_cluster_sequence_breakout(df)
    df = detect_stoch_bounce(df, oversold_level=args.oversold)
    df = detect_momentum_pullback(df)

    bt = Backtest(df, MultiSignalLongOnly, cash=10_000, commission=args.commission)
    stats = bt.run()

    trades = int(len(stats["_trades"]))
    pf = _clean(float(stats.get("Profit Factor", float("nan"))))
    ret = _clean(float(stats.get("Return [%]", float("nan"))))
    maxdd = _clean(float(stats.get("Max. Drawdown [%]", float("nan"))))
    wr = _clean(float(stats.get("Win Rate [%]", float("nan"))))
    sharpe = _clean(float(stats.get("Sharpe Ratio", float("nan"))))

    result = {
        "model": "multi-signal (cluster+bounce)",
        "trades": trades,
        "profit_factor": pf,
        "return_pct": ret,
        "max_drawdown_pct": maxdd,
        "win_rate_pct": wr,
        "sharpe_ratio": sharpe,
        "oversold_level": args.oversold,
        "stats": {k: _clean(float(v)) if isinstance(v, (int, float)) else str(v) for k, v in stats.items() if not k.startswith("_")},
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "stats"}, indent=2))


if __name__ == "__main__":
    main()
