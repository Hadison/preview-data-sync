#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from etf_update.updater import load_preview, update_preview, write_preview

DEFAULT_INPUT = PROJECT_ROOT / "public" / "preview" / "00981a.json"
LEGACY_INPUT = PROJECT_ROOT / "preview" / "00981a.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update 00981A ETF holdings preview JSON.")
    parser.add_argument("--source", default="auto", choices=("auto", "fund_official", "cmoney", "mock"))
    parser.add_argument("--source-url", default=None, help="Optional JSON/CSV endpoint for the selected source.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--etf-code", default="00981A")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = resolve_input_path(args.input)
    source_name, holdings = fetch_holdings(args.source, args.etf_code, args.source_url)

    existing = load_preview(input_path)
    updated, changed = update_preview(existing, holdings)
    if changed:
        write_preview(args.output, updated)
        print(f"updated {args.output} from {source_name}: as_of={updated['as_of']} n_days={updated['n_days']}")
    else:
        if input_path != args.output and input_path.exists():
            args.output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(input_path, args.output)
        print(f"no update needed from {source_name}: as_of={updated.get('as_of')}")
    return 0


def resolve_input_path(path: Path) -> Path:
    if path.exists():
        return path
    if path == DEFAULT_INPUT and LEGACY_INPUT.exists():
        return LEGACY_INPUT
    return path


def fetch_holdings(source: str, etf_code: str, source_url: str | None):
    sources = ("fund_official", "cmoney", "mock") if source == "auto" else (source,)
    errors: list[str] = []
    for source_name in sources:
        try:
            module = importlib.import_module(f"data_sources.{source_name}")
            return source_name, module.fetch(etf_code=etf_code, source_url=source_url)
        except Exception as exc:
            errors.append(f"{source_name}: {exc}")
            if source != "auto":
                raise
    raise RuntimeError("all sources failed: " + " | ".join(errors))


if __name__ == "__main__":
    raise SystemExit(main())
