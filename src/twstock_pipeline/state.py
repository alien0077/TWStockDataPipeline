from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

DOMAINS = ("market", "institutional", "margin", "financial", "revenue", "tdcc", "etf", "fx")


def load_state(path: Path) -> dict:
    if not path.exists():
        return {domain: {"last_success": None, "last_attempt": None, "status": "never"} for domain in DOMAINS}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = handle.name
    os.replace(temporary, path)


def mark_success(state: dict, domain: str, completed_date: str) -> None:
    """Advance only after the caller completed download, validation and output."""
    details = state.setdefault(domain, {})
    details["last_success"] = completed_date
    details["last_attempt"] = completed_date
    details["status"] = "healthy"
    details.pop("pending_dates", None)
