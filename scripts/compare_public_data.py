#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from twstock_pipeline.compat import latest_output


def inspect(path: Path) -> dict:
    result = {"path": str(path), "exists": path.exists(), "bytes": path.stat().st_size if path.exists() else 0, "json": False, "keys": [], "error": None}
    if not path.exists():
        return result
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        result["json"] = True
        result["keys"] = sorted(payload.keys()) if isinstance(payload, dict) else []
        result["empty"] = not bool(payload)
    except Exception as exc:
        result["error"] = str(exc)
    return result


def compare(old: Path, shadow: Path) -> dict:
    left, right = inspect(old), inspect(shadow)
    status = "PASS"
    reasons = []
    if not right["exists"] or not right["json"] or right.get("empty"):
        status = "FAIL"
        reasons.append("shadow output missing, invalid JSON, or empty")
    if left["exists"] and left["json"] and right["json"]:
        missing = sorted(set(left["keys"]) - set(right["keys"]))
        if missing:
            status = "FAIL"
            reasons.append(f"missing keys: {missing}")
    elif left["exists"]:
        status = "WARN"
        reasons.append("legacy output could not be parsed")
    return {"status": status, "reasons": reasons, "old": left, "shadow": right}


def institutional_boundary(old: Path, shadow: Path) -> dict:
    result = compare(old, shadow)
    result["status"] = "NOT_APPLICABLE_PRIVATE"
    result["reasons"] = ["legacy leaderboard is private-derived; public gate covers official T86 base only"]
    return result


parser = argparse.ArgumentParser()
parser.add_argument("--old-root", type=Path, required=True)
parser.add_argument("--shadow-root", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
contracts = {
    "market": "daily/tw/latest.json",
    "institutional": "quant/institutional_leaderboard.json",
    "margin": "daily/tw_market_margin/latest.json",
    "etf": "quant/etf/outputs/latest_snapshot.json",
    "fx": "meta/exchange_rate_history.json",
    "tdcc": "weekly/shareholders/YHD4.json",
    "revenue": "monthly/2330.json",
    "financial": "quarterly/2330.json",
    "calendar": "meta/calendar.json",
    "corporate_actions": f"meta/actions/{date.today().year}.json",
}
shadow_contracts = {
    "market": "daily/tw/latest.json",
    "institutional": "daily/institutional/latest.json",
    "margin": "daily/tw_market_margin/latest.json",
    "etf": "quant/etf/outputs/latest_snapshot.json",
    "fx": "meta/exchange_rate_history.json",
    "tdcc": "weekly/tdcc/latest.json",
    "revenue": "monthly/revenue/latest.json",
    "financial": "fundamentals/official_latest.json",
    "calendar": "meta/calendar.json",
    "corporate_actions": f"meta/actions/{date.today().year}.json",
}
report = {domain: compare(latest_output(args.old_root, contracts[domain]), latest_output(args.shadow_root, shadow_contracts[domain])) for domain in contracts}
report["institutional"] = institutional_boundary(latest_output(args.old_root, contracts["institutional"]), latest_output(args.shadow_root, shadow_contracts["institutional"]))
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v["status"] for k, v in report.items()}, ensure_ascii=False))
