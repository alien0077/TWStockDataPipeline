from __future__ import annotations

import hashlib
from dataclasses import dataclass


class PublishError(RuntimeError):
    pass


@dataclass
class GitDataPublisher:
    api: object
    repo: str
    token: str | None = None
    dry_run: bool = True
    chunk_size: int = 1000

    def publish(self, expected_head: str, changes: dict[str, bytes]) -> dict:
        if not self.dry_run and not self.token:
            raise PublishError("PUBLIC_DATA_TOKEN is required for production publish")
        head = self.api.get_ref(self.repo)
        if head != expected_head:
            raise PublishError("Public_Data HEAD changed; regenerate baseline")
        commit = self.api.get_commit(self.repo, expected_head)
        base_tree = commit["tree"]
        if self.dry_run:
            return {"dry_run": True, "expected_head": expected_head, "base_tree": base_tree, "paths": sorted(changes)}
        blob_shas = {path: self.api.create_blob(self.repo, data) for path, data in sorted(changes.items())}
        tree = base_tree
        for start in range(0, len(blob_shas), self.chunk_size):
            entries = [{"path": p, "mode": "100644", "type": "blob", "sha": s} for p, s in list(blob_shas.items())[start:start + self.chunk_size]]
            tree = self.api.create_tree(self.repo, tree, entries)
        new_commit = self.api.create_commit(self.repo, tree, [expected_head])
        if self.api.get_ref(self.repo) != expected_head:
            raise PublishError("Public_Data HEAD changed before ref update")
        self.api.update_ref(self.repo, new_commit, force=False)
        return {"dry_run": False, "commit": new_commit, "tree": tree, "paths": sorted(changes)}
