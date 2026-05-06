#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import json
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREVIEW_DIRS = [PROJECT_ROOT / "preview", PROJECT_ROOT / "public" / "preview"]


def main() -> int:
    etf_files = discover_etf_files()
    if not etf_files:
        raise RuntimeError("no ETF preview JSON files found")

    for input_path in etf_files:
        stem = input_path.stem.lower()
        etf_code = stem.upper()
        output_path = PROJECT_ROOT / "public" / "preview" / f"{stem}.json"
        prices_input = find_prices_input(stem)
        prices_output = PROJECT_ROOT / "public" / "preview" / f"{stem}-prices.json"

        print(f"==> Updating {etf_code}", flush=True)
        commands = [
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "update_00981a.py"),
                "--source",
                "auto",
                "--etf-code",
                etf_code,
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ],
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "update_00981a_prices.py"),
                "--holdings-input",
                str(output_path),
                "--prices-input",
                str(prices_input),
                "--output",
                str(prices_output),
                "--sleep-seconds",
                os.environ.get("ETF_PRICE_SLEEP_SECONDS", "0.05"),
            ],
        ]
        for command in commands:
            subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    write_manifest()
    return 0


def discover_etf_files() -> list[Path]:
    by_stem: dict[str, Path] = {}
    for directory in PREVIEW_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            if path.name.endswith("-prices.json") or path.name == "index.json":
                continue
            by_stem[path.stem.lower()] = path
    return [by_stem[stem] for stem in sorted(by_stem)]


def find_prices_input(stem: str) -> Path:
    public_path = PROJECT_ROOT / "public" / "preview" / f"{stem}-prices.json"
    legacy_path = PROJECT_ROOT / "preview" / f"{stem}-prices.json"
    if public_path.exists():
        return public_path
    if legacy_path.exists():
        return legacy_path
    return public_path


def write_manifest() -> None:
    preview_dir = PROJECT_ROOT / "public" / "preview"
    items = []
    for path in sorted(preview_dir.glob("*.json")):
        if path.name.endswith("-prices.json") or path.name == "index.json":
            continue
        prices_path = preview_dir / f"{path.stem}-prices.json"
        try:
            holdings = json.loads(path.read_text(encoding="utf-8"))
            prices = json.loads(prices_path.read_text(encoding="utf-8")) if prices_path.exists() else {}
        except json.JSONDecodeError:
            continue
        items.append(
            {
                "slug": path.stem.lower(),
                "code": holdings.get("etf", {}).get("code", path.stem.upper()),
                "name": holdings.get("etf", {}).get("name", ""),
                "issuer": holdings.get("etf", {}).get("issuer", ""),
                "holdings_as_of": holdings.get("as_of", ""),
                "prices_as_of": prices.get("as_of", ""),
                "current_count": len(holdings.get("current", [])),
                "price_code_count": len(prices.get("codes", [])),
            }
        )
    manifest_path = preview_dir / "index.json"
    manifest_path.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
