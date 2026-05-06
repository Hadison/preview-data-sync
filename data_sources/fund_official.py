from __future__ import annotations

import os

import requests

from etf_update.models import Holding

from .common import holdings_from_rows, parse_csv_payload, parse_json_payload


def fetch(etf_code: str = "00981A", source_url: str | None = None) -> list[Holding]:
    url = source_url or os.environ.get("ETF_HOLDINGS_URL")
    if not url:
        raise RuntimeError(
            "official source needs ETF_HOLDINGS_URL or --source-url. "
            "The endpoint may be JSON or CSV with date/code/name/weight/shares fields."
        )

    response = requests.get(url, timeout=30, headers={"User-Agent": f"ETFupdate/{etf_code}"})
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    text = response.text

    if "json" in content_type or text.lstrip().startswith(("{", "[")):
        rows = parse_json_payload(text)
    else:
        rows = parse_csv_payload(text)
    return holdings_from_rows(rows)

