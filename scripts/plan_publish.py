#!/usr/bin/env python3
"""Plan the exact Public_Data tree changes without committing or pushing."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--old-root", type=Path, required=True, help="Public_Data/data")
parser.add_argument("--shadow-root", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()

mapping = {
    "market": ("daily/tw", "daily/tw"),
    "margin": ("daily/tw_market_margin", "daily/tw_market_margin"),
    "tdcc": ("weekly/shareholders", "weekly/shareholders"),
    "revenue": ("monthly", "monthly"),
    "financial": ("quarterly", "quarterly"),
    "etf": ("quant/etf/outputs/latest_snapshot.json", "quant/etf/outputs/latest_snapshot.json"),
    "fx": ("meta/exchange_rate_history.json", "meta/exchange_rate_history.json"),
    "calendar": ("meta/calendar.json", "meta/calendar.json"),
    "corporate_actions": ("meta/actions", "meta/actions"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root: Path, rel: str) -> list[Path]:
    path = root / rel
    if path.is_file():
        return [path]
    return sorted(path.rglob("*.json")) if path.exists() else []


def merged_bytes(old: Path, new: Path, domain: str) -> bytes:
    """Apply the production historical merge semantics in-memory."""
    if domain not in {"TDCC", "revenue", "financial"} or not old.exists():
        return new.read_bytes()
    left, right = json.loads(old.read_text()), json.loads(new.read_text())
    key = "recent" if domain == "TDCC" else "data"
    old_rows, new_rows = left.get(key, []), right.get(key, [])
    def period(row):
        return str(row.get("date") or row.get("period") or row.get("week") or "")
    merged = {period(row): row for row in old_rows if period(row)}
    for row in new_rows:
        p = period(row)
        if not p:
            continue
        prior = merged.get(p, {})
        merged[p] = {k: (v if v is not None else prior.get(k)) for k, v in {**prior, **row}.items()}
    rows = sorted(merged.values(), key=period, reverse=True)
    right[key] = rows
    return (json.dumps(right, ensure_ascii=False, indent=2) + "\n").encode()


added, modified, deleted, unchanged = [], [], [], []
by_domain = {}
for domain, (old_rel, shadow_rel) in mapping.items():
    old_files = {p.relative_to(args.old_root).as_posix(): p for p in files(args.old_root, old_rel)}
    shadow_files = {p.relative_to(args.shadow_root).as_posix(): p for p in files(args.shadow_root, shadow_rel)}
    domain_result = {"added": [], "modified": [], "deleted": [], "unchanged": []}
    for rel in sorted(set(old_files) | set(shadow_files)):
        old, shadow = old_files.get(rel), shadow_files.get(rel)
        if old is None:
            added.append(rel); domain_result["added"].append(rel)
        elif shadow is None:
            deleted.append(rel); domain_result["deleted"].append(rel)
        elif hashlib.sha256(merged_bytes(old, shadow, domain).strip()).hexdigest() == digest(old):
            unchanged.append(rel); domain_result["unchanged"].append(rel)
        else:
            modified.append(rel); domain_result["modified"].append(rel)
    by_domain[domain] = domain_result

plan = {"files_added": added, "files_modified": modified, "files_deleted": deleted, "files_unchanged": unchanged, "by_domain": by_domain}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: len(plan[k]) for k in ("files_added", "files_modified", "files_deleted", "files_unchanged")}))
