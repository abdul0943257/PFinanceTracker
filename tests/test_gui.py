"""Integration checks for desktop actions, using isolated saved data."""
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

import FinanceAPP as gui


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "finance_data.json"
        self.data_patch = patch.object(gui.finance, "DATA_FILE", self.path)
        self.data_patch.start()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = gui.FinanceApp(self.root)
        self.root.update_idletasks()

    def tearDown(self):
        self.root.destroy()
        self.data_patch.stop()
        self.directory.cleanup()

    def test_load_saved_dates_and_open_calendars(self):
        self.path.write_text(json.dumps(dict(
            currency="USD",
            transactions=[dict(date="2026-7-5", category="Food", amount="20", type="expense")],
            budgets={"2026-7": {"Food": "40"}},
        )), encoding="utf-8")
        loaded = self.app.load_data()
        self.assertEqual(loaded["transactions"][0]["date"], "2026-07-05")
        self.assertEqual(loaded["budgets"], {"2026-07": {"Food": "40"}})
        for value, month_only in (("2026-07-05", False), ("2026-07", True)):
            picker = gui.DatePicker(self.root, tk.StringVar(master=self.root, value=value), month_only)
            picker.open_calendar()
            self.assertEqual((picker.year, picker.month), (2026, 7))
            picker.popup.destroy()
            picker.destroy()
        for month_only in (False, True):
            variable = tk.StringVar(master=self.root, value="invalid")
            picker = gui.DatePicker(self.root, variable, month_only)
            picker.open_calendar()
            today = gui.date.today()
            self.assertEqual((picker.year, picker.month), (today.year, today.month))
            self.assertEqual(variable.get(), "invalid")
            picker.move_month(-1)
            picker.select_date(gui.date(2026, 7, 5))
            self.assertEqual(variable.get(), "2026-07" if month_only else "2026-07-05")
            picker.destroy()
        for invalid in ("2026-02-30", "invalid"):
            with self.assertRaises(ValueError):
                gui.finance.normalize_date(invalid)
        with self.assertRaises(ValueError):
            gui.finance.normalize_month("2026-13")

    def test_transaction_budget_and_reload(self):
        self.app.entry["Date (YYYY-MM-DD)"].set("2026-07-15")
        self.app.entry["Category"].set("Food")
        self.app.entry["Amount"].set("42.50")
        self.app.add_transaction()
        self.app.month.set("2026-07")
        self.app.budget["Category"].set("Food")
        self.app.budget["Budget"].set("40")
        self.app.set_budget()
        self.assertIn("42.50", self.app.totals.get())
        row = self.app.categories.item(self.app.categories.get_children()[0])["values"]
        self.assertEqual(row[-1], "Over budget")
        self.assertEqual(self.app.load_data(), json.loads(self.path.read_text()))
        self.app.entry["Amount"].set("-1")
        with self.assertRaises(ValueError):
            self.app.add_transaction()
        self.assertEqual(len(self.app.data["transactions"]), 1)

    def test_edit_sorted_transaction_and_reject_invalid_update(self):
        self.app.data["transactions"] = [
            gui.finance.transaction("2026-07-01", "Food", "10", "expense"),
            gui.finance.transaction("2026-08-01", "Salary", "100", "income"),
        ]
        self.app.refresh()
        self.assertEqual(self.app.transactions.get_children()[0], "1")
        self.app.transactions.selection_set("1")
        self.app.edit_transaction()
        self.assertEqual(self.app.entry["Category"].get(), "Salary")
        self.app.entry["Amount"].set("-1")
        with self.assertRaises(ValueError):
            self.app.update_transaction()
        self.assertEqual(self.app.data["transactions"][1]["amount"], "100")
        self.assertEqual(self.app.editing_index, 1)
        self.app.entry["Amount"].set("25.50")
        self.app.entry["Category"].set("Transport")
        self.app.entry["Date (YYYY-MM-DD)"].set("2026-07-02")
        self.app.kind.set("expense")
        self.app.month.set("2026-07")
        self.app.update_transaction()
        saved = json.loads(self.path.read_text())
        self.assertEqual(len(saved["transactions"]), 2)
        self.assertEqual(saved["transactions"][0]["amount"], "10")
        self.assertEqual(saved["transactions"][1], gui.finance.transaction("2026-07-02", "Transport", "25.50", "expense"))
        self.assertIn("35.50", self.app.totals.get())
        self.assertIsNone(self.app.editing_index)
        self.app.transactions.selection_set("0")
        self.app.edit_transaction()
        self.app.entry["Amount"].set("999")
        self.app.cancel_edit()
        self.assertEqual(self.app.load_data(), saved)

    def test_calculations_render_charts(self):
        self.app.data["transactions"] = [gui.finance.transaction(f"2026-{month:02}-15", "Food", str(amount), "expense") for month, amount in ((7, 100), (8, 200), (9, 300))]
        for variable, value in zip(self.app.trend.values(), ("2026-07", "2026-09")):
            variable.set(value)
        self.app.calculate_trend()
        self.assertIn("400.00", self.app.trend_result.get())
        self.app.calculate_savings()
        self.assertIn("10,000", self.app.savings_result.get())
        self.app.calculate_simulation()
        self.assertIn("Median", self.app.sim_result.get())
        self.app.calculate_allocation()
        self.assertIn("Stocks:", self.app.allocation_result.get())
        self.root.update_idletasks()
        for area in (self.app.trend_chart, self.app.savings_chart, self.app.sim_chart):
            self.assertEqual(len(area.winfo_children()), 2)
            button = next(child for child in area.winfo_children() if isinstance(child, gui.ttk.Button))
            path = Path(self.directory.name) / f"chart-{str(area).split('.')[-1]}.png"
            with patch.object(gui.filedialog, "asksaveasfilename", return_value=str(path)):
                button.invoke()
            self.assertTrue(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        with patch.object(gui.filedialog, "asksaveasfilename", return_value=""):
            with patch.object(gui.Figure, "savefig") as save:
                button.invoke()
                save.assert_not_called()

    def test_invalid_csv_does_not_partially_import(self):
        path = Path(self.directory.name) / "import.csv"
        path.write_text("date,category,amount,type\n2026-07-01,Food,20,expense\n2026-07-02,Food,-5,expense\n")
        with patch.object(gui.filedialog, "askopenfilename", return_value=str(path)):
            with self.assertRaises(ValueError):
                self.app.import_csv()
        self.assertEqual(self.app.data["transactions"], [])
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
