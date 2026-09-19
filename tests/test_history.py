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


@pytest.mark.parametrize("domain,key", [("TDCC", "date"), ("revenue", "period"), ("financial", "period")])
def test_historical_domains_preserve_periods_and_non_null_values(tmp_path: Path, domain: str, key: str):
    path = tmp_path / f"{domain}.json"
    path.write_text(json.dumps({"data": [{key: "C", "legacy_field": "keep"}, {key: "B"}, {key: "A"}]}))
    incoming = [{key: "D", "legacy_field": None}, {key: "C", "legacy_field": None}]
    result = merge_history(path, incoming, lambda x: x[key], lambda x: x[key])
    rows = {row[key]: row for row in result["data"]}
    assert set(rows) == {"A", "B", "C", "D"}
    assert rows["C"]["legacy_field"] == "keep"


def test_empty_candidate_does_not_rewrite_history(tmp_path: Path):
    path = tmp_path / "tdcc.json"
    path.write_text(json.dumps({"data": [{"date": "2026-W01"}]}))
    result = merge_history(path, [], lambda x: x["date"], lambda x: x["date"])
    assert result["data"] == [{"date": "2026-W01"}]
