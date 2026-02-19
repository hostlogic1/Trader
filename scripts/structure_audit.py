from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def pivots(series: pd.Series, left: int = 2, right: int = 2, mode: str = "high") -> pd.Series:
    """Fractal pivots (non-causal visualization); for research audit only.

    For backtesting signals we will implement causal pivot detection later.
    """
    s = series
    out = pd.Series(False, index=s.index)
    for i in range(left, len(s) - right):
        window = s.iloc[i - left : i + right + 1]
        if mode == "high":
            out.iloc[i] = s.iloc[i] == window.max()
        else:
            out.iloc[i] = s.iloc[i] == window.min()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", default="reports/structure_audit.json")
    args = ap.parse_args()

    df5 = pd.read_csv(args.csv, parse_dates=[0], index_col=0)
    df5 = df5[["Open", "High", "Low", "Close", "Volume"]].copy()
    df5.index = pd.to_datetime(df5.index, utc=True)

    # Build 15m and 1h bars from 5m
    df15 = df5.resample("15min").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
    df1h = df5.resample("1h").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()

    # Pivot counts (audit only)
    ph15 = pivots(df15["High"], 2, 2, "high")
    pl15 = pivots(df15["Low"], 2, 2, "low")

    # Simple HH/HL counts on 15m pivots
    pivot_highs = df15.loc[ph15, "High"]
    pivot_lows = df15.loc[pl15, "Low"]

    hh = int((pivot_highs.diff() > 0).sum())
    lh = int((pivot_highs.diff() < 0).sum())
    hl = int((pivot_lows.diff() > 0).sum())
    ll = int((pivot_lows.diff() < 0).sum())

    out = {
        "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_tf": "5m",
        "derived": {
            "15m_bars": int(len(df15)),
            "1h_bars": int(len(df1h)),
        },
        "pivot_params": {"left": 2, "right": 2},
        "15m": {
            "pivot_highs": int(ph15.sum()),
            "pivot_lows": int(pl15.sum()),
            "hh": hh,
            "lh": lh,
            "hl": hl,
            "ll": ll,
        },
        "note": "Audit counts only. Next: implement causal swing detection for backtests + key-level zones and BOS logic (HL break -> LH/LL) gated near 15m levels."
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
