import pytest
from twstock_pipeline.git_data_publish import GitDataPublisher, PublishError


class FakeAPI:
    def __init__(self, head="h"):
        self.head = head; self.calls = []; self.refs = []
    def get_ref(self, repo): self.calls.append(("get_ref", repo)); return self.head
    def get_commit(self, repo, sha): self.calls.append(("get_commit", sha)); return {"tree": "tree0"}
    def create_blob(self, repo, data): self.calls.append(("blob", data)); return "blob"
    def create_tree(self, repo, base, entries): self.calls.append(("tree", base, entries)); return base + "x"
    def create_commit(self, repo, tree, parents): self.calls.append(("commit", tree, parents)); return "commit"
    def update_ref(self, repo, sha, force): self.calls.append(("ref", sha, force))


def test_dry_run_never_writes_and_requires_base_tree():
    api = FakeAPI(); result = GitDataPublisher(api, "x/y").publish("h", {"data/a.json": b"{}"})
    assert result["dry_run"] and result["base_tree"] == "tree0"
    assert not any(c[0] in {"blob", "tree", "commit", "ref"} for c in api.calls)


def test_publish_uses_parent_base_tree_and_force_false():
    api = FakeAPI(); result = GitDataPublisher(api, "x/y", token="t", dry_run=False).publish("h", {"data/a.json": b"{}"})
    assert result["commit"] == "commit"
    assert ("tree", "tree0", [{"path": "data/a.json", "mode": "100644", "type": "blob", "sha": "blob"}]) in api.calls
    assert ("commit", "tree0x", ["h"]) in api.calls
    assert ("ref", "commit", False) in api.calls


def test_head_race_aborts_before_ref_update():
    api = FakeAPI(); api.refs = ["h", "other"]
    original = api.get_ref
    def raced(repo):
        api.calls.append(("get_ref", repo)); return "h" if len([c for c in api.calls if c[0] == "get_ref"]) == 1 else "other"
    api.get_ref = raced
    with pytest.raises(PublishError): GitDataPublisher(api, "x/y", token="t", dry_run=False).publish("h", {"x": b"1"})
    assert not any(c[0] == "ref" for c in api.calls)


def test_missing_token_fails_without_write():
    api = FakeAPI()
    with pytest.raises(PublishError): GitDataPublisher(api, "x/y", dry_run=False).publish("h", {"x": b"1"})
    assert api.calls == []


def test_chunking_chains_tree_base():
    api = FakeAPI(); result = GitDataPublisher(api, "x/y", token="t", dry_run=False, chunk_size=1).publish("h", {"a": b"1", "b": b"2"})
    trees = [c for c in api.calls if c[0] == "tree"]
    assert trees[0][1] == "tree0" and trees[1][1] == "tree0x"
