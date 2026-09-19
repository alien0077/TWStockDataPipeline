#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from twstock_pipeline import collectors
from twstock_pipeline.calendar import latest_expected_trading_date

parser = argparse.ArgumentParser()
parser.add_argument("domain", choices=("market", "institutional", "margin", "calendar", "tdcc", "financial", "revenue", "etf", "fx", "corporate_actions"))
parser.add_argument("--date", type=date.fromisoformat)
parser.add_argument("--data-root", type=Path, default=Path("data"))
args = parser.parse_args()
target_date = args.date or latest_expected_trading_date(date.today(), args.data_root)
if args.domain == "market":
    output = collectors.sync_market(target_date, args.data_root)
elif args.domain == "institutional":
    output = collectors.sync_institutional(target_date, args.data_root)
elif args.domain == "margin":
    output = collectors.sync_margin(target_date, args.data_root)
elif args.domain == "calendar":
    output = collectors.sync_calendar(args.data_root)
elif args.domain == "tdcc":
    output = collectors.sync_tdcc(args.data_root)
elif args.domain == "financial":
    output = collectors.sync_financial(args.data_root)
elif args.domain == "revenue":
    output = collectors.sync_revenue(args.data_root)
elif args.domain == "etf":
    output = collectors.sync_etf(args.data_root)
elif args.domain == "fx":
    output = collectors.sync_fx(args.data_root)
else:
    output = collectors.sync_corporate_actions(args.data_root)
print(output)
