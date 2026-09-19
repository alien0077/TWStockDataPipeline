from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path


def build_health(state: dict, expected_date: date, data_root: Path | None = None) -> dict:
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "domains": {}}
    for domain, details in state.items():
        latest = details.get("last_success")
        output_exists = None
        if data_root is not None:
            candidates = list(data_root.glob(f"**/{latest}.json")) if latest else []
            output_exists = bool(candidates)
        result["domains"][domain] = {
            "latest_date": latest,
            "expected_date": expected_date.isoformat(),
            "stale": latest != expected_date.isoformat() if latest else True,
            "status": details.get("status", "unknown") if output_exists is not False else "missing_output",
            "output_exists": output_exists,
        }
    return result
