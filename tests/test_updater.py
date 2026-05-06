from __future__ import annotations

import unittest

from etf_update.models import Holding
from etf_update.prices import extract_holding_codes, merge_prices, update_price_store
from etf_update.updater import update_preview
from etf_update.validation import ValidationError, validate_holdings


class ValidationTests(unittest.TestCase):
    def test_rejects_backwards_date(self) -> None:
        holdings = [Holding(date="20260501", code="2330", name="台積電", weight=80.0, shares=1)]

        with self.assertRaises(ValidationError):
            validate_holdings(holdings, previous_as_of="20260502")

    def test_rejects_bad_weight_sum(self) -> None:
        holdings = [Holding(date="20260501", code="2330", name="台積電", weight=10.0, shares=1)]

        with self.assertRaises(ValidationError):
            validate_holdings(holdings)


class UpdaterTests(unittest.TestCase):
    def test_adds_new_day_and_marks_exit(self) -> None:
        existing = {
            "etf": {"code": "00981A"},
            "as_of": "20260501",
            "first_date": "20260501",
            "n_days": 1,
            "current": [
                {"date": "20260501", "code": "2330", "name": "台積電", "weight": 70.0, "shares": 10},
                {"date": "20260501", "code": "2317", "name": "鴻海", "weight": 20.0, "shares": 20},
            ],
            "series": {
                "2330": [{"date": "20260501", "weight": 70.0, "shares": 10}],
                "2317": [{"date": "20260501", "weight": 20.0, "shares": 20}],
            },
            "exited_codes": [],
            "exit_date": {},
            "active_days": {},
            "name_of": {"2330": "台積電", "2317": "鴻海"},
        }
        holdings = [
            Holding(date="20260504", code="2330", name="台積電", weight=65.0, shares=12),
            Holding(date="20260504", code="2454", name="聯發科", weight=25.0, shares=3),
        ]

        updated, changed = update_preview(existing, holdings)

        self.assertTrue(changed)
        self.assertEqual(updated["as_of"], "20260504")
        self.assertEqual(updated["n_days"], 2)
        self.assertEqual(updated["exit_date"]["2317"], "20260504")
        self.assertIn("2317", updated["exited_codes"])
        self.assertEqual(len(updated["series"]["2330"]), 2)
        self.assertEqual(updated["active_days"]["2454"], 1)

    def test_existing_date_is_idempotent(self) -> None:
        existing = {
            "as_of": "20260501",
            "current": [{"date": "20260501", "code": "2330", "name": "台積電", "weight": 90.0}],
            "series": {"2330": [{"date": "20260501", "weight": 90.0}]},
        }
        holdings = [Holding(date="20260501", code="2330", name="台積電", weight=90.0)]

        updated, changed = update_preview(existing, holdings)

        self.assertFalse(changed)
        self.assertEqual(updated, existing)

    def test_reentry_clears_exit_state(self) -> None:
        existing = {
            "as_of": "20260501",
            "first_date": "20260501",
            "current": [{"date": "20260501", "code": "2317", "name": "鴻海", "weight": 90.0}],
            "series": {
                "2330": [{"date": "20260430", "weight": 80.0}],
                "2317": [{"date": "20260501", "weight": 90.0}],
            },
            "exited_codes": ["2330"],
            "exit_date": {"2330": "20260501"},
            "active_days": {},
            "name_of": {},
        }
        holdings = [
            Holding(date="20260504", code="2330", name="台積電", weight=70.0),
            Holding(date="20260504", code="2317", name="鴻海", weight=20.0),
        ]

        updated, changed = update_preview(existing, holdings)

        self.assertTrue(changed)
        self.assertNotIn("2330", updated["exited_codes"])
        self.assertNotIn("2330", updated["exit_date"])


if __name__ == "__main__":
    unittest.main()


class PriceUpdaterTests(unittest.TestCase):
    def test_extracts_all_holding_codes(self) -> None:
        holdings = {
            "current": [{"code": "2330"}, {"code": "C_NTD"}, {"code": "TSLA US"}],
            "series": {"2383": [], "0050": []},
            "exited_codes": ["8069"],
        }

        self.assertEqual(extract_holding_codes(holdings), ["0050", "2330", "2383", "8069", "TSLA US"])

    def test_merge_prices_dedupes_and_overwrites_by_date(self) -> None:
        existing = [
            {"date": "20260501", "open": 10, "high": 11, "low": 9, "close": 10.5, "adj_factor": 1, "volume_shares": 100}
        ]
        incoming = [
            {"date": "20260501", "open": 20, "high": 21, "low": 19, "close": 20.5, "adj_factor": 1, "volume_shares": 200},
            {"date": "20260502", "open": 22, "high": 23, "low": 21, "close": 22.5, "adj_factor": 1, "volume_shares": 300},
        ]

        merged = merge_prices(existing, incoming)

        self.assertEqual([row["date"] for row in merged], ["20260501", "20260502"])
        self.assertEqual(merged[0]["open"], 20.0)
        self.assertEqual(merged[0]["volume_shares"], 200)

    def test_update_price_store_keeps_exited_codes_and_fetches_missing_only(self) -> None:
        holdings = {
            "as_of": "20260504",
            "first_date": "20260501",
            "current": [{"code": "2330"}],
            "series": {"2330": [], "2383": [], "TSLA US": []},
            "exited_codes": ["8069"],
        }
        existing = {
            "as_of": "20260501",
            "first_date": "20260501",
            "codes": ["8069"],
            "prices": {
                "8069": [
                    {"date": "20260501", "open": 10, "high": 11, "low": 9, "close": 10.5, "adj_factor": 1, "volume_shares": 100}
                ]
            },
        }
        calls = []

        def fetcher(code, start, end):
            calls.append((code, start, end))
            return [
                {"date": "20260504", "open": 20, "high": 21, "low": 19, "close": 20.5, "adj_factor": 1, "volume_shares": 200}
            ]

        updated, stats = update_price_store(existing, holdings, fetcher)

        self.assertEqual(updated["codes"], ["2330", "2383", "8069", "TSLA US"])
        self.assertIn(("8069", "20260502", "20260504"), calls)
        self.assertIn(("2330", "20260501", "20260504"), calls)
        self.assertNotIn(("TSLA US", "20260501", "20260504"), calls)
        self.assertEqual(stats.new_codes, 3)
        self.assertEqual(stats.added_price_rows, 3)
