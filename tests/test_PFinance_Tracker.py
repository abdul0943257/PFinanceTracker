import unittest
from decimal import Decimal
from pathlib import Path
import tempfile

import PFinance_Tracker as finance


class FinanceTests(unittest.TestCase):
    def test_linear_trend_and_rmse(self):
        data = finance.default_data()
        for month, amount in (("2026-07", "100"), ("2026-08", "200"),
                              ("2026-09", "300")):
            data["transactions"].append(finance.transaction(
                month + "-15", "Housing", amount, "expense"
            ))
        months, totals, fitted, prediction, rmse = finance.expense_trend(
            data, "2026-07", "2026-09"
        )
        self.assertEqual(totals, [Decimal("100.00"), Decimal("200.00"), Decimal("300.00")])
        self.assertEqual(prediction, Decimal("400.00"))
        self.assertEqual(rmse, Decimal("0.00"))

    def test_savings_matches_analytical_solution(self):
        balance = Decimal("1000")
        contribution = Decimal("100")
        rate = Decimal("0.06")
        schedule = finance.savings(balance, contribution, rate, 60)
        final_analytical = finance.analytical_balance(
            balance, contribution, rate, 60
        )
        self.assertLessEqual(abs(schedule[-1] - final_analytical), Decimal("0.01"))

    def test_bisection_rounds_up_to_target(self):
        required = finance.find_monthly_contribution(
            Decimal("1000"), Decimal("20000"), Decimal("0.05"), 60
        )
        actual = finance.analytical_balance(
            Decimal("1000"), required, Decimal("0.05"), 60
        )
        self.assertGreaterEqual(actual, Decimal("20000"))

    def test_zero_volatility_is_deterministic(self):
        first = finance.monte_carlo_wealth(
            Decimal("1000"), Decimal("0.12"), Decimal("0"),
            Decimal("100"), years=5, simulations=20, seed=7
        )
        second = finance.monte_carlo_wealth(
            Decimal("1000"), Decimal("0.12"), Decimal("0"),
            Decimal("100"), years=5, simulations=20, seed=99
        )
        self.assertEqual(first["p10"], first["p90"])
        self.assertEqual(first["median"], second["median"])

    def test_csv_export_and_persistence(self):
        data = finance.default_data("USD")
        data["transactions"].append(finance.transaction(
            "2026-11-01", "Food", "42.50", "expense"
        ))
        with tempfile.TemporaryDirectory() as directory:
            path = finance.export_month_csv(
                data, "2026-11", Path(directory)
            )
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8")
            self.assertIn("42.50", text)


if __name__ == "__main__":
    unittest.main()
