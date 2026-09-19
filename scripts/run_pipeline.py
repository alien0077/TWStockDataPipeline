#!/usr/bin/env python3
"""Run the public pipeline without GitHub Actions.

Designed for cron/systemd/Oracle VM. Collection and validation happen in a
temporary shadow tree. Publishing remains an explicit opt-in operation.
"""
from __future__ import annotations

import argparse
import json
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


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", type=date.fromisoformat)
    p.add_argument("--baseline-sha", required=True)
    p.add_argument("--report", type=Path, required=True,
                   help="compatibility report produced by validation")
    p.add_argument("--checkpoint", type=Path, default=Path("artifacts/publish_checkpoint.json"))
    p.add_argument("--publish", action="store_true")
    args = p.parse_args()

    with tempfile.TemporaryDirectory(prefix="twstock-shadow-") as tmp:
        shadow = Path(tmp)
        for domain in DOMAINS:
            cmd = [PYTHON, "scripts/sync_public.py", domain, "--data-root", str(shadow)]
            if args.date and domain in {"market", "institutional", "margin"}:
                cmd += ["--date", args.date.isoformat()]
            run(cmd)

        cmd = [
            PYTHON, "scripts/publish_public.py",
            "--shadow-root", str(shadow),
            "--baseline-sha", args.baseline_sha,
            "--report", str(args.report),
            "--checkpoint", str(args.checkpoint),
        ]
        if args.publish:
            cmd.append("--publish")
        run(cmd)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
