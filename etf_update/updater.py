from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .models import Holding
from .validation import validate_holdings


DEFAULT_ETF = {
    "code": "00981A",
    "name": "主動統一台股增長",
    "issuer": "統一投信",
}


def load_preview(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "etf": DEFAULT_ETF,
            "as_of": "",
            "first_date": "",
            "n_days": 0,
            "current": [],
            "exited_codes": [],
            "exit_date": {},
            "active_days": {},
            "series": {},
            "name_of": {},
        }
    return json.loads(path.read_text(encoding="utf-8"))


def write_preview(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def update_preview(existing: dict[str, Any], holdings: list[Holding]) -> tuple[dict[str, Any], bool]:
    previous_as_of = existing.get("as_of") or None
    validated = validate_holdings(holdings, previous_as_of=previous_as_of)
    update_date = validated[0].date

    if previous_as_of == update_date:
        updated_same_day = deepcopy(existing)
        desired_current = [row.to_current_dict() for row in validated]
        if updated_same_day.get("current") == desired_current:
            return updated_same_day, False
        updated_same_day["current"] = desired_current
        return updated_same_day, True

    updated = deepcopy(existing)
    updated.setdefault("etf", DEFAULT_ETF)
    updated.setdefault("series", {})
    updated.setdefault("name_of", {})
    updated.setdefault("exit_date", {})
    updated.setdefault("active_days", {})

    previous_current_codes = {str(row.get("code", "")).strip() for row in updated.get("current", [])}
    current_codes = {row.code for row in validated}
    exited_today = sorted(code for code in previous_current_codes - current_codes if code)

    for row in validated:
        history = list(updated["series"].get(row.code, []))
        if not any(point.get("date") == update_date for point in history):
            history.append(row.to_series_point())
        updated["series"][row.code] = history
        updated["name_of"][row.code] = row.name

    for code in exited_today:
        updated["exit_date"][code] = update_date
    for code in current_codes:
        updated["exit_date"].pop(code, None)

    ever_held_codes = set(updated["series"].keys())
    exited_codes = sorted(code for code in ever_held_codes - current_codes if code)
    updated["exited_codes"] = exited_codes

    updated["active_days"] = {
        code: sum(1 for point in points if float(point.get("weight", 0) or 0) > 0)
        for code, points in updated["series"].items()
    }
    updated["days_held"] = dict(updated["active_days"])
    updated["current"] = [row.to_current_dict() for row in validated]
    updated["as_of"] = update_date
    updated["first_date"] = updated.get("first_date") or update_date
    updated["n_days"] = count_distinct_dates(updated["series"])

    return updated, True


def count_distinct_dates(series: dict[str, list[dict[str, Any]]]) -> int:
    return len({str(point.get("date")) for points in series.values() for point in points if point.get("date")})
