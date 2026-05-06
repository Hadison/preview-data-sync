from __future__ import annotations

import time

import requests

from etf_update.prices import month_starts_between


TWSE_STOCK_DAY_ENDPOINT = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"


def fetch_prices(code: str, start_date: str, end_date: str) -> list[dict]:
    rows: list[dict] = []
    for month_start in month_starts_between(start_date, end_date):
        payload = _get_month_payload(code, month_start)
        if payload.get("stat") in ("很抱歉，沒有符合條件的資料!", "查詢日期大於今日，請重新查詢!"):
            continue
        if payload.get("stat") != "OK":
            raise RuntimeError(f"TWSE returned {payload.get('stat')}")
        rows.extend(_parse_payload(payload))
    return [row for row in rows if start_date <= row["date"] <= end_date]


def _get_month_payload(code: str, month_start: str) -> dict:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(
                TWSE_STOCK_DAY_ENDPOINT,
                timeout=30,
                headers={"User-Agent": f"ETFupdate-prices/{code}"},
                params={"response": "json", "date": month_start, "stockNo": code},
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"TWSE request failed after retries: {last_error}")


def _parse_payload(payload: dict) -> list[dict]:
    result = []
    for row in payload.get("data", []):
        if len(row) < 7:
            continue
        try:
            result.append(
                {
                    "date": _roc_date_to_yyyymmdd(row[0]),
                    "volume_shares": _parse_int(row[1]),
                    "open": _parse_float(row[3]),
                    "high": _parse_float(row[4]),
                    "low": _parse_float(row[5]),
                    "close": _parse_float(row[6]),
                    "adj_factor": 1.0,
                }
            )
        except ValueError:
            continue
    return result


def _roc_date_to_yyyymmdd(value: str) -> str:
    year, month, day = [int(part) for part in value.split("/")]
    return f"{year + 1911:04d}{month:02d}{day:02d}"


def _parse_float(value) -> float:
    text = str(value).strip().replace(",", "")
    if text in ("", "--", "X0.00"):
        raise ValueError(f"invalid numeric field: {value!r}")
    return float(text)


def _parse_int(value) -> int:
    return int(str(value).strip().replace(",", ""))
