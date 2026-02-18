from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from backtesting import Backtest

from traderlib.indicators import calculate_indicators
from traderlib.signals import detect_multi_stoch_breakout
from traderlib.strategy_baseline import BaselineStochLongOnly


def profit_factor_from_stats(stats) -> float:
    # backtesting.py uses a pandas Series-like stats object
    for k in ("Profit Factor", "Profit factor", "ProfitFactor"):
        if k in stats:
            try:
                return float(stats[k])
            except Exception:
                pass
    return float("nan")


def run_one(csv_path: Path, cash: float, commission: float):
    df = pd.read_csv(csv_path, parse_dates=[0], index_col=0)
    # Ensure required columns names
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()

    df = calculate_indicators(df)
    df = detect_multi_stoch_breakout(df, consolidation_bars=5, oversold_level=20, overbought_level=80)

    bt = Backtest(df, BaselineStochLongOnly, cash=cash, commission=commission, trade_on_close=False)
    stats = bt.run()
    pf = profit_factor_from_stats(stats)
    return stats, pf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv-1m", required=True)
    ap.add_argument("--csv-5m", required=True)
    ap.add_argument("--cash", type=float, default=10_000)
    ap.add_argument("--commission", type=float, default=0.001, help="fraction per trade side (e.g. 0.001 = 0.1%)")
    ap.add_argument("--out", default="reports/ab_result.json")
    args = ap.parse_args()

    s1, pf1 = run_one(Path(args.csv_1m), args.cash, args.commission)
    s5, pf5 = run_one(Path(args.csv_5m), args.cash, args.commission)

    winner = "1m" if (pf1 > pf5) else "5m"

    out = {
        "1m": {"profit_factor": pf1, "stats": s1.to_dict()},
        "5m": {"profit_factor": pf5, "stats": s5.to_dict()},
        "winner": winner,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"winner": winner, "pf_1m": pf1, "pf_5m": pf5}, indent=2))


if __name__ == "__main__":
    main()
