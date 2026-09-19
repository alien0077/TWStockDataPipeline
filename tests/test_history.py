import json
from pathlib import Path

import pytest

from twstock_pipeline.history import merge_history


def test_merge_history_appends_and_replaces(tmp_path: Path):
    path = tmp_path / "2330.json"
    path.write_text(json.dumps({"data": [{"period": "2026-07", "value": 1}]}))
    result = merge_history(path, [{"period": "2026-08", "value": 2}, {"period": "2026-07", "value": 3}], lambda x: x["period"], lambda x: x["period"])
    assert result["data"] == [{"period": "2026-08", "value": 2}, {"period": "2026-07", "value": 3}]


def test_merge_history_empty_input_preserves_history(tmp_path: Path):
    path = tmp_path / "2330.json"
    path.write_text(json.dumps({"data": [{"period": "2026-07"}]}))
    assert merge_history(path, [], lambda x: x["period"], lambda x: x["period"])["data"] == [{"period": "2026-07"}]


def test_merge_history_rejects_malformed_existing(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{}")
    with pytest.raises(ValueError):
        merge_history(path, [], lambda x: x.get("period", ""), lambda x: x.get("period", ""))
