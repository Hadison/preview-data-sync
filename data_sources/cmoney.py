from __future__ import annotations

import os

import requests

from etf_update.models import Holding

from .common import holdings_from_rows, parse_csv_payload, parse_json_payload

CMONEY_DTNO_SHAREHOLDING_TW = "59449513"
CMONEY_ENDPOINT = "https://www.cmoney.tw/MobileService/ashx/GetDtnoData.ashx"


def fetch(etf_code: str = "00981A", source_url: str | None = None) -> list[Holding]:
    url = source_url or os.environ.get("CMONEY_HOLDINGS_URL")
    if url:
        return _fetch_structured_url(url)

    response = requests.get(
        CMONEY_ENDPOINT,
        timeout=30,
        headers={"User-Agent": f"preview-data-sync/{etf_code}"},
        params={
            "action": "getdtnodata",
            "DtNo": CMONEY_DTNO_SHAREHOLDING_TW,
            "ParamStr": f"AssignID={etf_code};MTPeriod=0;DTMode=0;DTRange=1;DTOrder=1;MajorTable=M722;",
            "FilterNo": "0",
        },
    )
    response.raise_for_status()
    return _parse_cmoney_dtno_payload(response.json())


def _fetch_structured_url(url: str) -> list[Holding]:
    response = requests.get(url, timeout=30, headers={"User-Agent": "preview-data-sync/00981A"})
    response.raise_for_status()
    text = response.text
    if "json" in response.headers.get("content-type", "").lower() or text.lstrip().startswith(("{", "[")):
        rows = parse_json_payload(text)
    else:
        rows = parse_csv_payload(text)
    return holdings_from_rows(rows)


def _parse_cmoney_dtno_payload(payload: dict) -> list[Holding]:
    rows = []
    for row in payload.get("Data", []):
        if len(row) < 6:
            continue
        date, code, name, weight, shares, unit = row[:6]
        if str(unit).strip() != "股":
            continue
        rows.append(
            {
                "date": date,
                "code": code,
                "name": name,
                "weight": weight,
                "shares": shares,
            }
        )
    return holdings_from_rows(rows)
