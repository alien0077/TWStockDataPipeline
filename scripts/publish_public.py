#!/usr/bin/env python3
"""Disabled-by-default, compatibility-gated Public_Data publisher."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--shadow-root", type=Path, required=True)
parser.add_argument("--report", type=Path, required=True)
parser.add_argument("--repo", default="alien0077/Public_Data")
parser.add_argument("--checkpoint", type=Path, required=True)
args = parser.parse_args()

report = json.loads(args.report.read_text(encoding="utf-8"))
allowed = {"etf": "quant/etf/outputs/latest_snapshot.json", "fx": "meta/exchange_rate_history.json", "calendar": "meta/calendar.json", "corporate_actions": f"meta/actions/{__import__('datetime').date.today().year}.json"}
publishable = [domain for domain in allowed if report.get(domain, {}).get("status") == "PASS"]
if not publishable:
    raise SystemExit("compatibility gate: no PASS domain is publishable")
token = os.environ.get("PUBLIC_DATA_TOKEN")
if not token:
    raise SystemExit("PUBLIC_DATA_TOKEN is required; publisher is intentionally disabled without it")

with tempfile.TemporaryDirectory(prefix="twstock-public-publish-") as work:
    repo = Path(work) / "Public_Data"
    url = f"https://x-access-token:{token}@github.com/{args.repo}.git"
    subprocess.run(["git", "clone", "--depth", "1", url, str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "pull", "--rebase", "origin", "main"], check=True)
    copied = []
    for domain in publishable:
        relative = Path(allowed[domain])
        source = args.shadow_root / relative
        if not source.exists() or source.stat().st_size == 0:
            raise SystemExit(f"publish validation failed: {source}")
        target = repo / "data" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(str(Path("data") / relative))
    subprocess.run(["git", "-C", str(repo), "add", *copied], check=True)
    if subprocess.run(["git", "-C", str(repo), "diff", "--cached", "--quiet"]).returncode == 0:
        raise SystemExit("no validated changes to publish")
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "data: publish validated public domains"], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "origin", "main"], check=True)
args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
args.checkpoint.write_text(json.dumps({"status": "published", "domains": publishable}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"status": "published", "domains": publishable}))
