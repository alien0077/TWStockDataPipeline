from __future__ import annotations

import base64
from dataclasses import dataclass

import requests


@dataclass
class GitHubGitDataAPI:
    """Minimal GitHub Git Data API adapter used by GitDataPublisher."""

    token: str | None = None
    timeout: int = 30

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, url: str, **kwargs):
        response = requests.request(method, url, headers=self._headers(), timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response.json()

    def _base(self, repo: str) -> str:
        return f"https://api.github.com/repos/{repo}"

    def get_ref(self, repo: str) -> str:
        data = self._request("GET", f"{self._base(repo)}/git/ref/heads/main")
        return str(data["object"]["sha"])

    def get_commit(self, repo: str, sha: str) -> dict:
        data = self._request("GET", f"{self._base(repo)}/git/commits/{sha}")
        return {"tree": data["tree"]["sha"]}

    def create_blob(self, repo: str, data: bytes) -> str:
        payload = {"content": base64.b64encode(data).decode("ascii"), "encoding": "base64"}
        return str(self._request("POST", f"{self._base(repo)}/git/blobs", json=payload)["sha"])

    def create_tree(self, repo: str, base_tree: str, entries: list[dict]) -> str:
        payload = {"base_tree": base_tree, "tree": entries}
        return str(self._request("POST", f"{self._base(repo)}/git/trees", json=payload)["sha"])

    def create_commit(self, repo: str, tree: str, parents: list[str]) -> str:
        payload = {"message": "data: publish validated public domains", "tree": tree, "parents": parents}
        return str(self._request("POST", f"{self._base(repo)}/git/commits", json=payload)["sha"])

    def update_ref(self, repo: str, sha: str, force: bool = False) -> None:
        self._request("PATCH", f"{self._base(repo)}/git/refs/heads/main", json={"sha": sha, "force": force})
