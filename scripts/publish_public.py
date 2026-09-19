#!/usr/bin/env python3
"""Fail-closed Public_Data publisher preparation entry point.

The default mode is a local dry-run. Production transport is deliberately
unavailable until the read-only GitHub baseline/API adapter is wired.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

from twstock_pipeline.publisher_state import gates_from_state, prepare_publish_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shadow-root", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--baseline-sha", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--repo", default="alien0077/Public_Data")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--publish", action="store_true")
    return parser.parse_args()


def _load_report(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("compatibility report must be an object")
    return payload


def _read_required(path: Path) -> bytes:
    data = path.read_bytes()
    if not data:
        raise ValueError(f"empty publish candidate: {path}")
    return data


def main() -> int:
    args = parse_args()
    report = _load_report(args.report)
    allowed = {
        "etf": "quant/etf/outputs/latest_snapshot.json",
        "fx": "meta/exchange_rate_history.json",
        "calendar": "meta/calendar.json",
        "corporate_actions": f"meta/actions/{date.today().year}.json",
    }
    publishable = [domain for domain in allowed if report.get(domain, {}).get("status") == "PASS"]
    if not publishable:
        raise SystemExit("compatibility gate: no PASS domain is publishable")

    candidate_files: dict[str, bytes] = {}
    baseline_files: dict[str, bytes] = {}
    domain_by_path: dict[str, str] = {}
    for domain in publishable:
        relative = allowed[domain]
        publish_path = str(Path("data") / relative)
        candidate_files[publish_path] = _read_required(args.shadow_root / relative)
        baseline_path = args.baseline_root / publish_path
        if baseline_path.exists():
            baseline_files[publish_path] = _read_required(baseline_path)
        domain_by_path[publish_path] = domain

    compatibility_pass = all(report.get(domain, {}).get("status") == "PASS" for domain in publishable)
    state = prepare_publish_state(
        baseline_sha=args.baseline_sha,
        baseline_files=baseline_files,
        candidate_files=candidate_files,
        domain_by_path=domain_by_path,
        compatibility_pass=compatibility_pass,
    )

    result = {
        "status": "dry_run",
        "baseline_sha": state.baseline_sha,
        "publishable_domains": publishable,
        "plan": dict(state.publish_plan),
        "gates": gates_from_state(state),
        "changed_paths": sorted(state.changes),
    }

    if args.publish:
        # Keep production fail-closed until the read-only GitHub baseline/API
        # adapter is implemented and covered by entry-point safety tests.
        if not os.environ.get("PUBLIC_DATA_TOKEN"):
            raise SystemExit("PUBLIC_DATA_TOKEN is required for production publish")
        raise SystemExit("production Git Data API adapter is not wired; refusing remote mutation")

    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    args.checkpoint.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
