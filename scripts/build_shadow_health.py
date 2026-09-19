#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from twstock_pipeline.calendar import latest_expected_trading_date

parser = argparse.ArgumentParser()
parser.add_argument("--data-root", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = args.data_root
patterns = {
    "market": "daily/tw/*.json",
    "institutional": "daily/institutional/*.json",
    "margin": "daily/tw_market_margin/*.json",
    "financial": "fundamentals/official_latest.json",
    "revenue": "monthly/revenue/latest.json",
    "tdcc": "weekly/tdcc/latest.json",
    "etf": "quant/etf/outputs/latest_snapshot.json",
    "fx": "meta/exchange_rate_history.json",
}
domains = {}
expected_trading = latest_expected_trading_date(date.today(), root)
for domain, pattern in patterns.items():
    files = sorted(root.glob(pattern))
    latest = None
    if files:
        stem = files[-1].stem
        try:
            latest = date.fromisoformat(stem).isoformat()
        except ValueError:
            latest = datetime.fromtimestamp(files[-1].stat().st_mtime, timezone.utc).date().isoformat()
    expected = expected_trading.isoformat() if domain in {"market", "institutional", "margin"} else date.today().isoformat()
    domains[domain] = {"latest_date": latest, "expected_date": expected, "stale": latest != expected, "status": "healthy" if latest == expected else "missing_output", "output_exists": bool(files)}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "domains": domains}, ensure_ascii=False, indent=2) + "\n")
