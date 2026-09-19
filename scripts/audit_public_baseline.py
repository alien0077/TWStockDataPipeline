#!/usr/bin/env python3
"""Read-only Public_Data baseline contract audit."""
from __future__ import annotations
import argparse
import json
from twstock_pipeline.github_api import GitHubGitDataAPI

CONTRACT = {
    "market": "data/daily/tw/",
    "margin": "data/daily/tw_market_margin/",
    "tdcc": "data/weekly/shareholders/",
    "revenue": "data/monthly/",
    "financial": "data/quarterly/",
    "etf": "data/quant/etf/outputs/latest_snapshot.json",
    "fx": "data/meta/exchange_rate_history.json",
    "calendar": "data/meta/calendar.json",
    "corporate_actions": "data/meta/actions/",
}


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--sha", required=True)
    p.add_argument("--repo", default="alien0077/Public_Data")
    args=p.parse_args()
    api=GitHubGitDataAPI()
    commit=api.get_commit(args.repo,args.sha)
    tree=api.get_tree(args.repo,commit["tree"],recursive=True)
    if tree.get("truncated"):
        raise SystemExit("baseline tree truncated")
    paths=[str(x.get("path")) for x in tree.get("tree",[]) if x.get("type")=="blob"]
    counts={}
    for domain,prefix in CONTRACT.items():
        if prefix.endswith(".json"):
            counts[domain]=int(prefix in paths)
        else:
            counts[domain]=sum(1 for x in paths if x.startswith(prefix) and x.endswith(".json"))
    result={"baseline_sha":args.sha,"tree_sha":commit["tree"],"truncated":False,"counts":counts}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
