from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DATE_RE = re.compile(r"^\d{8}$")


@dataclass(frozen=True)
class PriceUpdateStats:
    new_codes: int
    updated_codes: int
    added_price_rows: int
    failed_codes: dict[str, str]


def load_prices(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"as_of": "", "first_date": "", "codes": [], "prices": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def write_prices(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def extract_holding_codes(holdings: dict[str, Any]) -> list[str]:
    codes = set()
    for row in holdings.get("current", []):
        code = str(row.get("code", "")).strip()
        if _is_security_code(code):
            codes.add(code)
    for code in holdings.get("series", {}).keys():
        code = str(code).strip()
        if _is_security_code(code):
            codes.add(code)
    for code in holdings.get("exited_codes", []):
        code = str(code).strip()
        if _is_security_code(code):
            codes.add(code)
    return sorted(codes)


def next_calendar_day(date_text: str) -> str:
    return (datetime.strptime(date_text, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")


def month_starts_between(start_date: str, end_date: str) -> list[str]:
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    cursor = start.replace(day=1)
    months = []
    while cursor <= end:
        months.append(cursor.strftime("%Y%m%d"))
        year = cursor.year + (1 if cursor.month == 12 else 0)
        month = 1 if cursor.month == 12 else cursor.month + 1
        cursor = cursor.replace(year=year, month=month, day=1)
    return months


def merge_prices(existing_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {row["date"]: normalize_price_row(row) for row in existing_rows}
    for row in new_rows:
        normalized = normalize_price_row(row)
        merged[normalized["date"]] = normalized
    rows = [merged[date] for date in sorted(merged)]
    validate_price_rows(rows)
    return rows


def normalize_price_row(row: dict[str, Any]) -> dict[str, Any]:
    date = str(row.get("date", "")).strip()
    if not DATE_RE.match(date):
        raise ValueError(f"invalid price date: {date}")

    return {
        "date": date,
        "open": _parse_float(row.get("open"), "open"),
        "high": _parse_float(row.get("high"), "high"),
        "low": _parse_float(row.get("low"), "low"),
        "close": _parse_float(row.get("close"), "close"),
        "adj_factor": _parse_float(row.get("adj_factor", 1.0), "adj_factor"),
        "volume_shares": _parse_int(row.get("volume_shares"), "volume_shares"),
    }


def validate_price_rows(rows: list[dict[str, Any]]) -> None:
    seen_dates = set()
    for row in rows:
        normalized = normalize_price_row(row)
        date = normalized["date"]
        if date in seen_dates:
            raise ValueError(f"duplicate price date: {date}")
        if normalized["high"] < normalized["low"]:
            raise ValueError(f"high cannot be lower than low: {date}")
        seen_dates.add(date)


def update_price_store(
    existing: dict[str, Any],
    holdings: dict[str, Any],
    fetcher,
) -> tuple[dict[str, Any], PriceUpdateStats]:
    as_of = str(holdings.get("as_of") or "").strip()
    first_date = str(holdings.get("first_date") or "").strip()
    if not DATE_RE.match(as_of):
        raise ValueError(f"holdings as_of must be YYYYMMDD: {as_of}")
    if not DATE_RE.match(first_date):
        raise ValueError(f"holdings first_date must be YYYYMMDD: {first_date}")

    existing_codes = {str(code).strip() for code in existing.get("codes", []) if _is_security_code(str(code).strip())}
    holding_codes = set(extract_holding_codes(holdings))
    all_codes = sorted(existing_codes | holding_codes)

    updated = deepcopy(existing)
    previous_codes = sorted(existing_codes)
    previous_as_of = str(existing.get("as_of") or "").strip()
    previous_first_date = str(existing.get("first_date") or "").strip()
    updated["as_of"] = as_of
    updated["first_date"] = first_date
    updated["codes"] = all_codes
    updated.setdefault("prices", {})

    new_codes = len(holding_codes - existing_codes)
    updated_codes = 0
    added_price_rows = 0
    failed_codes: dict[str, str] = {}

    for code in all_codes:
        old_rows = [normalize_price_row(row) for row in updated.get("prices", {}).get(code, [])]
        if not _is_taiwan_price_code(code):
            updated["prices"][code] = merge_prices(old_rows, [])
            continue
        fetch_start = first_date if not old_rows else next_calendar_day(old_rows[-1]["date"])
        if fetch_start > as_of:
            updated["prices"][code] = merge_prices(old_rows, [])
            continue

        try:
            new_rows = fetcher(code, fetch_start, as_of)
            filtered_rows = [row for row in new_rows if fetch_start <= row["date"] <= as_of]
            merged_rows = merge_prices(old_rows, filtered_rows)
            added_for_code = max(0, len({row["date"] for row in merged_rows}) - len({row["date"] for row in old_rows}))
            if added_for_code:
                updated_codes += 1
                added_price_rows += added_for_code
            updated["prices"][code] = merged_rows
        except Exception as exc:
            failed_codes[code] = str(exc)
            updated["prices"][code] = merge_prices(old_rows, [])

    stats = PriceUpdateStats(
        new_codes=new_codes,
        updated_codes=updated_codes,
        added_price_rows=added_price_rows,
        failed_codes=failed_codes,
    )
    has_data_change = (
        previous_as_of != as_of
        or previous_first_date != first_date
        or previous_codes != all_codes
        or added_price_rows > 0
    )
    updated["source"] = "TWSE/TPEx official daily trading APIs"
    if has_data_change or not updated.get("generated_at"):
        updated["generated_at"] = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return updated, stats


def _parse_float(value: Any, field_name: str) -> float:
    try:
        return float(str(value).strip().replace(",", "").replace("--", ""))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric: {value!r}") from exc


def _parse_int(value: Any, field_name: str) -> int:
    try:
        return int(float(str(value).strip().replace(",", "")))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be integer: {value!r}") from exc


def _is_security_code(code: str) -> bool:
    if not code:
        return False
    if code.startswith(("C_", "DA_")):
        return False
    return True


def _is_taiwan_price_code(code: str) -> bool:
    return bool(re.match(r"^\d{4,6}$", code))
