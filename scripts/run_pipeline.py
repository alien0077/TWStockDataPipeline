#!/usr/bin/env python3
"""Actions-free end-to-end public data pipeline.

Collection happens in a temporary shadow tree. The audited Public_Data baseline
is materialized read-only only for the exact compatibility contracts, then the
same pinned SHA is passed to the publisher. Publishing is explicit opt-in.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
DOMAINS = (
    "calendar", "market", "institutional", "margin", "tdcc",
    "revenue", "financial", "etf", "fx", "corporate_actions",
)
CONTRACTS = {
    "market": "data/daily/tw/latest.json",
    "margin": "data/daily/tw_market_margin/latest.json",
    "etf": "data/quant/etf/outputs/latest_snapshot.json",
    "fx": "data/meta/exchange_rate_history.json",
    "tdcc": "data/weekly/shareholders/YHD4.json",
    "revenue": "data/monthly/2330.json",
    "financial": "data/quarterly/2330.json",
    "calendar": "data/meta/calendar.json",
}
# Institutional leaderboard is deliberately private and is not read from or
# written to Public_Data. compare_public_data.py applies the explicit boundary.
PRIVATE_PLACEHOLDER = "data/quant/institutional_leaderboard.json"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def materialize_contract_baseline(repo: str, sha: str, root: Path) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from twstock_pipeline.github_api import GitHubGitDataAPI

    paths = list(CONTRACTS.values())
    target_year = (date.today() if not hasattr(materialize_contract_baseline, "_target_date") else materialize_contract_baseline._target_date).year\n    paths.append(f"data/meta/actions/{target_year}.json")
    api = GitHubGitDataAPI(token=os.environ.get("GITHUB_TOKEN"))
    files = api.load_files_at_commit(repo, sha, sorted(paths))
    for path, payload in files.items():
        target = root / path.removeprefix("data/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", type=date.fromisoformat)
    p.add_argument("--baseline-sha", required=True)
    p.add_argument("--repo", default="alien0077/Public_Data")
    p.add_argument("--checkpoint", type=Path, default=Path("artifacts/publish_checkpoint.json"))
    p.add_argument("--report", type=Path, default=Path("artifacts/compatibility_report.json"))
    p.add_argument("--health", type=Path, default=Path("artifacts/shadow_health.json"))
    p.add_argument("--publish", action="store_true")
    args = p.parse_args()

    with tempfile.TemporaryDirectory(prefix="twstock-e2e-") as tmp:
        work = Path(tmp)
        shadow = work / "shadow"
        baseline = work / "baseline"
        for domain in DOMAINS:
            cmd = [PYTHON, "scripts/sync_public.py", domain, "--data-root", str(shadow)]
            if args.date and domain in {"market", "institutional", "margin"}:
                cmd += ["--date", args.date.isoformat()]
            run(cmd)

        run([PYTHON, "scripts/build_shadow_health.py",
             "--data-root", str(shadow), "--output", str(args.health)])

        materialize_contract_baseline._target_date = args.date or date.today()\n        materialize_contract_baseline(args.repo, args.baseline_sha, baseline)
        # Placeholder path may remain absent: institutional_boundary() explicitly
        # marks this private-derived legacy contract NOT_APPLICABLE_PRIVATE.
        run([PYTHON, "scripts/compare_public_data.py",
             "--old-root", str(baseline), "--shadow-root", str(shadow),
             "--output", str(args.report)])

        cmd = [
            PYTHON, "scripts/publish_public.py",
            "--shadow-root", str(shadow),
            "--baseline-sha", args.baseline_sha,
            "--report", str(args.report),
            "--checkpoint", str(args.checkpoint),
            "--repo", args.repo,
        ]
        if args.publish:
            cmd.append("--publish")
        run(cmd)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
