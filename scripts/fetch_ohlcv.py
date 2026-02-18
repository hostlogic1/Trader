from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import ccxt
import pandas as pd


def iso_utc(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat(timespec="seconds")


def fetch_ohlcv(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    since: Optional[str],
    limit: int,
) -> pd.DataFrame:
    ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    ex.load_markets()

    if symbol not in ex.symbols:
        raise SystemExit(f"Symbol {symbol} not available on {exchange_id}. Example symbols: {ex.symbols[:20]}")

    since_ms = None
    if since:
        # since is ISO date or datetime; treat as UTC
        dt = datetime.fromisoformat(since)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        since_ms = int(dt.timestamp() * 1000)

    rows = []
    prev_last = None
    while True:
        batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since_ms, limit=limit)
        if not batch:
            break
        rows.extend(batch)
        last = batch[-1][0]
        if prev_last is not None and last <= prev_last:
            # Safety against infinite loops if exchange repeats last candle
            break
        prev_last = last
        # advance 1ms to avoid duplicates
        since_ms = last + 1

    df = pd.DataFrame(rows, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"])
    df["Datetime"] = pd.to_datetime(df["Timestamp"], unit="ms", utc=True)
    df = df.set_index("Datetime").drop(columns=["Timestamp"])

    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default="coinbase", help="ccxt exchange id, e.g., coinbase or binance")
    ap.add_argument("--symbol", default="SOL/USDC")
    ap.add_argument("--timeframe", default="1m")
    ap.add_argument("--since", default=None, help="ISO date/datetime in UTC, e.g. 2025-12-01")
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    df = fetch_ohlcv(args.exchange, args.symbol, args.timeframe, args.since, args.limit)

    out = args.out
    if out is None:
        safe_sym = args.symbol.replace("/", "-")
        out = f"data/{args.exchange}_{safe_sym}_{args.timeframe}.csv"

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path)
    print(f"Saved {len(df)} bars to {out_path} (from {df.index.min()} to {df.index.max()})")


if __name__ == "__main__":
    main()
