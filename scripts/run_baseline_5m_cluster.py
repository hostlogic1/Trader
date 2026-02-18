from __future__ import annotations

import argparse
import json
import math
import sys
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


def _jsonify(v):
    try:
        import numpy as np
        import pandas as pd

        if isinstance(v, np.generic):
            return v.item()
        if isinstance(v, pd.Timedelta):
            return str(v)
        if isinstance(v, pd.Timestamp):
            return v.isoformat()
    except Exception:
        pass
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    return v


def _clean_stats(d: dict) -> dict:
    d = dict(d)
    d.pop("_equity_curve", None)
    d.pop("_trades", None)
    d.pop("_strategy", None)
    return {k: _jsonify(v) for k, v in d.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--cash", type=float, default=10_000)
    ap.add_argument("--commission", type=float, default=0.001)
    ap.add_argument("--out", default="reports/baseline_5m_cluster.json")
    args = ap.parse_args()

    df = pd.read_csv(args.csv, parse_dates=[0], index_col=0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()

    df = calculate_indicators(df)
    df = detect_cluster_sequence_breakout(
        df,
        cluster_spread=8.0,
        consolidation_bars=5,
        extreme_level=20.0,
        seq_window=4,
        slope_th=0.0,
    )

    bt = Backtest(df, BaselineStochClusterLongOnly, cash=args.cash, commission=args.commission)
    stats = bt.run()

    trades = stats["_trades"]
    n_trades = int(len(trades))

    pf = None
    if "Profit Factor" in stats:
        pf = _clean(float(stats["Profit Factor"]))

    out = {
        "profit_factor": pf,
        "trades": n_trades,
        "stats": _clean_stats(stats.to_dict()),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    print(json.dumps({"profit_factor": pf, "trades": n_trades}, indent=2))


if __name__ == "__main__":
    main()
