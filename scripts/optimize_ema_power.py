from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from backtesting import Backtest, Strategy

from traderlib.regime_heuristic import compute_regime
from traderlib.power_candle import add_power_candle_flags
from traderlib.ma import add_ema


def _clean(x):
    if isinstance(x, float) and math.isnan(x):
        return None
    return x


def profit_factor_from_trades(trades_df) -> float | None:
    """Compute profit factor from backtesting.py _trades df.

    PF = gross_profit / abs(gross_loss)
    If there are no losing trades, PF is treated as a large finite number.
    If there are no trades, returns None.
    """
    if trades_df is None or len(trades_df) == 0:
        return None
    pnl = trades_df["PnL"].astype(float)
    gp = float(pnl[pnl > 0].sum())
    gl = float(pnl[pnl < 0].sum())
    if gp <= 0 and gl >= 0:
        return 0.0
    if gl == 0:
        return 99.0  # cap instead of inf
    return gp / abs(gl)


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


def attach_regime(df5: pd.DataFrame) -> pd.DataFrame:
    df15 = resample_15m(df5)
    reg = compute_regime(df15)
    df15 = df15.copy()
    df15["REGIME"] = reg.regime
    df15["REGIME_CONF"] = reg.confidence
    out = df5.copy()
    out["REGIME"] = df15["REGIME"].reindex(out.index, method="ffill")
    out["REGIME_CONF"] = df15["REGIME_CONF"].reindex(out.index, method="ffill")
    return out


class EmaPowerLS(Strategy):
    ema_fast = 20
    ema_slow = 50
    min_conf = 0.40

    atr_n = 14
    base_sl_atr = 1.5
    base_tp_atr = 1.0
    sl_conf_mult = 0.8
    tp_conf_mult = 1.2

    def init(self):
        df = self.data.df
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
        if i < max(self.ema_slow, self.atr_n) + 10:
            return

        regime = df["REGIME"].iat[i]
        conf = float(df["REGIME_CONF"].iat[i])
        if not math.isfinite(conf) or conf < self.min_conf:
            return
        if regime not in ("TRENDING", "UNKNOWN"):
            return

        fast = float(df["EMA_FAST"].iat[i])
        slow = float(df["EMA_SLOW"].iat[i])
        close = float(df["Close"].iat[i])

        bull_trend = (close > slow) and (fast > slow)
        bear_trend = (close < slow) and (fast < slow)

        bull_power = bool(df["BullPower"].iat[i])
        bear_power = bool(df["BearPower"].iat[i])

        if self.position:
            return

        atr = float(df["ATR"].iat[i])
        if not math.isfinite(atr) or atr <= 0:
            return

        sl_atr = self.base_sl_atr * (1.0 + self.sl_conf_mult * conf)
        tp_atr = self.base_tp_atr * (1.0 + self.tp_conf_mult * conf)
        entry = close

        if bull_trend and bull_power:
            self.buy(sl=entry - sl_atr * atr, tp=entry + tp_atr * atr)
        elif bear_trend and bear_power:
            self.sell(sl=entry + sl_atr * atr, tp=entry - tp_atr * atr)


def score(stats) -> tuple:
    # sort by PF desc, then Sharpe desc, then DD desc (less negative is better)
    pf = _clean(float(stats.get("Profit Factor", float("nan"))))
    sh = _clean(float(stats.get("Sharpe Ratio", float("nan"))))
    dd = _clean(float(stats.get("Max. Drawdown [%]", float("nan"))))
    trades = int(len(stats["_trades"]))
    return (pf if pf is not None else -1e9, sh if sh is not None else -1e9, dd if dd is not None else -1e9, trades)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default="binanceus")
    ap.add_argument("--symbols", default="BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT")
    ap.add_argument("--timeframe", default="5m")
    ap.add_argument("--commission", type=float, default=0.001)
    ap.add_argument("--fast", default="5,10,15,20,25,30")
    ap.add_argument("--slow", default="30,50,70,100,150,200")
    ap.add_argument("--min-trades", type=int, default=50)
    ap.add_argument("--out", default="reports/ema_power_opt.json")
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    fasts = [int(x) for x in args.fast.split(",") if x.strip()]
    slows = [int(x) for x in args.slow.split(",") if x.strip()]

    # Load data once per symbol
    dfs = {}
    for sym in symbols:
        csv = Path("data") / f"{args.exchange}_{sym.replace('/', '-')}_{args.timeframe}.csv"
        if csv.exists():
            dfs[sym] = load_csv(csv)

    results = []

    for f,s in itertools.product(fasts, slows):
        if f >= s:
            continue
        total_trades = 0
        weighted_pf_num = 0.0
        weighted_pf_den = 0
        per = {}

        for sym, df5 in dfs.items():
            df = attach_regime(df5)
            df = add_ema(df, f, "EMA_FAST")
            df = add_ema(df, s, "EMA_SLOW")
            df = add_power_candle_flags(df, lookback=10, close_near_top=0.35, body_ratio_min=0.50)
            df = df.dropna().copy()

            EmaPowerLS.ema_fast = f
            EmaPowerLS.ema_slow = s

            bt = Backtest(df, EmaPowerLS, cash=1_000_000, commission=args.commission)
            st = bt.run()
            trades_df = st["_trades"]
            trades = int(len(trades_df))
            pf = profit_factor_from_trades(trades_df)
            sh = _clean(float(st.get("Sharpe Ratio", float("nan"))))
            dd = _clean(float(st.get("Max. Drawdown [%]", float("nan"))))

            per[sym] = {"trades": trades, "pf": pf, "sharpe": sh, "dd": dd}
            total_trades += trades
            if pf is not None and trades > 0:
                weighted_pf_num += pf * trades
                weighted_pf_den += trades

        weighted_pf = None
        if weighted_pf_den:
            weighted_pf = weighted_pf_num / weighted_pf_den

        results.append({
            "ema_fast": f,
            "ema_slow": s,
            "total_trades": total_trades,
            "weighted_pf": weighted_pf,
            "per_symbol": per,
        })

    # Filter candidates that have enough trades
    candidates = [r for r in results if r["total_trades"] >= args.min_trades and r["weighted_pf"] is not None]
    candidates.sort(key=lambda r: (r["weighted_pf"], r["total_trades"]), reverse=True)

    out = {
        "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "symbols": symbols,
        "grid": {"fast": fasts, "slow": slows},
        "min_trades": args.min_trades,
        "top": candidates[:10],
        "all": results,
        "note": "Coarse EMA search for TRENDING/UNKNOWN regime with power candles. Next: fine search around winners + add RANGING module at 15m key levels.",
    }

    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    if candidates:
        best = candidates[0]
        print(json.dumps({"best": {"ema_fast": best["ema_fast"], "ema_slow": best["ema_slow"], "weighted_pf": best["weighted_pf"], "total_trades": best["total_trades"]}}, indent=2))
    else:
        print("No candidates met min-trades")


if __name__ == "__main__":
    main()
