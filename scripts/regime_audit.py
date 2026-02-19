from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def efficiency_ratio(close: pd.Series, n: int) -> pd.Series:
    direction = (close - close.shift(n)).abs()
    volatility = (close.diff().abs()).rolling(n).sum()
    return direction / volatility


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", default="reports/regime_audit.json")
    args = ap.parse_args()

    df = pd.read_csv(args.csv, parse_dates=[0], index_col=0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index, utc=True)

    # Simple regime heuristic (audit): ER + ATR%
    close = df["Close"]
    er50 = efficiency_ratio(close, 50)

    tr = pd.concat([
        (df["High"] - df["Low"]),
        (df["High"] - df["Close"].shift(1)).abs(),
        (df["Low"] - df["Close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()
    atrp = atr14 / close

    # Initial thresholds (TUNABLE)
    trending = er50 > 0.35
    ranging = er50 < 0.25
    volatile = atrp > 0.06

    # Resolve priority: volatile > trending > ranging > unknown
    regime = pd.Series("UNKNOWN", index=df.index)
    regime[ranging] = "RANGING"
    regime[trending] = "TRENDING"
    regime[volatile] = "VOLATILE"

    counts = regime.value_counts(dropna=False).to_dict()

    out = {
        "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bars": int(len(df)),
        "thresholds": {"er_trend": 0.35, "er_range": 0.25, "atrp_volatile": 0.06},
        "counts": counts,
        "note": "Audit-only. Next: add hysteresis + confidence and use regime to select strategy variant (trend pullback vs range reversal vs volatile selective)."
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
