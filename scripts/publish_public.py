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
from twstock_pipeline.git_data_publish import GitDataPublisher, validate_publish_gates
from twstock_pipeline.github_api import GitHubGitDataAPI


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
    mapping = {
        "market": "daily/tw",
        "institutional": "daily/institutional",
        "margin": "daily/tw_market_margin",
        "tdcc": "weekly/shareholders",
        "revenue": "monthly",
        "financial": "quarterly",
        "etf": "quant/etf/outputs/latest_snapshot.json",
        "fx": "meta/exchange_rate_history.json",
        "calendar": "meta/calendar.json",
        "corporate_actions": "meta/actions",
    }
    publishable = [domain for domain in mapping if report.get(domain, {}).get("status") == "PASS"]
    if not publishable:
        raise SystemExit("compatibility gate: no PASS domain is publishable")

    candidate_files: dict[str, bytes] = {}
    baseline_files: dict[str, bytes] = {}
    domain_by_path: dict[str, str] = {}

    def selected_files(root: Path, relative: str) -> list[Path]:
        target = root / relative
        if target.is_file():
            return [target]
        if target.is_dir():
            return sorted(target.rglob("*.json"))
        return []

    for domain in publishable:
        relative = mapping[domain]
        sources = selected_files(args.shadow_root, relative)
        if not sources:
            raise SystemExit(f"publish validation failed: no candidate files for {domain}: {relative}")
        for source in sources:
            rel = source.relative_to(args.shadow_root).as_posix()
            publish_path = f"data/{rel}"
            candidate_files[publish_path] = _read_required(source)
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

    gates = gates_from_state(state)
    validate_publish_gates(gates)

    if args.publish:
        token = os.environ.get("PUBLIC_DATA_TOKEN")
        if not token:
            raise SystemExit("PUBLIC_DATA_TOKEN is required for production publish")
        api = GitHubGitDataAPI(token=token)
        publisher = GitDataPublisher(api=api, repo=args.repo, token=token, dry_run=False)
        transport = publisher.publish(
            expected_head=state.baseline_sha,
            changes=dict(state.changes),
            gates=gates,
        )
        result["status"] = "published"
        result["transport"] = transport

    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    args.checkpoint.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
