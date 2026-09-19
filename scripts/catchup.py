#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from twstock_pipeline.calendar import trading_dates
from twstock_pipeline.health import build_health
from twstock_pipeline.state import load_state, save_state
from twstock_pipeline import collectors


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic, restartable public catch-up controller")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--state", type=Path, default=Path("state/pipeline_state.json"))
    parser.add_argument("--health", type=Path, default=Path("data/data_health.json"))
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    state = load_state(args.state)
    calendar_file = args.data_root / "reference" / "market_calendar.json"
    holidays = set()
    if calendar_file.exists():
        holidays = {date.fromisoformat(value) for value in json.loads(calendar_file.read_text()).get("holidays", [])}
    expected = trading_dates(date(2000, 1, 1), args.today, holidays)
    dispatch = {"market": collectors.sync_market, "institutional": collectors.sync_institutional, "margin": collectors.sync_margin}
    for domain, details in state.items():
        last = details.get("last_success")
        start = date.fromisoformat(last) + timedelta(days=1) if last else (expected[-1] if expected else args.today)
        missing = [day for day in expected if day >= start]
        details["last_attempt"] = args.today.isoformat()
        details["pending_dates"] = [day.isoformat() for day in missing]
        details["status"] = "pending" if missing else "current"
        if domain in dispatch and missing:
            # Bounded catch-up: one explicit date per invocation protects the
            # upstream API and makes a failure restartable without advancing state.
            target = missing[0]
            output = dispatch[domain](target, args.data_root)
            if not output.exists() or output.stat().st_size == 0:
                raise RuntimeError(f"{domain} output validation failed: {output}")
            details["last_success"] = target.isoformat()
            details["status"] = "healthy"
            details["pending_dates"] = [day.isoformat() for day in missing[1:]]
    save_state(args.state, state)
    args.health.parent.mkdir(parents=True, exist_ok=True)
    args.health.write_text(json.dumps(build_health(state, expected[-1] if expected else args.today, args.data_root), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
