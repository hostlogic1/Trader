from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from backtesting import Backtest

# allow running as script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from traderlib.indicators import calculate_indicators
from traderlib.signals_cluster import detect_cluster_sequence_breakout
from traderlib.strategy_cluster import BaselineStochClusterLongOnly


def _clean(x):
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


@dataclass
class Result:
    params: dict
    profit_factor: float | None
    trades: int
    max_dd: float | None
    ret: float | None


def run_once(df: pd.DataFrame, params: dict, commission: float) -> Result:
    dfx = detect_cluster_sequence_breakout(
        df,
        cluster_spread=params["cluster_spread"],
        consolidation_bars=params["consolidation_bars"],
        extreme_level=params["extreme_level"],
        seq_window=params["seq_window"],
        slope_th=params["slope_th"],
    )

    bt = Backtest(dfx, BaselineStochClusterLongOnly, cash=10_000, commission=commission)
    stats = bt.run()

    trades = int(len(stats["_trades"]))
    pf = _clean(float(stats.get("Profit Factor", float("nan"))))
    maxdd = _clean(float(stats.get("Max. Drawdown [%]", float("nan"))))
    ret = _clean(float(stats.get("Return [%]", float("nan"))))

    return Result(params=params, profit_factor=pf, trades=trades, max_dd=maxdd, ret=ret)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--commission", type=float, default=0.001)
    ap.add_argument("--min-trades", type=int, default=50, help="guardrail: ignore configs with fewer trades")
    ap.add_argument("--out", default="reports/tuning_cluster.json")
    args = ap.parse_args()

    df = pd.read_csv(args.csv, parse_dates=[0], index_col=0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df = calculate_indicators(df)

    grid = {
        "cluster_spread": [6.0, 8.0, 10.0, 12.0],
        "consolidation_bars": [3, 5, 7],
        "extreme_level": [10.0, 20.0],
        "seq_window": [2, 4, 6],
        "slope_th": [0.0],
    }

    keys = list(grid.keys())
    best: Result | None = None
    results: list[dict] = []

    for values in itertools.product(*[grid[k] for k in keys]):
        params = dict(zip(keys, values))
        r = run_once(df, params, args.commission)
        results.append({
            **params,
            "profit_factor": r.profit_factor,
            "trades": r.trades,
            "max_drawdown_pct": r.max_dd,
            "return_pct": r.ret,
        })

        if r.trades < args.min_trades or r.profit_factor is None:
            continue

        if best is None or (r.profit_factor > (best.profit_factor or -1)):
            best = r

    out = {
        "best": None if best is None else {
            "params": best.params,
            "profit_factor": best.profit_factor,
            "trades": best.trades,
            "max_drawdown_pct": best.max_dd,
            "return_pct": best.ret,
        },
        "grid": grid,
        "results": results,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    if best is None:
        print("No configuration met min-trades guardrail")
    else:
        print(json.dumps(out["best"], indent=2))


if __name__ == "__main__":
    main()
