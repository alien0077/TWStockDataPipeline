#!/usr/bin/env python3
"""Export one historical TWSE + TPEx daily close snapshot.

This is a public-data compatibility helper for downstream research consumers.
It uses official historical endpoints and writes the normalized
``daily/tw/YYYY-MM-DD.json`` contract without valuation logic.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
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


def first(values: dict, *names):
    for name in names:
        if name in values and values[name] not in (None, ""):
            return values[name]
    return None


def get_with_retry(url: str, *, params: dict, attempts: int = 4, timeout: int = 30):
    last = None
    session = requests.Session()
    session.headers.update(HEADERS)
    for attempt in range(attempts):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(min(8.0, 1.0 * (2**attempt)))
    raise last or RuntimeError(f"REQUEST_FAILED:{url}")


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


def tpex_rows(payload: dict, day: date) -> list[dict]:
    """Parse TPEx historical JSON tables using labels before positional fallback."""
    rows: list[dict] = []
    seen: set[str] = set()
    for table in payload.get("tables", []):
        fields = table.get("fields", [])
        raw_rows = table.get("data", [])
        if not isinstance(fields, list) or not isinstance(raw_rows, list):
            continue
        for raw in raw_rows:
            if not isinstance(raw, list) or len(raw) < 8:
                continue
            values = dict(zip(fields, raw))
            stock_id = str(
                first(values, "代號", "證券代號", "股票代號")
                or raw[0]
                or ""
            ).strip().strip('="')
            if not SECURITY_CODE.fullmatch(stock_id):
                continue
            close = number(first(values, "收盤", "收盤價") or (raw[2] if len(raw) > 2 else None))
            if close is None or stock_id in seen:
                continue
            seen.add(stock_id)
            rows.append(
                {
                    "id": stock_id,
                    "date": day.isoformat(),
                    "market": "TPEX",
                    "o": number(first(values, "開盤", "開盤價") or (raw[4] if len(raw) > 4 else None)),
                    "h": number(first(values, "最高", "最高價") or (raw[5] if len(raw) > 5 else None)),
                    "l": number(first(values, "最低", "最低價") or (raw[6] if len(raw) > 6 else None)),
                    "c": close,
                    "v": number(first(values, "成交股數", "成交量") or (raw[7] if len(raw) > 7 else None)),
                    "t": number(first(values, "成交金額(元)", "成交金額") or (raw[8] if len(raw) > 8 else None)),
                }
            )
        if rows:
            break
    return rows


def tpex_csv_rows(text: str, day: date) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for raw in csv.reader(io.StringIO(text)):
        if len(raw) < 9:
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
                "o": number(raw[4]) if len(raw) > 4 else None,
                "h": number(raw[5]) if len(raw) > 5 else None,
                "l": number(raw[6]) if len(raw) > 6 else None,
                "c": close,
                "v": number(raw[7]) if len(raw) > 7 else None,
                "t": number(raw[8]) if len(raw) > 8 else None,
            }
        )
    return rows


def parse_tpex_response(response: requests.Response, day: date) -> list[dict]:
    # TPEx has historically returned JSON payloads from both its JSON and
    # download routes. Try JSON first, then Big5/UTF-8 CSV as a conservative
    # fallback. No row is accepted unless a security code and numeric close
    # are present.
    try:
        payload = response.json()
        if isinstance(payload, dict):
            rows = tpex_rows(payload, day)
            if rows:
                return rows
    except (ValueError, json.JSONDecodeError):
        pass
    for encoding in ("big5", "utf-8-sig", "utf-8"):
        try:
            text = response.content.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            continue
        stripped = text.lstrip()
        if stripped.startswith("{"):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                rows = tpex_rows(payload, day)
                if rows:
                    return rows
        rows = tpex_csv_rows(text, day)
        if rows:
            return rows
    return []


def fetch_tpex(day: date) -> tuple[list[dict], str]:
    roc_day = f"{day.year - 1911}/{day.month:02d}/{day.day:02d}"
    endpoints = [
        (
            "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php",
            {"l": "zh-tw", "d": roc_day, "se": "EW", "o": "json"},
        ),
        (
            "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes/download",
            {"d": roc_day},
        ),
    ]
    errors: list[str] = []
    for url, params in endpoints:
        try:
            response = get_with_retry(url, params=params)
            rows = parse_tpex_response(response, day)
            if rows:
                return rows, url
            errors.append(f"{url}:EMPTY_OR_UNPARSEABLE")
        except requests.RequestException as exc:
            errors.append(f"{url}:{type(exc).__name__}:{exc}")
    raise RuntimeError("TPEX_HISTORICAL_FETCH_FAILED:" + ";".join(errors))


def fetch(day: date) -> dict:
    stamp = day.strftime("%Y%m%d")
    twse = get_with_retry(
        "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
        params={"date": stamp, "type": "ALLBUT0999", "response": "json"},
    )
    twse_market = twse_rows(twse.json(), day)
    tpex_market, tpex_source = fetch_tpex(day)
    rows = twse_market + tpex_market
    deduped = {str(row["id"]): row for row in rows}
    return {
        "version": "2.1",
        "updated_at": day.isoformat(),
        "stocks": list(deduped.values()),
        "data": list(deduped.values()),
        "source": "TWSE MI_INDEX + TPEx official historical endpoints",
        "source_detail": {
            "twse": "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
            "tpex": tpex_source,
        },
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
    print(json.dumps({"counts": payload["counts"], "source_detail": payload["source_detail"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
