from __future__ import annotations

from collections.abc import Iterable

from .models import Holding, normalize_date


class ValidationError(ValueError):
    pass


def validate_holdings(
    holdings: Iterable[Holding],
    *,
    previous_as_of: str | None = None,
    min_weight_sum: float = 60.0,
    max_weight_sum: float = 105.0,
) -> list[Holding]:
    rows = list(holdings)
    if not rows:
        raise ValidationError("holdings cannot be empty")

    dates = {row.date for row in rows}
    if len(dates) != 1:
        raise ValidationError(f"all holdings must use one date, got: {sorted(dates)}")

    current_date = next(iter(dates))
    if previous_as_of and current_date < normalize_date(previous_as_of):
        raise ValidationError(f"date cannot move backwards: {current_date} < {previous_as_of}")

    seen_codes: set[str] = set()
    for row in rows:
        if not row.code:
            raise ValidationError("stock code cannot be empty")
        if row.code in seen_codes:
            raise ValidationError(f"duplicate stock code: {row.code}")
        if not isinstance(row.weight, (int, float)):
            raise ValidationError(f"weight must be numeric: {row.code}")
        if row.weight < 0:
            raise ValidationError(f"weight cannot be negative: {row.code}")
        if row.shares is not None and row.shares < 0:
            raise ValidationError(f"shares cannot be negative: {row.code}")
        seen_codes.add(row.code)

    total_weight = sum(row.weight for row in rows)
    if not min_weight_sum <= total_weight <= max_weight_sum:
        raise ValidationError(
            f"weight sum is outside expected range: {total_weight:.2f} "
            f"(expected {min_weight_sum:.2f}-{max_weight_sum:.2f})"
        )

    return rows

