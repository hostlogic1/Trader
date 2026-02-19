from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/summary.json")
    args = ap.parse_args()

    # This is a lightweight placeholder; the dashboard reads status.json.
    out = {
        "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": "Completed structure/regime audits and basket backtests. Next: implement causal key-level zones + BOS rules and wire regime selector to switch entry modes.",
    }

    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
