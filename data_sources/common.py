from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from io import StringIO
from typing import Any

from etf_update.models import Holding


FIELD_ALIASES = {
    "date": ("date", "資料日期", "日期", "as_of", "dataDate"),
    "code": ("code", "股票代號", "證券代號", "symbol", "stockId", "stock_id"),
    "name": ("name", "股票名稱", "證券名稱", "stockName", "stock_name"),
    "weight": ("weight", "權重", "持股比重", "比重", "比例", "持股比例"),
    "shares": ("shares", "股數", "持股股數", "持有股數", "持股數"),
}


def holdings_from_rows(rows: Iterable[dict[str, Any]], default_date: str | None = None) -> list[Holding]:
    holdings: list[Holding] = []
    for row in rows:
        normalized = normalize_row(row)
        if default_date and not normalized.get("date"):
            normalized["date"] = default_date
        holdings.append(Holding.from_mapping(normalized))
    return holdings


def parse_json_payload(text: str) -> list[dict[str, Any]]:
    payload = json.loads(text)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("holdings", "data", "items", "rows", "current"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        nested_data = payload.get("data")
        if isinstance(nested_data, dict):
            for key in ("holdings", "items", "rows"):
                value = nested_data.get(key)
                if isinstance(value, list):
                    return value
    raise ValueError("JSON payload does not contain a holdings list")


def parse_csv_payload(text: str) -> list[dict[str, Any]]:
    sample = text[:4096]
    dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
    reader = csv.DictReader(StringIO(text), dialect=dialect)
    return [dict(row) for row in reader]


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for target, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in row and row[alias] not in (None, ""):
                normalized[target] = row[alias]
                break
    return normalized

