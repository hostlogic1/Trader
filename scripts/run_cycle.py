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


def main():
    # Keep these small and safe; expand later.
    exchange = os.environ.get("TRADER_EXCHANGE", "coinbase")
    symbol = os.environ.get("TRADER_SYMBOL", "SOL/USDC")

    # Rolling lookback for refresh (candles are stored locally, not committed)
    since_dt = datetime.now(timezone.utc) - timedelta(days=int(os.environ.get("TRADER_LOOKBACK_DAYS", "180")))
    since = since_dt.date().isoformat()

    commission = float(os.environ.get("TRADER_COMMISSION", "0.001"))

    # Ensure git uses the deploy-key ssh config
    os.environ.setdefault("GIT_SSH_COMMAND", "ssh -F /data/.openclaw/workspace/.ssh/config")

    sh(["python3", "scripts/update_status.py", "--phase", "research", "--task", f"Cycle: fetch OHLCV + baseline A/B ({exchange} {symbol})", "--notes", "Refreshing candles and re-running baseline A/B (1m vs 5m). Winner = higher profit factor."])

    sh(["python3", "scripts/fetch_ohlcv.py", "--exchange", exchange, "--symbol", symbol, "--timeframe", "1m", "--since", since, "--limit", "1000"])
    sh(["python3", "scripts/fetch_ohlcv.py", "--exchange", exchange, "--symbol", symbol, "--timeframe", "5m", "--since", since, "--limit", "1000"])

    csv_1m = f"data/{exchange}_{symbol.replace('/', '-')}_1m.csv"
    csv_5m = f"data/{exchange}_{symbol.replace('/', '-')}_5m.csv"

    # Run A/B and write report (reports/ is local ignored, but we’ll also push a tiny summary to docs/status.json)
    out_json = "reports/ab_result.json"
    sh(["python3", "scripts/run_baseline_ab.py", "--csv-1m", csv_1m, "--csv-5m", csv_5m, "--commission", str(commission), "--out", out_json])

    result = json.loads((REPO / out_json).read_text())

    summary = {
        "asof": utc_now_iso(),
        "exchange": exchange,
        "symbol": symbol,
        "commission": commission,
        "winner": result.get("winner"),
        "pf_1m": result.get("1m", {}).get("profit_factor"),
        "pf_5m": result.get("5m", {}).get("profit_factor"),
    }

    # Update status.json with last_backtest summary
    status_path = REPO / "docs" / "status.json"
    status = json.loads(status_path.read_text())
    status["phase"] = "research"
    status["current_task"] = "Idle (last cycle complete)"
    status["last_backtest"] = summary
    status["notes"] = "Baseline A/B rerun complete. Next: add key-level + market-structure gating, then regime strategies and selector."
    status["updated_at"] = utc_now_iso()
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")

    # Commit + push status updates
    sh(["git", "add", "docs/status.json"])
    # Avoid failing if no change
    try:
        sh(["git", "commit", "-m", f"Status: baseline A/B cycle {summary['asof']}"])
    except subprocess.CalledProcessError as e:
        if "nothing to commit" not in e.output.decode("utf-8", errors="replace"):
            raise
    sh(["git", "push", "origin", "main"])


if __name__ == "__main__":
    main()
