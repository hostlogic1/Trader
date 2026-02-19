from __future__ import annotations

"""Regime-only hourly research cycle.

Goals:
- Stop running legacy stochastic experiments.
- Fetch/update Top-10 universe data (5m) from a chosen exchange.
- Run regime+confidence (15m) -> 5m EMA trend + bull/bear power candle (long+short).
- Run coarse EMA optimizer as a candidate generator.
- Push a small summary to docs/status.json.

This is research/backtest only.
"""

import json
import os
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def sh(cmd: list[str], timeout: int = 3600) -> str:
    out = subprocess.check_output(cmd, cwd=REPO, stderr=subprocess.STDOUT, timeout=timeout)
    return out.decode("utf-8", errors="replace")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_status() -> dict:
    p = REPO / "docs" / "status.json"
    return json.loads(p.read_text())


def save_status(s: dict) -> None:
    p = REPO / "docs" / "status.json"
    p.write_text(json.dumps(s, indent=2, sort_keys=True) + "\n")


def commit_push(msg: str) -> None:
    sh(["git", "add", "docs/status.json"])
    try:
        sh(["git", "commit", "-m", msg])
    except subprocess.CalledProcessError as e:
        if "nothing to commit" not in e.output.decode("utf-8", errors="replace"):
            raise
    sh(["git", "push", "origin", "main"])


def main():
    # Ensure git uses deploy-key config
    os.environ["GIT_SSH_COMMAND"] = os.environ.get(
        "GIT_SSH_COMMAND", "ssh -F /data/.openclaw/workspace/.ssh/config"
    )

    exchange = os.environ.get("TRADER_EXCHANGE", "binanceus")
    timeframe = os.environ.get("TRADER_TIMEFRAME", "5m")
    commission = float(os.environ.get("TRADER_COMMISSION", "0.001"))

    # Default top-10-ish basket; can be overridden.
    symbols = os.environ.get(
        "TRADER_SYMBOLS",
        "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT,ADA/USDT,DOGE/USDT,AVAX/USDT,LINK/USDT,MATIC/USDT",
    )

    lookback_days = int(os.environ.get("TRADER_LOOKBACK_DAYS", "180"))

    status = load_status()
    status["phase"] = "research"
    status["current_task"] = "Regime-only cycle: fetch universe + EMA power-candle L/S + coarse EMA search"
    status["notes"] = "Legacy stochastic pipeline disabled. This cycle updates regime+confidence strategy only."
    status["updated_at"] = utc_now_iso()
    status["pipeline_step"] = "regime_only"
    save_status(status)
    commit_push("Status: start regime-only cycle")

    # Fetch universe (5m)
    sh(
        [
            "python3",
            "scripts/fetch_universe.py",
            "--exchange",
            exchange,
            "--symbols",
            symbols,
            "--timeframe",
            timeframe,
            "--lookback-days",
            str(lookback_days),
            "--limit",
            "1000",
        ],
        timeout=3600,
    )

    # Run backtest at default EMA pair
    out_bt = "reports/regime_ema_power_basket.json"
    sh(
        [
            "python3",
            "scripts/run_regime_sma_power_basket.py",
            "--exchange",
            exchange,
            "--symbols",
            symbols,
            "--timeframe",
            timeframe,
            "--commission",
            str(commission),
            "--ema-fast",
            os.environ.get("TRADER_EMA_FAST", "20"),
            "--ema-slow",
            os.environ.get("TRADER_EMA_SLOW", "50"),
            "--out",
            out_bt,
        ],
        timeout=3600,
    )

    # Coarse optimizer (candidate generator)
    out_opt = "reports/ema_power_opt.json"
    sh(
        [
            "python3",
            "scripts/optimize_ema_power.py",
            "--exchange",
            exchange,
            "--symbols",
            symbols,
            "--timeframe",
            timeframe,
            "--commission",
            str(commission),
            "--min-trades",
            os.environ.get("TRADER_OPT_MIN_TRADES", "50"),
            "--out",
            out_opt,
        ],
        timeout=3600,
    )

    bt = json.loads((REPO / out_bt).read_text())
    opt = json.loads((REPO / out_opt).read_text())

    top = opt.get("top", [])
    best = top[0] if top else None

    status = load_status()
    status["phase"] = "research"
    status["current_task"] = "Regime-only cycle complete"
    status["last_research"] = {
        "asof": utc_now_iso(),
        "model": bt.get("model"),
        "params": bt.get("params"),
        "total_trades": bt.get("total_trades"),
        "weighted_profit_factor": bt.get("weighted_profit_factor"),
        "best_ema_candidate": None if best is None else {
            "ema_fast": best.get("ema_fast"),
            "ema_slow": best.get("ema_slow"),
            "weighted_pf": best.get("weighted_pf"),
            "total_trades": best.get("total_trades"),
        },
        "note": "Next: implement RANGING key-level module + regime hysteresis/confidence and rerun.",
    }
    status["notes"] = status["last_research"]["note"]
    status["updated_at"] = status["last_research"]["asof"]

    save_status(status)
    commit_push("Status: regime-only cycle complete")


if __name__ == "__main__":
    main()
