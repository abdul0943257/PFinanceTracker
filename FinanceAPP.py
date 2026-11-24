"""Desktop interface for the personal finance tracker. Run: python FinanceAPP.py."""
import copy
import json
import tkinter as tk
from datetime import date
from decimal import Decimal
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import PFinanceTracker as finance


class FinanceApp(ttk.Frame):
    def __init__(self, root):
        super().__init__(root, padding=18)
        self.root = root
        root.title("Personal Finance Tracker")
        root.geometry("1100x760")
        root.minsize(900, 650)
        self.pack(fill="both", expand=True)
        self.data = self.load_data()
        self.category_dropdowns = []
        self.status = tk.StringVar(value="Ready. Your data stays on this computer.")
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="Personal Finance Tracker", font=("Segoe UI", 20, "bold")).pack(side="left")
        self.currency = tk.StringVar(value=self.data["currency"])
        ttk.Button(header, text="Save currency", command=self.guard(self.set_currency)).pack(side="right")
        ttk.Entry(header, textvariable=self.currency, width=8).pack(side="right", padx=8)
        ttk.Label(header, text="Currency:").pack(side="right")
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)
        self.build_transactions()
        self.build_summary()
        self.build_trend()
        self.build_savings()
        self.build_simulation()
        self.build_allocation()
        ttk.Label(self, textvariable=self.status, wraplength=1000).pack(anchor="w", pady=(12, 0))
        self.refresh()

    def load_data(self):
        if not finance.DATA_FILE.exists():
            return dict(currency="USD", transactions=[], budgets={})
        data = json.loads(finance.DATA_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("currency"), str) or not data["currency"].strip():
            raise ValueError("Saved data must contain a currency label.")
        if not isinstance(data.get("transactions"), list) or not isinstance(data.get("budgets"), dict):
            raise ValueError("Saved transactions or budgets have an invalid format.")
        for item in data["transactions"]:
            finance.transaction(item["date"], item["category"], item["amount"], item["type"])
        for month, categories in data["budgets"].items():
            date.fromisoformat(month + "-01")
            for amount in categories.values():
                finance.money(amount)
        return data

    def guard(self, action):
        def run():
            try:
                action()
            except (ValueError, ArithmeticError, OSError, KeyError, TypeError) as error:
                messagebox.showerror("Check your input", str(error), parent=self.root)
        return run

    def tab(self, title):
        frame = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(frame, text=title)
        return frame

    def fields(self, parent, specs):
        form = ttk.Frame(parent)
        form.pack(fill="x", pady=(0, 12))
        values = {}
        for row, (label, default) in enumerate(specs):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=4)
            value = tk.StringVar(value=default)
            if label == "Category":
                field = ttk.Combobox(form, textvariable=value, width=26,
                                     values=self.category_choices())
                self.category_dropdowns.append(field)
            else:
                field = ttk.Entry(form, textvariable=value, width=28)
            field.grid(row=row, column=1, sticky="w", pady=4)
            values[label] = value
        return values

    def category_choices(self):
        categories = {"Food", "Housing", "Transport", "Utilities", "Healthcare",
                      "Education", "Entertainment", "Shopping", "Savings",
                      "Salary", "Freelance", "Investments", "Gifts", "Other"}
        categories.update(item["category"] for item in self.data["transactions"])
        for budgets in self.data["budgets"].values():
            categories.update(budgets)
        return sorted(categories, key=str.casefold)

    def button(self, parent, label, action):
        ttk.Button(parent, text=label, command=self.guard(action)).pack(anchor="w", pady=(0, 12))

    def table(self, parent, columns):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        table = ttk.Treeview(frame, columns=columns, show="headings", height=8)
        for column in columns:
            table.heading(column, text=column)
            table.column(column, width=130, minwidth=80)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        table.pack(fill="both", expand=True)
        return table

    def commit(self, data):
        finance.save(data)
        self.data = data
        self.refresh()

    def set_currency(self):
        currency = self.currency.get().strip()
        if not currency:
            raise ValueError("Enter a currency label, such as USD or KES.")
        data = copy.deepcopy(self.data)
        data["currency"] = currency
        self.commit(data)
        self.status.set("Currency label saved. Existing amounts are not converted.")

    def build_transactions(self):
        tab = self.tab("Transactions")
        self.entry = self.fields(tab, [("Date (YYYY-MM-DD)", date.today().isoformat()), ("Category", ""), ("Amount", "")])
        self.kind = tk.StringVar(value="expense")
        ttk.Combobox(tab, textvariable=self.kind, values=("expense", "income"), state="readonly", width=25).pack(anchor="w", pady=(0, 10))
        self.button(tab, "Add transaction", self.add_transaction)
        self.button(tab, "Import CSV…", self.import_csv)
        ttk.Label(tab, text="CSV columns: date, category, amount, type. Importing the same file again adds duplicates.").pack(anchor="w", pady=(0, 8))
        self.transactions = self.table(tab, ("Date", "Category", "Type", "Amount"))

    def add_transaction(self):
        item = finance.transaction(self.entry["Date (YYYY-MM-DD)"].get().strip(), self.entry["Category"].get(), self.entry["Amount"].get().strip(), self.kind.get())
        data = copy.deepcopy(self.data)
        data["transactions"].append(item)
        self.commit(data)
        self.entry["Amount"].set("")
        self.status.set("Transaction saved.")

    def import_csv(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            data = copy.deepcopy(self.data)
            count = finance.import_csv(path, data)
            self.commit(data)
            self.status.set(f"Imported and saved {count} transactions.")

    def build_summary(self):
        tab = self.tab("Summary & budgets")
        self.month = self.fields(tab, [("Month (YYYY-MM)", date.today().strftime("%Y-%m"))])["Month (YYYY-MM)"]
        self.button(tab, "Refresh summary", self.refresh_summary)
        self.totals = tk.StringVar()
        ttk.Label(tab, textvariable=self.totals, font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 12))
        self.budget = self.fields(tab, [("Category", ""), ("Budget", "")])
        self.button(tab, "Save category budget for this month", self.set_budget)
        self.button(tab, "Export monthly summary CSV", self.export_summary)
        self.categories = self.table(tab, ("Category", "Expenses", "Budget", "Status"))

    def set_budget(self):
        month = self.month.get().strip()
        date.fromisoformat(month + "-01")
        category = self.budget["Category"].get().strip()
        if not category:
            raise ValueError("Enter a category.")
        amount = finance.money(self.budget["Budget"].get().strip())
        data = copy.deepcopy(self.data)
        data["budgets"].setdefault(month, {})[category] = str(amount)
        self.commit(data)
        self.status.set("Category budget saved.")

    def export_summary(self):
        path = finance.export_month_csv(self.data, self.month.get().strip())
        self.status.set(f"Report saved to {path}")

    def refresh(self):
        choices = self.category_choices()
        for dropdown in self.category_dropdowns:
            dropdown.configure(values=choices)
        self.transactions.delete(*self.transactions.get_children())
        for item in sorted(self.data["transactions"], key=lambda item: item["date"], reverse=True):
            self.transactions.insert("", "end", values=(item["date"], item["category"], item["type"], f'{Decimal(item["amount"]):,.2f}'))
        # A user may be editing the month while saving a transaction.
        try:
            self.refresh_summary()
        except ValueError:
            self.totals.set("Enter a valid month and refresh the summary.")
            self.categories.delete(*self.categories.get_children())

    def refresh_summary(self):
        month = self.month.get().strip()
        income, expenses, net, categories = finance.summary(self.data, month)
        self.totals.set(f'{self.data["currency"]}   Income: {income:,.2f}   Expenses: {expenses:,.2f}   Net: {net:,.2f}')
        self.categories.delete(*self.categories.get_children())
        budgets = self.data["budgets"].get(month, {})
        for category in sorted(set(categories) | set(budgets)):
            spent = categories.get(category, Decimal("0"))
            limit = finance.money(budgets[category]) if category in budgets else None
            self.categories.insert("", "end", values=(category, f"{spent:,.2f}", "—" if limit is None else f"{limit:,.2f}", "Over budget" if limit is not None and spent > limit else ""))

    def chart_area(self, tab):
        area = ttk.Frame(tab)
        area.pack(fill="both", expand=True)
        return area

    def chart(self, area, title, xlabel, ylabel):
        for child in area.winfo_children():
            child.destroy()
        figure = Figure(figsize=(7, 3), dpi=100, layout="constrained")
        axes = figure.add_subplot()
        axes.set(title=title, xlabel=xlabel, ylabel=ylabel)
        canvas = FigureCanvasTkAgg(figure, master=area)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        return axes, canvas

    def build_trend(self):
        tab = self.tab("Expense trend")
        ttk.Label(tab, text="Enter at least three consecutive completed months. Include all transactions before forecasting.").pack(anchor="w", pady=(0, 12))
        self.trend = self.fields(tab, [("First month (YYYY-MM)", ""), ("Last month (YYYY-MM)", "")])
        self.button(tab, "Calculate trend", self.calculate_trend)
        self.trend_result = tk.StringVar()
        ttk.Label(tab, textvariable=self.trend_result).pack(anchor="w")
        self.trend_chart = self.chart_area(tab)

    def calculate_trend(self):
        months, totals, fitted, prediction, rmse = finance.expense_trend(self.data, *(v.get().strip() for v in self.trend.values()))
        forecast = finance.next_month(months[-1])
        self.trend_result.set(f"Projected expenses for {forecast}: {prediction:,.2f} {self.data['currency']} | RMSE: {rmse:,.2f}")
        axes, canvas = self.chart(self.trend_chart, "Monthly expense trend", "Month", self.data["currency"])
        axes.plot(months, totals, "o-", label="Actual")
        axes.plot(months + [forecast], list(fitted) + [prediction], "--", label="Trend / forecast")
        axes.tick_params(axis="x", rotation=25)
        axes.legend()
        canvas.draw()

    def build_savings(self):
        tab = self.tab("Savings target")
        self.saving = self.fields(tab, [("Initial balance", "0"), ("Target balance", "10000"), ("Annual interest (%)", "5"), ("Months", "60")])
        self.button(tab, "Calculate monthly contribution", self.calculate_savings)
        self.savings_result = tk.StringVar()
        ttk.Label(tab, textvariable=self.savings_result).pack(anchor="w")
        self.savings_chart = self.chart_area(tab)

    def calculate_savings(self):
        balance = finance.money(self.saving["Initial balance"].get())
        target = finance.money(self.saving["Target balance"].get())
        rate = finance.decimal_value(self.saving["Annual interest (%)"].get()) / 100
        months = int(self.saving["Months"].get())
        if months < 1 or months > 1200 or rate <= -1:
            raise ValueError("Use 1–1200 months and an annual interest rate greater than -100%.")
        deposit, _, _ = finance.required_contribution(balance, target, rate, months)
        schedule = finance.savings(balance, finance.money(deposit), rate, months)
        self.savings_result.set(f"Monthly contribution: {deposit:,.2f} {self.data['currency']} | Final balance: {schedule[-1]:,.2f}")
        axes, canvas = self.chart(self.savings_chart, "Savings schedule", "Month", self.data["currency"])
        axes.plot(range(months + 1), [float(v) for v in schedule])
        canvas.draw()

    def build_simulation(self):
        tab = self.tab("Monte Carlo")
        ttk.Label(tab, text="Five-year simulation • 1,000 paths • normally distributed monthly returns").pack(anchor="w", pady=(0, 12))
        self.sim = self.fields(tab, [("Initial balance", "1000"), ("Monthly deposit", "100"), ("Expected annual return (%)", "7"), ("Annual volatility (%)", "15")])
        self.button(tab, "Run simulation", self.calculate_simulation)
        self.sim_result = tk.StringVar()
        ttk.Label(tab, textvariable=self.sim_result).pack(anchor="w")
        self.sim_chart = self.chart_area(tab)

    def calculate_simulation(self):
        balance, deposit, annual_return, volatility = [float(finance.decimal_value(v.get())) for v in self.sim.values()]
        bands = finance.monte_carlo(balance, deposit, annual_return / 100, volatility / 100)
        self.sim_result.set(f"Final balances ({self.data['currency']}): 5th {bands[0,-1]:,.2f} | Median {bands[1,-1]:,.2f} | 95th {bands[2,-1]:,.2f}")
        axes, canvas = self.chart(self.sim_chart, "Simulated wealth", "Month", self.data["currency"])
        axes.fill_between(range(61), bands[0], bands[2], alpha=0.25, label="5th–95th percentiles")
        axes.plot(range(61), bands[1], label="Median")
        axes.legend()
        canvas.draw()

    def build_allocation(self):
        tab = self.tab("Allocation")
        self.alloc = self.fields(tab, [("Investment amount", "10000"), ("Maximum weighted risk", "0.5"), ("Minimum cash reserve", "1000")])
        grid = ttk.Frame(tab)
        grid.pack(anchor="w", pady=(0, 14))
        for col, label in enumerate(("Asset", "Return (%)", "Risk score", "Maximum (%)")):
            ttk.Label(grid, text=label).grid(row=0, column=col, padx=8, pady=6)
        self.assets = []
        for row, (asset, defaults) in enumerate((("Cash", (2, 0, 100)), ("Bonds", (4, 0.3, 100)), ("Stocks", (8, 0.8, 60))), 1):
            ttk.Label(grid, text=asset).grid(row=row, column=0, sticky="w", padx=8)
            values = []
            for col, value in enumerate(defaults, 1):
                variable = tk.StringVar(value=str(value))
                ttk.Entry(grid, textvariable=variable, width=16).grid(row=row, column=col, padx=8, pady=4)
                values.append(variable)
            self.assets.append(values)
        self.button(tab, "Optimize allocation", self.calculate_allocation)
        self.allocation_result = tk.StringVar()
        ttk.Label(tab, textvariable=self.allocation_result, font=("Segoe UI", 13), justify="left").pack(anchor="w", pady=12)

    def calculate_allocation(self):
        amount, risk, reserve = [float(finance.decimal_value(v.get())) for v in self.alloc.values()]
        rows = [[float(finance.decimal_value(v.get())) for v in row] for row in self.assets]
        result = finance.optimize_allocation(amount, [r[0] / 100 for r in rows], [r[1] for r in rows], [r[2] / 100 for r in rows], risk, reserve)
        self.allocation_result.set("\n".join(f"{asset}: {value:,.2f} {self.data['currency']} ({value / amount:.1%})" for asset, value in zip(("Cash", "Bonds", "Stocks"), result)))


def main():
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TLabel", font=("Segoe UI", 10))
    style.configure("TButton", padding=6)
    try:
        FinanceApp(root)
    except (ValueError, ArithmeticError, OSError, KeyError, TypeError) as error:
        root.withdraw()
        messagebox.showerror("Unable to open tracker", f"Could not load finance_data.json:\n{error}\n\nYour saved file has not been changed.", parent=root)
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
