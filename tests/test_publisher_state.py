import hashlib
import json

import pytest

from twstock_pipeline.publisher_state import merge_bytes, prepare_publish_state


def encoded(rows, key="data"):
    return (json.dumps({key: rows}, ensure_ascii=False, indent=2) + "\n").encode()


def test_history_preserves_baseline_periods():
    baseline = encoded([{"period": "2026-02", "v": 2}, {"period": "2026-01", "v": 1}])
    candidate = encoded([{"period": "2026-03", "v": 3}])
    state = prepare_publish_state(
        baseline_sha="head",
        baseline_files={"data/monthly/2330.json": baseline},
        candidate_files={"data/monthly/2330.json": candidate},
        domain_by_path={"data/monthly/2330.json": "revenue"},
        compatibility_pass=True,
    )
    rows = json.loads(state.final_files["data/monthly/2330.json"])["data"]
    assert {row["period"] for row in rows} == {"2026-01", "2026-02", "2026-03"}
    assert state.safety.history_files_checked == 1
    assert state.safety.history_failures == 0
    assert state.safety.data_loss_count == 0


def test_same_period_null_preserves_non_null_baseline():
    baseline = encoded([{"period": "2026-02", "legacy": "keep"}])
    candidate = encoded([{"period": "2026-02", "legacy": None}])
    final = merge_bytes(baseline, candidate, "financial")
    assert json.loads(final)["data"][0]["legacy"] == "keep"


def test_malformed_historical_baseline_fails_closed():
    with pytest.raises((ValueError, json.JSONDecodeError)):
        merge_bytes(b"{}", encoded([{"period": "2026-03"}]), "revenue")


def test_non_history_candidate_bytes_are_not_reserialized():
    candidate = b'{ "x" : 1 }\n'
    state = prepare_publish_state(
        baseline_sha="head",
        baseline_files={},
        candidate_files={"data/meta.json": candidate},
        domain_by_path={"data/meta.json": "fx"},
        compatibility_pass=True,
    )
    assert state.final_files["data/meta.json"] is candidate
    assert state.changes["data/meta.json"] is state.final_files["data/meta.json"]


def test_unchanged_path_is_not_transport_change():
    payload = b'{"x":1}\n'
    state = prepare_publish_state(
        baseline_sha="head",
        baseline_files={"data/a.json": payload},
        candidate_files={"data/a.json": payload},
        domain_by_path={"data/a.json": "fx"},
        compatibility_pass=True,
    )
    assert state.publish_plan["data/a.json"] == "UNCHANGED"
    assert "data/a.json" not in state.changes


def test_exact_audited_bytes_are_transport_bytes():
    baseline = encoded([{"period": "2026-01", "v": 1}])
    candidate = encoded([{"period": "2026-02", "v": 2}])
    state = prepare_publish_state(
        baseline_sha="head",
        baseline_files={"data/q.json": baseline},
        candidate_files={"data/q.json": candidate},
        domain_by_path={"data/q.json": "financial"},
        compatibility_pass=True,
    )
    path = "data/q.json"
    assert state.changes[path] is state.final_files[path]
    assert hashlib.sha256(state.changes[path]).digest() == hashlib.sha256(state.final_files[path]).digest()


def test_publish_plan_never_emits_deletion_for_untouched_baseline_paths():
    state = prepare_publish_state(
        baseline_sha="head",
        baseline_files={"data/untouched.json": b'{"legacy":true}\n'},
        candidate_files={"data/new.json": b'{"new":true}\n'},
        domain_by_path={"data/new.json": "fx"},
        compatibility_pass=True,
    )
    assert state.safety.delete_count == 0
    assert "data/untouched.json" not in state.publish_plan
    assert "data/untouched.json" not in state.changes
