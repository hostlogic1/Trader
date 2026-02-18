from __future__ import annotations

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


def _load_status() -> dict:
    p = REPO / "docs" / "status.json"
    return json.loads(p.read_text())


def _save_status(status: dict) -> None:
    p = REPO / "docs" / "status.json"
    p.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")


def _commit_push(msg: str) -> None:
    sh(["git", "add", "docs/status.json"])
    try:
        sh(["git", "commit", "-m", msg])
    except subprocess.CalledProcessError as e:
        if "nothing to commit" not in e.output.decode("utf-8", errors="replace"):
            raise
    sh(["git", "push", "origin", "main"])


def main():
    # Safe, low-API pipeline: one step per run.
    exchange = os.environ.get("TRADER_EXCHANGE", "coinbase")
    symbol = os.environ.get("TRADER_SYMBOL", "SOL/USDC")

    since_dt = datetime.now(timezone.utc) - timedelta(days=int(os.environ.get("TRADER_LOOKBACK_DAYS", "180")))
    since = since_dt.date().isoformat()

    commission = float(os.environ.get("TRADER_COMMISSION", "0.001"))

    # Ensure git uses the deploy-key ssh config
    os.environ.setdefault("GIT_SSH_COMMAND", "ssh -F /data/.openclaw/workspace/.ssh/config")

    status = _load_status()
    step = status.get("pipeline_step") or "fetch_5m"

    if step == "fetch_5m":
        status["phase"] = "research"
        status["current_task"] = f"Fetching 5m OHLCV ({exchange} {symbol})"
        status["notes"] = f"Refreshing 5m candles since {since}. Next: baseline backtest."
        status["updated_at"] = utc_now_iso()
        _save_status(status)
        _commit_push(f"Status: {status['current_task']}"
        )

        sh(["python3", "scripts/fetch_ohlcv.py", "--exchange", exchange, "--symbol", symbol, "--timeframe", "5m", "--since", since, "--limit", "1000"])
        status["pipeline_step"] = "backtest_5m"

    elif step == "backtest_5m":
        status["phase"] = "research"
        status["current_task"] = "Running 5m baseline backtest (cluster+sequence)"
        status["notes"] = "Goal: get stable trade generation; next step is parameter tuning for trade frequency + profit factor."
        status["updated_at"] = utc_now_iso()
        _save_status(status)
        _commit_push(f"Status: {status['current_task']}")

        csv_5m = f"data/{exchange}_{symbol.replace('/', '-')}_5m.csv"
        out_json = "reports/baseline_5m_cluster.json"
        sh(["python3", "scripts/run_baseline_5m_cluster.py", "--csv", csv_5m, "--commission", str(commission), "--out", out_json])
        result = json.loads((REPO / out_json).read_text())

        status["last_backtest"] = {
            "asof": utc_now_iso(),
            "exchange": exchange,
            "symbol": symbol,
            "timeframe": "5m",
            "model": "cluster+sequence (looser baseline)",
            "trades": result.get("trades"),
            "profit_factor": result.get("profit_factor"),
            "return_pct": result.get("stats", {}).get("Return [%]"),
            "max_drawdown_pct": result.get("stats", {}).get("Max. Drawdown [%]"),
        }
        status["pipeline_step"] = "tune_params"

    elif step == "tune_params":
        status["phase"] = "tuning"
        status["current_task"] = "Tuning cluster/sequence params (light grid)"
        status["notes"] = "Searching for higher profit factor while increasing trade count. Next: apply best params + rerun backtest."
        status["updated_at"] = utc_now_iso()
        _save_status(status)
        _commit_push(f"Status: {status['current_task']}")

        csv_5m = f"data/{exchange}_{symbol.replace('/', '-')}_5m.csv"
        out_json = "reports/tuning_cluster.json"
        sh(["python3", "scripts/tune_cluster_params.py", "--csv", csv_5m, "--commission", str(commission), "--min-trades", "50", "--out", out_json])
        tuning = json.loads((REPO / out_json).read_text())
        status["last_optimization"] = {
            "asof": utc_now_iso(),
            "kind": "grid",
            "best": tuning.get("best"),
        }
        status["pipeline_step"] = "backtest_5m"

    else:
        status["phase"] = "research"
        status["current_task"] = "Idle"
        status["notes"] = f"Unknown pipeline_step={step}; resetting to fetch_5m"
        status["pipeline_step"] = "fetch_5m"

    status["updated_at"] = utc_now_iso()
    _save_status(status)
    _commit_push(f"Status: pipeline step complete ({step})")


if __name__ == "__main__":
    main()
