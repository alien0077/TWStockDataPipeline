from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path


def trading_dates(start: date, end: date, holidays: set[date] | None = None) -> list[date]:
    """Return weekdays excluding the project's explicit Taiwan holiday set.

    The holiday set is an input from the official market-calendar sync; it is
    never inferred from weekday alone when a calendar is available.
    """
    holidays = holidays or set()
    result: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5 and cursor not in holidays:
            result.append(cursor)
        cursor += timedelta(days=1)
    return result


def latest_expected_trading_date(today: date, data_root: Path) -> date:
    holidays: set[date] = set()
    path = data_root / "meta" / "calendar.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        holidays.update(date.fromisoformat(x) for x in payload.get("holidays", []) if isinstance(x, str))
        for year in payload.get("meta", {}).get("years", {}).values():
            if isinstance(year, dict):
                holidays.update(date.fromisoformat(x) for x in year.get("tw", []) if isinstance(x, str))
    cursor = today
    while cursor.weekday() >= 5 or cursor in holidays:
        cursor -= timedelta(days=1)
    return cursor
