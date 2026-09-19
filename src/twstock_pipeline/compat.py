from __future__ import annotations

import json
from pathlib import Path


def validate_public_data_tree(data_root: Path) -> list[str]:
    errors: list[str] = []
    index = data_root / "index.json"
    if not index.exists():
        return ["missing data/index.json"]
    payload = json.loads(index.read_text(encoding="utf-8"))
    for key in ("version", "available_days_tw", "latest_daily_tw", "latest_daily_tw_market_margin"):
        if key not in payload:
            errors.append(f"index missing required key: {key}")
    return errors


def validate_health_payload(payload: dict) -> list[str]:
    errors = []
    for domain in ("market", "institutional", "margin", "financial", "revenue", "tdcc", "etf", "fx"):
        entry = payload.get("domains", {}).get(domain)
        if not isinstance(entry, dict):
            errors.append(f"health missing domain: {domain}")
            continue
        for key in ("latest_date", "expected_date", "stale", "status"):
            if key not in entry:
                errors.append(f"health {domain} missing key: {key}")
    return errors
