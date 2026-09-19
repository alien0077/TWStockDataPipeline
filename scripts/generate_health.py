#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from twstock_pipeline.health import build_health
from twstock_pipeline.state import load_state

parser = argparse.ArgumentParser()
parser.add_argument("--data-root", type=Path, default=Path("data"))
parser.add_argument("--state", type=Path, default=Path("state/pipeline_state.json"))
parser.add_argument("--output", type=Path, default=Path("data/data_health.json"))
args = parser.parse_args()
state = load_state(args.state)
latest = max((v.get("last_success") for v in state.values() if v.get("last_success")), default=date.today().isoformat())
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(build_health(state, date.fromisoformat(latest), args.data_root), ensure_ascii=False, indent=2) + "\n")
