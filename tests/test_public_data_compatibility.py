import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
from twstock_pipeline.compat import validate_health_payload, validate_public_data_tree


def test_existing_public_index_contract_fixture():
    assert validate_public_data_tree(ROOT / "fixtures") == []


def test_health_contract_has_all_domains():
    payload = {"domains": {d: {"latest_date": None, "expected_date": "2026-09-17", "stale": True, "status": "missing"} for d in ("market", "institutional", "margin", "financial", "revenue", "tdcc", "etf", "fx")}}
    assert validate_health_payload(payload) == []
