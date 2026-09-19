import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
from twstock_pipeline.calendar import trading_dates, latest_expected_trading_date
from twstock_pipeline.state import load_state, save_state


def test_calendar_excludes_holiday_and_weekend():
    assert trading_dates(date(2026, 9, 18), date(2026, 9, 21), {date(2026, 9, 18)}) == [date(2026, 9, 21)]


def test_state_is_atomic_and_restartable(tmp_path):
    path = tmp_path / "state.json"
    state = load_state(path)
    state["market"]["last_success"] = "2026-09-17"
    save_state(path, state)
    assert json.loads(path.read_text())["market"]["last_success"] == "2026-09-17"


def test_latest_expected_trading_date_weekend_and_holiday(tmp_path):
    (tmp_path / "meta").mkdir()
    (tmp_path / "meta/calendar.json").write_text('{"holidays":["2026-09-18"]}')
    assert latest_expected_trading_date(date(2026, 9, 19), tmp_path) == date(2026, 9, 17)
    assert latest_expected_trading_date(date(2026, 9, 20), tmp_path) == date(2026, 9, 17)
    assert latest_expected_trading_date(date(2026, 9, 17), tmp_path) == date(2026, 9, 17)
