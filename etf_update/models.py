from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


DATE_FORMAT = "%Y%m%d"


@dataclass(frozen=True)
class Holding:
    date: str
    code: str
    name: str
    weight: float
    shares: float | None = None

    @classmethod
    def from_mapping(cls, row: dict[str, Any]) -> "Holding":
        return cls(
            date=normalize_date(row.get("date")),
            code=str(row.get("code", "")).strip().upper(),
            name=str(row.get("name", "")).strip(),
            weight=parse_float(row.get("weight"), "weight"),
            shares=parse_optional_float(row.get("shares"), "shares"),
        )

    def to_current_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "date": self.date,
            "code": self.code,
            "name": self.name,
            "weight": self.weight,
        }
        if self.shares is not None:
            data["shares"] = self.shares
        return data

    def to_series_point(self) -> dict[str, Any]:
        data: dict[str, Any] = {"date": self.date, "weight": self.weight}
        if self.shares is not None:
            data["shares"] = self.shares
        return data


def normalize_date(value: Any) -> str:
    if value is None:
        raise ValueError("date is required")

    raw = str(value).strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).strftime(DATE_FORMAT)
        except ValueError:
            continue
    raise ValueError(f"invalid date: {raw}")


def parse_float(value: Any, field_name: str) -> float:
    if value is None or value == "":
        raise ValueError(f"{field_name} is required")
    try:
        cleaned = str(value).strip().replace(",", "").replace("%", "")
        return round(float(cleaned), 6)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric: {value!r}") from exc


def parse_optional_float(value: Any, field_name: str) -> float | None:
    if value is None or value == "":
        return None
    return parse_float(value, field_name)

