from __future__ import annotations

import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

HISTORY_DOMAINS = {"tdcc", "revenue", "financial"}


@dataclass(frozen=True)
class PublishSafetyResult:
    compatibility_pass: bool
    history_files_checked: int
    history_failures: int
    data_loss_count: int
    delete_count: int


@dataclass(frozen=True)
class PublishPreparedState:
    baseline_sha: str
    baseline_files: Mapping[str, bytes]
    candidate_files: Mapping[str, bytes]
    final_files: Mapping[str, bytes]
    publish_plan: Mapping[str, str]
    changes: Mapping[str, bytes]
    safety: PublishSafetyResult


def _period(row: dict) -> str:
    return str(row.get("date") or row.get("period") or row.get("week") or "")


def _history_rows(payload: object, domain: str) -> tuple[str, list[dict]]:
    if not isinstance(payload, dict):
        raise ValueError(f"malformed {domain} history: expected object")
    key = "recent" if domain == "tdcc" else "data"
    rows = payload.get(key)
    if not isinstance(rows, list):
        raise ValueError(f"malformed {domain} history: expected {key} list")
    return key, [row for row in rows if isinstance(row, dict)]


def merge_bytes(baseline: bytes | None, candidate: bytes, domain: str) -> bytes:
    """Return the exact publish bytes; historical domains preserve baseline periods."""
    if domain not in HISTORY_DOMAINS or baseline is None:
        return candidate

    old = json.loads(baseline.decode("utf-8"))
    new = json.loads(candidate.decode("utf-8"))
    old_key, old_rows = _history_rows(old, domain)
    new_key, new_rows = _history_rows(new, domain)
    if old_key != new_key:
        raise ValueError(f"history key mismatch for {domain}")

    merged = {_period(row): row for row in old_rows if _period(row)}
    for row in new_rows:
        period = _period(row)
        if not period:
            continue
        prior = merged.get(period, {})
        combined = {**prior, **row}
        merged[period] = {
            field: (value if value is not None else prior.get(field))
            for field, value in combined.items()
        }

    new[new_key] = sorted(merged.values(), key=_period, reverse=True)
    return (json.dumps(new, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _periods(data: bytes, domain: str) -> set[str]:
    payload = json.loads(data.decode("utf-8"))
    _, rows = _history_rows(payload, domain)
    return {_period(row) for row in rows if _period(row)}


def prepare_publish_state(
    *,
    baseline_sha: str,
    baseline_files: Mapping[str, bytes],
    candidate_files: Mapping[str, bytes],
    domain_by_path: Mapping[str, str],
    compatibility_pass: bool,
) -> PublishPreparedState:
    """Build and audit one immutable write-set. No remote mutation occurs here."""
    if not baseline_sha:
        raise ValueError("baseline_sha is required")

    baseline = dict(baseline_files)
    candidates = dict(candidate_files)
    finals: dict[str, bytes] = {}
    plan: dict[str, str] = {}
    changes: dict[str, bytes] = {}
    history_files_checked = 0
    history_failures = 0
    data_loss_count = 0

    for path in sorted(candidates):
        candidate = candidates[path]
        domain = domain_by_path.get(path, "")
        final = merge_bytes(baseline.get(path), candidate, domain)
        finals[path] = final

        if path not in baseline:
            plan[path] = "ADD"
        elif final == baseline[path]:
            plan[path] = "UNCHANGED"
        else:
            plan[path] = "MODIFY"

        if plan[path] in {"ADD", "MODIFY"}:
            changes[path] = final

        if domain in HISTORY_DOMAINS and path in baseline:
            history_files_checked += 1
            before = _periods(baseline[path], domain)
            after = _periods(final, domain)
            lost = before - after
            if lost:
                history_failures += 1
                data_loss_count += len(lost)

    # The write-set is additive/update-only. Untouched repository paths remain
    # in Git through base_tree and are not represented as deletion entries.
    delete_count = sum(1 for action in plan.values() if action == "DELETE")

    safety = PublishSafetyResult(
        compatibility_pass=bool(compatibility_pass),
        history_files_checked=history_files_checked,
        history_failures=history_failures,
        data_loss_count=data_loss_count,
        delete_count=delete_count,
    )
    return PublishPreparedState(
        baseline_sha=baseline_sha,
        baseline_files=MappingProxyType(baseline),
        candidate_files=MappingProxyType(candidates),
        final_files=MappingProxyType(finals),
        publish_plan=MappingProxyType(plan),
        changes=MappingProxyType(changes),
        safety=safety,
    )


def gates_from_state(state: PublishPreparedState) -> dict[str, object]:
    return {
        "compatibility_pass": state.safety.compatibility_pass,
        "history_failures": state.safety.history_failures,
        "data_loss_count": state.safety.data_loss_count,
        "delete_count": state.safety.delete_count,
    }
