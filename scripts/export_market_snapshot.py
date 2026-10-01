#!/usr/bin/env python3
"""Export one historical TWSE + TPEx daily close snapshot.

This is a public-data compatibility helper for downstream research consumers.
It uses the same official endpoints as the pipeline and writes the normalized
``daily/tw/YYYY-MM-DD.json`` contract without any valuation logic.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
from datetime import date
from pathlib import Path

import requests

HEADERS = {
    "User-Agent": "TWStockDataPipeline/1.0",
    "Accept": "application/json,text/plain,*/*",
}
SECURITY_CODE = re.compile(r"^[0-9A-Z]{4,8}$")


def number(value):
    text = str(value or "").replace(",", "").strip()
    if text in {"", "--", "---", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def twse_rows(payload: dict, day: date) -> list[dict]:
    rows: list[dict] = []
    for table in payload.get("tables", []):
        fields = table.get("fields", [])
        if "證券代號" not in fields or "收盤價" not in fields:
            continue
        for raw in table.get("data", []):
            values = dict(zip(fields, raw))
            stock_id = str(values.get("證券代號", "")).strip()
            close = number(values.get("收盤價"))
            if not stock_id or close is None:
                continue
            rows.append(
                {
                    "id": stock_id,
                    "date": day.isoformat(),
                    "market": "TWSE",
                    "o": number(values.get("開盤價")),
                    "h": number(values.get("最高價")),
                    "l": number(values.get("最低價")),
                    "c": close,
                    "v": number(values.get("成交股數")),
                    "t": number(values.get("成交金額")),
                }
            )
        break
    return rows


def tpex_rows(text: str, day: date) -> list[dict]:
    """Parse TPEx dailyQuotes download rows.

    The official download is Big5 CSV. Data rows use the stable leading
    columns: security code, name, close, change, open, high, low, average,
    volume, amount, transactions. Header/footer rows are rejected by security
    code + numeric close validation instead of relying on localized labels.
    """
    rows: list[dict] = []
    seen: set[str] = set()
    for raw in csv.reader(io.StringIO(text)):
        if len(raw) < 10:
            continue
        stock_id = str(raw[0]).strip().strip('="')
        if not SECURITY_CODE.fullmatch(stock_id):
            continue
        close = number(raw[2])
        if close is None or stock_id in seen:
            continue
        seen.add(stock_id)
        rows.append(
            {
                "id": stock_id,
                "date": day.isoformat(),
                "market": "TPEX",
                "o": number(raw[4]),
                "h": number(raw[5]),
                "l": number(raw[6]),
                "c": close,
                "v": number(raw[8]),
                "t": number(raw[9]),
            }
        )
    return rows


def fetch(day: date) -> dict:
    stamp = day.strftime("%Y%m%d")
    twse = requests.get(
        "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
        params={"date": stamp, "type": "ALLBUT0999", "response": "json"},
        headers=HEADERS,
        timeout=30,
    )
    twse.raise_for_status()
    tpex = requests.get(
        "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes/download",
        params={"d": f"{day.year - 1911}/{day.month:02d}/{day.day:02d}"},
        headers=HEADERS,
        timeout=30,
    )
    tpex.raise_for_status()
    rows = twse_rows(twse.json(), day)
    rows.extend(tpex_rows(tpex.content.decode("big5", errors="replace"), day))
    deduped = {str(row["id"]): row for row in rows}
    return {
        "version": "2.0",
        "updated_at": day.isoformat(),
        "stocks": list(deduped.values()),
        "data": list(deduped.values()),
        "source": "TWSE MI_INDEX + TPEx dailyQuotes official endpoints",
        "counts": {
            "total": len(deduped),
            "twse": sum(1 for row in deduped.values() if row["market"] == "TWSE"),
            "tpex": sum(1 for row in deduped.values() if row["market"] == "TPEX"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    day = date.fromisoformat(args.date)
    payload = fetch(day)
    if payload["counts"]["twse"] <= 0 or payload["counts"]["tpex"] <= 0:
        raise SystemExit(f"INCOMPLETE_MARKET_SNAPSHOT:{payload['counts']}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
