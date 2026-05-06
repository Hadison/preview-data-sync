#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_sources import tpex, twse
from etf_update.updater import load_preview
from etf_update.prices import load_prices, update_price_store, write_prices


DEFAULT_HOLDINGS_INPUT = PROJECT_ROOT / "public" / "preview" / "00981a.json"
LEGACY_HOLDINGS_INPUT = PROJECT_ROOT / "preview" / "00981a.json"
DEFAULT_PRICES_INPUT = PROJECT_ROOT / "public" / "preview" / "00981a-prices.json"
LEGACY_PRICES_INPUT = PROJECT_ROOT / "preview" / "00981a-prices.json"

logger = logging.getLogger("update_00981a_prices")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update 00981A component stock price history.")
    parser.add_argument("--holdings-input", type=Path, default=DEFAULT_HOLDINGS_INPUT)
    parser.add_argument("--prices-input", type=Path, default=DEFAULT_PRICES_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_PRICES_INPUT)
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()

    holdings_input = resolve_input_path(args.holdings_input, DEFAULT_HOLDINGS_INPUT, LEGACY_HOLDINGS_INPUT)
    prices_input = resolve_input_path(args.prices_input, DEFAULT_PRICES_INPUT, LEGACY_PRICES_INPUT)
    holdings = load_preview(holdings_input)
    existing_prices = load_prices(prices_input)

    updated_prices, stats = update_price_store(
        existing_prices,
        holdings,
        fetcher=lambda code, start, end: fetch_with_providers(code, start, end, sleep_seconds=args.sleep_seconds),
    )

    if updated_prices != existing_prices:
        write_prices(args.output, updated_prices)
    elif prices_input != args.output and prices_input.exists():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(prices_input, args.output)

    logger.info("新增股票: %s", stats.new_codes)
    logger.info("更新股票: %s", stats.updated_codes)
    logger.info("補價格筆數: %s", stats.added_price_rows)
    if stats.failed_codes:
        logger.warning("抓取失敗股票: %s", ", ".join(f"{code}={err}" for code, err in stats.failed_codes.items()))
    else:
        logger.info("抓取失敗股票: 無")
    logger.info("price as_of=%s first_date=%s codes=%s", updated_prices["as_of"], updated_prices["first_date"], len(updated_prices["codes"]))
    return 0


def resolve_input_path(path: Path, default_path: Path, legacy_path: Path) -> Path:
    if path.exists():
        return path
    if path == default_path and legacy_path.exists():
        return legacy_path
    return path


def fetch_with_providers(code: str, start_date: str, end_date: str, *, sleep_seconds: float) -> list[dict]:
    errors = []
    for provider_name, provider in (("TWSE", twse), ("TPEx", tpex)):
        try:
            rows = provider.fetch_prices(code, start_date, end_date)
            time.sleep(sleep_seconds)
            if rows:
                logger.info("%s %s fetched %s rows", provider_name, code, len(rows))
                return rows
            errors.append(f"{provider_name}: no rows")
        except Exception as exc:
            errors.append(f"{provider_name}: {exc}")
    raise RuntimeError(" | ".join(errors))


if __name__ == "__main__":
    raise SystemExit(main())

