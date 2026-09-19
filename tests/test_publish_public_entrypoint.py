import json
import sys

import pytest

import scripts.publish_public as publish_public


class FakeAPI:
    instances = []
    head = "baseline"
    race = False

    def __init__(self, token=None):
        self.token = token
        self.blobs = []
        self.ref_updates = []
        self.ref_reads = 0
        FakeAPI.instances.append(self)

    def get_ref(self, repo):
        self.ref_reads += 1
        if self.race and self.ref_reads > 1:
            return "raced"
        return self.head

    def get_commit(self, repo, sha):
        return {"tree": "base-tree"}

    def create_blob(self, repo, data):
        self.blobs.append(data)
        return f"blob-{len(self.blobs)}"

    def create_tree(self, repo, base_tree, entries):
        assert base_tree == "base-tree"
        return "new-tree"

    def create_commit(self, repo, tree, parents):
        assert parents == ["baseline"]
        return "new-commit"

    def update_ref(self, repo, sha, force=False):
        self.ref_updates.append((sha, force))


def fixture_args(tmp_path, monkeypatch, publish=False):
    shadow = tmp_path / "shadow"
    baseline = tmp_path / "baseline"
    report = tmp_path / "report.json"
    checkpoint = tmp_path / "checkpoint.json"
    (shadow / "meta").mkdir(parents=True)
    (baseline / "data" / "meta").mkdir(parents=True)
    candidate = b'{ "version" : 2 }\n'
    (shadow / "meta" / "exchange_rate_history.json").write_bytes(candidate)
    (baseline / "data" / "meta" / "exchange_rate_history.json").write_bytes(b'{"version":1}\n')
    report.write_text(json.dumps({"fx": {"status": "PASS"}}))
    argv = [
        "publish_public.py",
        "--shadow-root", str(shadow),
        "--baseline-root", str(baseline),
        "--baseline-sha", "baseline",
        "--report", str(report),
        "--checkpoint", str(checkpoint),
    ]
    if publish:
        argv.append("--publish")
    monkeypatch.setattr(sys, "argv", argv)
    return checkpoint, candidate


def test_entrypoint_default_is_dry_run_and_no_remote_api(tmp_path, monkeypatch):
    checkpoint, _ = fixture_args(tmp_path, monkeypatch)
    FakeAPI.instances.clear()
    monkeypatch.setattr(publish_public, "GitHubGitDataAPI", FakeAPI)
    assert publish_public.main() == 0
    assert not FakeAPI.instances
    assert json.loads(checkpoint.read_text())["status"] == "dry_run"


def test_entrypoint_publish_missing_token_has_zero_remote_calls(tmp_path, monkeypatch):
    fixture_args(tmp_path, monkeypatch, publish=True)
    FakeAPI.instances.clear()
    monkeypatch.delenv("PUBLIC_DATA_TOKEN", raising=False)
    monkeypatch.setattr(publish_public, "GitHubGitDataAPI", FakeAPI)
    with pytest.raises(SystemExit, match="PUBLIC_DATA_TOKEN"):
        publish_public.main()
    assert not FakeAPI.instances


def test_entrypoint_transports_exact_candidate_bytes(tmp_path, monkeypatch):
    checkpoint, candidate = fixture_args(tmp_path, monkeypatch, publish=True)
    FakeAPI.instances.clear()
    monkeypatch.setenv("PUBLIC_DATA_TOKEN", "test-token")
    monkeypatch.setattr(publish_public, "GitHubGitDataAPI", FakeAPI)
    assert publish_public.main() == 0
    api = FakeAPI.instances[-1]
    assert api.blobs == [candidate]
    assert api.ref_updates == [("new-commit", False)]
    assert json.loads(checkpoint.read_text())["status"] == "published"


def test_entrypoint_stale_baseline_performs_zero_writes(tmp_path, monkeypatch):
    fixture_args(tmp_path, monkeypatch, publish=True)
    FakeAPI.instances.clear()
    monkeypatch.setenv("PUBLIC_DATA_TOKEN", "test-token")
    monkeypatch.setattr(publish_public, "GitHubGitDataAPI", FakeAPI)
    FakeAPI.head = "different"
    try:
        with pytest.raises(Exception, match="HEAD changed"):
            publish_public.main()
        api = FakeAPI.instances[-1]
        assert api.blobs == []
        assert api.ref_updates == []
    finally:
        FakeAPI.head = "baseline"


def test_entrypoint_head_race_never_updates_ref(tmp_path, monkeypatch):
    fixture_args(tmp_path, monkeypatch, publish=True)
    FakeAPI.instances.clear()
    monkeypatch.setenv("PUBLIC_DATA_TOKEN", "test-token")
    monkeypatch.setattr(publish_public, "GitHubGitDataAPI", FakeAPI)
    FakeAPI.race = True
    try:
        with pytest.raises(Exception, match="HEAD changed before ref update"):
            publish_public.main()
        api = FakeAPI.instances[-1]
        assert api.blobs
        assert api.ref_updates == []
    finally:
        FakeAPI.race = False
