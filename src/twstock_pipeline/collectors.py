"""Public-only collectors using the official endpoints already used by TWStockTracker.

Collectors return raw JSON/CSV rows and write atomically. Derived rankings,
valuation and AI features are deliberately outside this module.
"""
from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

HEADERS = {"User-Agent": "TWStockDataPipeline/1.0", "Accept": "application/json,text/plain,*/*"}


def _request(url: str, params: dict | None = None, timeout: int = 30) -> requests.Response:
    response = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response


def _request_bounded(url: str, params: dict | None = None, timeout: int = 30, attempts: int = 3) -> requests.Response:
    last = None
    for attempt in range(attempts):
        try:
            return _request(url, params, timeout)
        except requests.RequestException as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise last


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def sync_market(day: date, data_root: Path) -> Path:
    """Fetch TWSE MI_INDEX and TPEX daily quotes into the raw public domain."""
    stamp = day.strftime("%Y%m%d")
    twse = _request("https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX", {"date": stamp, "type": "ALLBUT0999", "response": "json"}).json()
    tpex = _request("https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes/download", {"d": f"{day.year - 1911}/{day.month:02d}/{day.day:02d}"}).content.decode("big5", errors="replace")
    path = data_root / "daily" / "tw" / f"{day.isoformat()}.json"
    _write_json(path, {"date": day.isoformat(), "source": "TWSE/TPEX official daily market", "twse": twse, "tpex_csv": tpex})
    return path


def sync_institutional(day: date, data_root: Path) -> Path:
    stamp = day.strftime("%Y%m%d")
    payload = _request("https://www.twse.com.tw/rwd/zh/fund/T86", {"date": stamp, "selectType": "ALLBUT0999", "response": "json"}).json()
    path = data_root / "daily" / "institutional" / f"{day.isoformat()}.json"
    _write_json(path, {"date": day.isoformat(), "source": "TWSE T86 official institutional trading", "payload": payload})
    return path


def sync_margin(day: date, data_root: Path) -> Path:
    stamp = day.strftime("%Y%m%d")
    payload = _request("https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN", {"date": stamp, "selectType": "ALL", "response": "json"}).json()
    path = data_root / "daily" / "tw_market_margin" / f"{day.isoformat()}.json"
    _write_json(path, {"date": day.isoformat(), "source": "TWSE MI_MARGN official margin", "payload": payload})
    return path


def sync_calendar(data_root: Path) -> Path:
    payload = _request("https://www.twse.com.tw/holidaySchedule/holidaySchedule", {"response": "json"}).json()
    holidays = [row[0].strip() for row in payload.get("data", []) if len(row) >= 2 and "開始交易" not in row[1]]
    path = data_root / "meta" / "calendar.json"
    today = date.today().isoformat()
    _write_json(path, {
        "version": "2.0",
        "updated_at": today,
        "stocks": [],
        "data": [],
        "meta": {"version": "2.0", "updated_at": today, "today": today, "years": {}},
        "source": "TWSE official holidaySchedule",
        "holidays": sorted(set(holidays)),
        "raw": payload,
    })
    return path


def sync_tdcc(data_root: Path) -> Path:
    response = _request("https://opendata.tdcc.com.tw/getOD.ashx?id=1-5", timeout=60)
    text = response.content.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    path = data_root / "weekly" / "tdcc" / "latest.json"
    _write_json(path, {"source": "TDCC official open data id=1-5", "rows": rows})
    return path


def sync_financial(data_root: Path) -> Path:
    endpoints = {
        "twse_profile": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "twse_income": "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci",
        "twse_balance": "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci",
        "tpex_profile": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
        "tpex_income": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_ci",
        "tpex_balance": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap07_O_ci",
    }
    payload = {name: _request(url).json() for name, url in endpoints.items()}
    path = data_root / "fundamentals" / "official_latest.json"
    _write_json(path, {"source": "TWSE/TPEX official OpenAPI", "datasets": payload})
    return path


def sync_revenue(data_root: Path) -> Path:
    endpoints = {
        "twse": "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
        "tpex": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O",
    }
    payload = {}
    errors = {}
    for name, url in endpoints.items():
        try:
            payload[name] = _request_bounded(url, timeout=30).json()
        except requests.RequestException as exc:
            errors[name] = {"error": type(exc).__name__, "message": str(exc)}
    if errors:
        payload["upstream_errors"] = errors
    path = data_root / "monthly" / "revenue" / "latest.json"
    _write_json(path, {"source": "TWSE/TPEX official monthly revenue", "datasets": payload, "upstream_status": "partial" if errors else "complete"})
    return path


def sync_etf(data_root: Path) -> Path:
    """Reuse the existing official ETF universe endpoint and ETFInfo holdings source."""
    universe = _request("https://openapi.twse.com.tw/v1/opendata/t187ap47_L").json()
    etfs = {}
    for item in universe:
        code = str(item.get("基金代號", "")).strip()
        name = str(item.get("基金簡稱", "")).strip()
        if not code or not name:
            continue
        etfs[code] = {
            "name": name,
            "category": "ETF",
            "type": "ETF",
            "tier": "official",
            "data_mode": "public_probe",
            "holdings": [],
            "source": "TWSE ETF OpenAPI",
        }
    # Holdings are a separate public source. Keep failures explicit per ETF;
    # never manufacture an empty successful holding list.
    def probe(entry: tuple[str, dict]) -> tuple[str, bool, str | None]:
        code, _ = entry
        try:
            response = _request(f"https://www.etfinfo.tw/etf/{code}/holdings", timeout=10)
            return code, response.status_code == 200 and '"holdings"' in response.text, None
        except Exception as exc:
            return code, False, type(exc).__name__

    # Bounded concurrency keeps a full universe run finite on hosted runners.
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(probe, entry) for entry in list(etfs.items())[:200]]
        for future in as_completed(futures):
            code, available, error = future.result()
            etfs[code]["raw_available"] = available
            if error:
                etfs[code]["probe_error"] = error
    path = data_root / "quant" / "etf" / "outputs" / "latest_snapshot.json"
    # Public_Data's legacy contract is a code-keyed snapshot, not a wrapper.
    _write_json(path, etfs)
    return path


def sync_fx(data_root: Path) -> Path:
    """Use the existing Yahoo Finance public chart source without private credentials."""
    symbols = {"USD_TWD": "USDTWD=X", "JPY_TWD": "JPYTWD=X", "EUR_TWD": "EURTWD=X"}
    end = int(datetime.now(timezone.utc).timestamp())
    start = int((datetime.now(timezone.utc) - timedelta(days=380)).timestamp())
    rows_by_date: dict[str, dict] = {}
    for label, symbol in symbols.items():
        payload = _request(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", {"period1": start, "period2": end, "interval": "1d"}).json()
        result = payload["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        for stamp, close in zip(result["timestamp"], closes):
            if close is not None:
                day = datetime.fromtimestamp(stamp, timezone.utc).date().isoformat()
                rows_by_date.setdefault(day, {"date": day})[label] = close
    path = data_root / "meta" / "exchange_rate_history.json"
    _write_json(path, {"version": "2.2", "updated_at": date.today().isoformat(), "base": "TWD", "currencies": list(symbols) + ["TWD_TWD"], "data": [rows_by_date[k] for k in sorted(rows_by_date)], "source": "Yahoo Finance chart public endpoint"})
    return path


def sync_corporate_actions(data_root: Path, start: date | None = None, end: date | None = None) -> Path:
    """Public acquisition/normalization of TWSE corporate-action records only."""
    start, end = start or date(end.year - 1, 1, 1) if end else date(datetime.now().year - 1, 1, 1), end or date.today()
    actions = []
    for kind, endpoint, code in (("DIVIDEND", "exRight", "TWT48U"), ("REDUCTION", "reducation", "TWTAUU"), ("SPLIT", "change", "TWTB8U")):
        payload = _request(f"https://www.twse.com.tw/rwd/zh/{endpoint}/{code}", {"startDate": start.strftime("%Y%m%d"), "endDate": end.strftime("%Y%m%d"), "response": "json"}).json()
        for row in payload.get("data", []):
            actions.append({"type": kind, "source": f"TWSE {code}", "raw": row, "fields": payload.get("fields", [])})
    path = data_root / "meta" / "actions" / f"{end.year}.json"
    updated_at = date.today().isoformat()
    _write_json(path, {"version": "2.0", "updated_at": updated_at, "stocks": actions, "data": actions, "source": "TWSE official corporate actions", "year": end.year})
    return path
