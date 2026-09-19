from __future__ import annotations

from datetime import date, timedelta


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
