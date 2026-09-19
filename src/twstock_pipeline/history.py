from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Callable, Iterable


def merge_history(path: Path, incoming: Iterable[dict], key: Callable[[dict], str], sort_key: Callable[[dict], str]) -> dict:
    """Fail-closed merge for legacy per-symbol JSON histories."""
    existing = []
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError(f"malformed legacy history: {path}")
        existing = [x for x in payload["data"] if isinstance(x, dict)]
    merged = {key(row): row for row in existing}
    for row in incoming:
        if isinstance(row, dict) and key(row):
            merged[key(row)] = row
    rows = sorted(merged.values(), key=sort_key, reverse=True)
    return {"data": rows}


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
