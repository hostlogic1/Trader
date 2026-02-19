from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

import ccxt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default="binanceus")
    ap.add_argument("--symbols", default="BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT")
    ap.add_argument("--timeframe", default="5m")
    ap.add_argument("--lookback-days", type=int, default=180)
    ap.add_argument("--limit", type=int, default=1000)
    args = ap.parse_args()

    ex = getattr(ccxt, args.exchange)({"enableRateLimit": True})
    ex.load_markets()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    since_dt = datetime.now(timezone.utc) - timedelta(days=args.lookback_days)
    since_ms = int(since_dt.timestamp() * 1000)

    for sym in symbols:
        if sym not in ex.symbols:
            print(f"SKIP {sym}: not on {args.exchange}")
            continue

        rows = []
        prev_last = None
        s = since_ms
        while True:
            batch = ex.fetch_ohlcv(sym, timeframe=args.timeframe, since=s, limit=args.limit)
            if not batch:
                break
            rows.extend(batch)
            last = batch[-1][0]
            if prev_last is not None and last <= prev_last:
                break
            prev_last = last
            s = last + 1
            if len(batch) < args.limit:
                break

        out = Path("data") / f"{args.exchange}_{sym.replace('/', '-')}_{args.timeframe}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)

        import pandas as pd

        df = pd.DataFrame(rows, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"])
        df["Datetime"] = pd.to_datetime(df["Timestamp"], unit="ms", utc=True)
        df = df.set_index("Datetime").drop(columns=["Timestamp"])
        df.to_csv(out)
        if len(df):
            print(f"Saved {sym} {args.timeframe}: {len(df)} bars ({df.index.min()} → {df.index.max()})")
        else:
            print(f"Saved {sym} {args.timeframe}: 0 bars")


if __name__ == "__main__":
    main()
