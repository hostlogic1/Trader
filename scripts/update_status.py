from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def update_status(**patch: Any) -> None:
    status_path = Path(__file__).resolve().parents[1] / "docs" / "status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)

    if status_path.exists():
        data = json.loads(status_path.read_text())
    else:
        data = {}

    data.setdefault("updated_at", "")
    data.setdefault("phase", "setup")
    data.setdefault("current_task", "")
    data.setdefault("last_backtest", None)
    data.setdefault("last_optimization", None)
    data.setdefault("notes", "")

    data.update(patch)
    data["updated_at"] = utc_now_iso()

    status_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default=None)
    ap.add_argument("--task", default=None)
    ap.add_argument("--notes", default=None)
    args = ap.parse_args()

    patch = {}
    if args.phase is not None:
        patch["phase"] = args.phase
    if args.task is not None:
        patch["current_task"] = args.task
    if args.notes is not None:
        patch["notes"] = args.notes

    update_status(**patch)
