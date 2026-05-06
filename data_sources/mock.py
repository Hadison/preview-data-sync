from __future__ import annotations

import json
import os
from pathlib import Path

from etf_update.models import Holding


def fetch(etf_code: str = "00981A", source_url: str | None = None) -> list[Holding]:
    path = Path(source_url or os.environ.get("MOCK_HOLDINGS_FILE", "preview/00981a.json"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    current = payload.get("current", [])
    if not current:
        raise RuntimeError(f"mock source has no current holdings: {path}")

    series = payload.get("series", {})
    enriched = []
    for row in current:
        row_with_shares = dict(row)
        if row_with_shares.get("shares") is None:
            row_with_shares["shares"] = _find_series_shares(
                series.get(str(row_with_shares.get("code", "")).strip(), []),
                str(row_with_shares.get("date", "")).strip(),
            )
        enriched.append(row_with_shares)
    return [Holding.from_mapping(row) for row in enriched]


def _find_series_shares(points, target_date: str):
    for point in reversed(points):
        if str(point.get("date", "")).strip() == target_date and point.get("shares") is not None:
            return point.get("shares")
    return None
