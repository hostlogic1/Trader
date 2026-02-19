from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from backtesting import Backtest, Strategy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from traderlib.regime_heuristic import compute_regime
from traderlib.power_candle import add_power_candle_flags
from traderlib.ma import add_sma


def _clean(x):
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=[0], index_col=0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index, utc=True)
    return df


def resample_15m(df5: pd.DataFrame) -> pd.DataFrame:
    return (
        df5.resample("15min")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna()
    )


def attach_regime_to_5m(df5: pd.DataFrame) -> pd.DataFrame:
    df15 = resample_15m(df5)
    reg = compute_regime(df15)
    df15 = df15.copy()
    df15["REGIME"] = reg.regime
    df15["REGIME_CONF"] = reg.confidence

    # forward-fill 15m labels down to 5m
    df5x = df5.copy()
    df5x["REGIME"] = df15["REGIME"].reindex(df5x.index, method="ffill")
    df5x["REGIME_CONF"] = df15["REGIME_CONF"].reindex(df5x.index, method="ffill")
    return df5x


class RegimeSmaPowerLong(Strategy):
    sma_fast = 20
    sma_slow = 50

    # confidence gate
    min_conf = 0.55

    # ATR exits scaled by confidence
    atr_n = 14
    base_sl_atr = 1.5
    base_tp_atr = 1.0
    sl_conf_mult = 0.8
    tp_conf_mult = 1.2

    def init(self):
        df = self.data.df
        # precompute ATR
        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        close = df["Close"].astype(float)
        tr = pd.concat([
            (high - low).abs(),
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(self.atr_n).mean()

    def next(self):
        df = self.data.df
        i = len(df) - 1
        if i < max(self.sma_slow, self.atr_n) + 5:
            return

        # require regime trending
        if df["REGIME"].iat[i] != "TRENDING":
            return
        conf = float(df["REGIME_CONF"].iat[i])
        if not math.isfinite(conf) or conf < self.min_conf:
            return

        # SMA trend filter
        fast = float(df["SMA_FAST"].iat[i])
        slow = float(df["SMA_SLOW"].iat[i])
        close = float(df["Close"].iat[i])
        if not (close > slow and fast > slow):
            return

        # Power candle trigger
        if not bool(df["BullPower"].iat[i]):
            return

        if self.position:
            return

        atr = float(df["ATR"].iat[i])
        if not math.isfinite(atr) or atr <= 0:
            return

        sl_atr = self.base_sl_atr * (1.0 + self.sl_conf_mult * conf)
        tp_atr = self.base_tp_atr * (1.0 + self.tp_conf_mult * conf)

        entry = close
        sl = entry - sl_atr * atr
        tp = entry + tp_atr * atr
        self.buy(sl=sl, tp=tp)


@dataclass
class SymResult:
    symbol: str
    trades: int
    pf: float | None
    sharpe: float | None
    maxdd: float | None
    ret: float | None


def backtest_symbol(df5: pd.DataFrame, commission: float, sma_fast: int, sma_slow: int) -> SymResult:
    df = attach_regime_to_5m(df5)
    df = add_sma(df, sma_fast, "SMA_FAST")
    df = add_sma(df, sma_slow, "SMA_SLOW")
    df = add_power_candle_flags(df, lookback=7)
    df = df.dropna().copy()

    # inject params
    RegimeSmaPowerLong.sma_fast = sma_fast
    RegimeSmaPowerLong.sma_slow = sma_slow

    bt = Backtest(df, RegimeSmaPowerLong, cash=10_000, commission=commission)
    stats = bt.run()

    trades = int(len(stats["_trades"]))
    pf = _clean(float(stats.get("Profit Factor", float("nan"))))
    sharpe = _clean(float(stats.get("Sharpe Ratio", float("nan"))))
    maxdd = _clean(float(stats.get("Max. Drawdown [%]", float("nan"))))
    ret = _clean(float(stats.get("Return [%]", float("nan"))))

    return SymResult(symbol="", trades=trades, pf=pf, sharpe=sharpe, maxdd=maxdd, ret=ret)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default="binanceus")
    ap.add_argument("--symbols", default="BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT")
    ap.add_argument("--timeframe", default="5m")
    ap.add_argument("--commission", type=float, default=0.001)
    ap.add_argument("--sma-fast", type=int, default=20)
    ap.add_argument("--sma-slow", type=int, default=50)
    ap.add_argument("--out", default="reports/regime_sma_power_basket.json")
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    per = {}
    total_trades = 0
    weighted_pf_num = 0.0
    weighted_pf_den = 0

    for sym in symbols:
        csv = Path("data") / f"{args.exchange}_{sym.replace('/', '-')}_{args.timeframe}.csv"
        if not csv.exists():
            per[sym] = {"error": f"missing {csv}"}
            continue
        df5 = load_csv(csv)
        r = backtest_symbol(df5, args.commission, args.sma_fast, args.sma_slow)
        r.symbol = sym
        per[sym] = {
            "trades": r.trades,
            "profit_factor": r.pf,
            "sharpe": r.sharpe,
            "max_drawdown_pct": r.maxdd,
            "return_pct": r.ret,
        }
        total_trades += r.trades
        if r.pf is not None and r.trades > 0:
            weighted_pf_num += r.pf * r.trades
            weighted_pf_den += r.trades

    agg_pf = None
    if weighted_pf_den > 0:
        agg_pf = weighted_pf_num / weighted_pf_den

    out = {
        "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": "15m regime+confidence (heuristic) -> 5m SMA trend + power candle entry",
        "params": {"sma_fast": args.sma_fast, "sma_slow": args.sma_slow},
        "exchange": args.exchange,
        "timeframe": args.timeframe,
        "commission": args.commission,
        "total_trades": total_trades,
        "weighted_profit_factor": agg_pf,
        "per_symbol": per,
        "note": "This is v0. TRENDING-only entries. Next: add RANGING strategy at 15m key levels + confidence-scaled TP/SL + SMA coarse-to-fine sweep across Top10 basket.",
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"total_trades": total_trades, "weighted_pf": agg_pf}, indent=2))


if __name__ == "__main__":
    main()
