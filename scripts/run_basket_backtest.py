from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
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


def backtest_one(csv_path: Path, commission: float) -> dict:
    df = pd.read_csv(csv_path, parse_dates=[0], index_col=0)
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

    bt = Backtest(df, BaselineStochClusterLongOnly, cash=10_000, commission=commission)
    stats = bt.run()

    trades = int(len(stats["_trades"]))
    pf = _clean(float(stats.get("Profit Factor", float("nan"))))
    ret = _clean(float(stats.get("Return [%]", float("nan"))))
    dd = _clean(float(stats.get("Max. Drawdown [%]", float("nan"))))
    sharpe = _clean(float(stats.get("Sharpe Ratio", float("nan"))))

    return {
        "trades": trades,
        "profit_factor": pf,
        "return_pct": ret,
        "max_drawdown_pct": dd,
        "sharpe": sharpe,
        "bars": int(len(df)),
        "start": str(df.index.min()),
        "end": str(df.index.max()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default="coinbase")
    ap.add_argument("--symbols", default="SOL/USDC,BTC/USDC,ETH/USDC")
    ap.add_argument("--timeframe", default="5m")
    ap.add_argument("--commission", type=float, default=0.001)
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out", default="reports/basket_backtest.json")
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    results = {}
    total_trades = 0

    for sym in symbols:
        safe_sym = sym.replace("/", "-")
        csv_path = Path(args.data_dir) / f"{args.exchange}_{safe_sym}_{args.timeframe}.csv"
        if not csv_path.exists():
            results[sym] = {"error": f"missing data file {csv_path}"}
            continue
        r = backtest_one(csv_path, args.commission)
        results[sym] = r
        total_trades += int(r.get("trades") or 0)

    out = {
        "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "exchange": args.exchange,
        "timeframe": args.timeframe,
        "commission": args.commission,
        "symbols": symbols,
        "total_trades": total_trades,
        "per_symbol": results,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    print(json.dumps({"total_trades": total_trades}, indent=2))


if __name__ == "__main__":
    main()
