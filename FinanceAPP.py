"""
Display the application in GUI
"""
# Import tools for files, dates, calculations, and charts.
import csv
import json
import math
from datetime import date
from decimal import Decimal
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import linprog

DATA_FILE = Path(__file__).with_name("finance_data.json")
OUTPUT = Path(__file__).with_name("finance_exports")


# Keep money as decimal values to avoid rounding errors in summaries.
def money(value):
    value = Decimal(str(value))
    if not value.is_finite() or value < 0 or value != value.quantize(Decimal("0.01")):
        raise ValueError("Enter a positive amount with at most two decimal places.")
    return value


# Check each transaction before saving it.
def transaction(day, category, amount, kind):
    date.fromisoformat(day)
    if not category.strip() or kind not in ("income", "expense"):
        raise ValueError("Enter a category and use income or expense as the type.")
    return dict(date=day, category=category.strip(), amount=str(money(amount)), type=kind)


# Save all entries in a local file that stays available after closing.
def save(data):
    temporary = DATA_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(DATA_FILE)


# Add up income and expenses for one month.
def summary(data, month):
    date.fromisoformat(month + "-01")
    income = Decimal("0")
    expenses = Decimal("0")
    categories = {}
    for item in data["transactions"]:
        if item["date"][:7] != month:
            continue
        amount = money(item["amount"])
        if item["type"] == "income":
            income += amount
        else:
            expenses += amount
            category = item["category"]
            categories[category] = categories.get(category, Decimal("0")) + amount
    return income, expenses, income - expenses, categories


# Work out the next calendar month.
def next_month(month):
    year, number = map(int, month.split("-"))
    return f"{year + (number == 12):04d}-{number % 12 + 1:02d}"


# Fit a straight line to consecutive, completed months.
def expense_trend(data, start, end):
    today_month = date.today().strftime("%Y-%m")
    date.fromisoformat(start + "-01")
    date.fromisoformat(end + "-01")
    if start > end or end >= today_month:
        raise ValueError("Use completed months in date order.")
    months = []
    month = start
    while month <= end:
        months.append(month)
        month = next_month(month)
    if len(months) < 3:
        raise ValueError("At least three consecutive complete months are required.")
    totals = np.array([float(summary(data, m)[1]) for m in months])
    x = np.arange(len(months))
    slope, intercept = np.polyfit(x, totals, 1)
    fitted = slope * x + intercept
    prediction = float(slope * len(months) + intercept)
    rmse = float(np.sqrt(np.mean((totals - fitted) ** 2)))
    return months, totals, fitted, prediction, rmse


# Add interest first, then add the monthly deposit.
def savings(balance, contribution, annual_rate, months):
    if balance < 0 or contribution < 0 or annual_rate <= -1 or months < 1:
        raise ValueError("Check the balance, deposit, rate, and number of months.")
    rate = annual_rate / 12
    balances = [balance]
    for _ in range(months):
        balances.append(balances[-1] * (1 + rate) + contribution)
    return balances


# Use the compound-interest formula to check the monthly simulation.
def analytical_balance(balance, contribution, annual_rate, months):
    rate = annual_rate / 12
    if rate == 0:
        return balance + contribution * months
    growth = (1 + rate) ** months
    return balance * growth + contribution * (growth - 1) / rate


# Narrow the deposit range until it is no wider than one cent.
def required_contribution(balance, target, annual_rate, months):
    if target < 0:
        raise ValueError("The target cannot be negative.")
    if savings(balance, 0, annual_rate, months)[-1] >= target:
        return 0.0, 0, 0.0
    low = 0.0
    high = max(1.0, target)
    if savings(balance, high, annual_rate, months)[-1] < target:
        raise ValueError("Could not bracket the target.")
    iterations = 0
    while high - low > 0.01 and iterations < 50:
        middle = (low + high) / 2
        if savings(balance, middle, annual_rate, months)[-1] >= target:
            high = middle
        else:
            low = middle
        iterations += 1
    if high - low > 0.01:
        raise ValueError("The search did not converge within 50 iterations.")
    contribution = math.ceil(high * 100) / 100
    return contribution, iterations, high - low


# Simulate five years using normally distributed monthly returns.
def monte_carlo(balance, contribution, annual_return, volatility, runs=1000, seed=None):
    if runs < 1000 or volatility < 0 or balance < 0 or contribution < 0:
        raise ValueError("Use at least 1,000 runs and nonnegative amounts and volatility.")
    rng = np.random.default_rng(seed)
    paths = np.empty((runs, 61))
    paths[:, 0] = balance
    for month in range(60):
        returns = rng.normal(annual_return / 12, volatility / np.sqrt(12), runs)
        # Limit losses to the amount invested; deposits arrive at month end.
        paths[:, month + 1] = paths[:, month] * np.maximum(0, 1 + returns) + contribution
    return np.percentile(paths, [5, 50, 95], axis=0)


# Maximize expected return while keeping cash and risk within limits.
def optimize_allocation(amount, returns, risks, caps, risk_limit, cash_minimum):
    if amount <= 0 or not 0 <= cash_minimum <= amount or risk_limit < 0:
        raise ValueError("Check the investment amount, cash reserve, and risk limit.")
    if not (len(returns) == len(risks) == len(caps) == 3):
        raise ValueError("Provide three values: cash, bonds, and stocks.")
    if any(r < 0 for r in risks) or any(not 0 <= c <= 1 for c in caps):
        raise ValueError("Risks must be nonnegative and caps must be between 0 and 1.")
    result = linprog(
        -np.array(returns),
        A_ub=[risks], b_ub=[risk_limit * amount],
        A_eq=[[1, 1, 1]], b_eq=[amount],
        bounds=[(cash_minimum, caps[0] * amount), (0, caps[1] * amount),
                (0, caps[2] * amount)], method="highs",
    )
    if not result.success:
        raise ValueError("These constraints have no feasible allocation.")
    return result.x


# Write readable tables to CSV files.
def write_csv(name, header, rows):
    OUTPUT.mkdir(exist_ok=True)
    with (OUTPUT / name).open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)


# Label each chart and save it as a PNG image.
def finish_chart(name, title, xlabel, ylabel):
    OUTPUT.mkdir(exist_ok=True)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(OUTPUT / name)
    plt.close()


# Read a finite number from the keyboard.
def number(prompt):
    value = float(input(prompt))
    if not math.isfinite(value):
        raise ValueError("Enter a finite number.")
    return value


# Run the main menu until the user chooses to quit.
def main():
    if DATA_FILE.exists():
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    else:
        currency = input("Currency label (for example USD or KES): ").strip()
        if not currency:
            raise ValueError("A currency label is required.")
        data = dict(currency=currency, transactions=[], budgets={})
        save(data)
    currency = data["currency"]
    while True:
        print("\n1 Add transaction | 2 Import CSV | 3 Set budget | 4 Monthly summary")
        print("5 Expense trend | 6 Savings target | 7 Monte Carlo | 8 Allocation | 0 Quit")
        choice = input("Choose: ").strip()
        try:
            if choice == "0":
                break
            elif choice == "1":
                item = transaction(input("Date YYYY-MM-DD: "), input("Category: "),
                                   input("Amount: "), input("Type (income/expense): "))
                data["transactions"].append(item)
                save(data)
            elif choice == "2":
                # Validate the whole import before adding any rows.
                with open(input("CSV path: "), newline="", encoding="utf-8-sig") as file:
                    rows = [transaction(r["date"], r["category"], r["amount"], r["type"])
                            for r in csv.DictReader(file)]
                data["transactions"].extend(rows)
                save(data)
                print(f"Imported {len(rows)} transactions. Reimporting adds duplicates.")
            elif choice == "3":
                month = input("Month YYYY-MM: ")
                date.fromisoformat(month + "-01")
                category = input("Category: ").strip()
                if not category:
                    raise ValueError("Enter a category.")
                data["budgets"].setdefault(month, {})[category] = str(money(input("Budget: ")))
                save(data)
            elif choice == "4":
                month = input("Month YYYY-MM: ")
                income, expense, net, categories = summary(data, month)
                print(f"{currency}: Income {income:.2f}, Expenses {expense:.2f}, Net {net:.2f}")
                budgets = data["budgets"].get(month, {})
                for category in sorted(set(categories) | set(budgets)):
                    spent = categories.get(category, Decimal("0"))
                    limit = budgets.get(category)
                    flag = "OVER BUDGET" if limit is not None and spent > money(limit) else ""
                    print(category, f"{spent:.2f}", "Budget:", limit, flag)
                if input("Export summary and chart? y/n: ").lower() == "y":
                    write_csv(f"summary_{month}.csv", ["month", "currency", "income", "expenses", "net"],
                              [[month, currency, income, expense, net]])
                    plt.figure()
                    plt.bar(["Income", "Expenses", "Net"], list(map(float, [income, expense, net])))
                    finish_chart(f"summary_{month}.png", f"Monthly summary: {month}", "Type", currency)
            elif choice == "5":
                print("Confirm that all transactions are entered for the selected months.")
                months, totals, fitted, prediction, rmse = expense_trend(
                    data, input("First complete month YYYY-MM: "), input("Last complete month YYYY-MM: "))
                print(f"Trend projection for {next_month(months[-1])}: {prediction:.2f} {currency}; RMSE {rmse:.2f}")
                plt.figure()
                plt.plot(months, totals, "o-", label="Expenses")
                plt.plot(months + [next_month(months[-1])], list(fitted) + [prediction], "--", label="Trend projection")
                plt.legend()
                finish_chart("expense_trend.png", "Expense trend projection", "Month", currency)
            elif choice == "6":
                balance = number("Initial balance: ")
                target = number("Savings target: ")
                rate = number("Annual interest percent: ") / 100
                months = int(input("Months until deadline (60 for five years): "))
                deposit, iterations, width = required_contribution(balance, target, rate, months)
                balances = savings(balance, deposit, rate, months)
                print(f"Monthly deposit: {deposit:.2f} {currency}; final balance: {balances[-1]:.2f}")
                print(f"Bisection iterations: {iterations}; interval width: {width:.6f}")
                for month, value in enumerate(balances):
                    print(f"Month {month}: {value:.2f}")
                if input("Export schedule and chart? y/n: ").lower() == "y":
                    write_csv("savings.csv", ["month", f"balance_{currency}"], enumerate(balances))
                    plt.figure()
                    plt.plot(range(months + 1), balances)
                    finish_chart("savings.png", "Savings balance schedule", "Month", currency)
            elif choice == "7":
                bands = monte_carlo(number("Initial balance: "), number("Monthly deposit: "),
                                    number("Expected annual return percent: ") / 100,
                                    number("Annual volatility percent: ") / 100)
                print("Final 5th, 50th, 95th percentiles:", np.round(bands[:, -1], 2), currency)
                plt.figure()
                plt.fill_between(range(61), bands[0], bands[2], alpha=0.3, label="5th-95th percentiles")
                plt.plot(range(61), bands[1], label="Median")
                plt.legend()
                finish_chart("monte_carlo.png", "Five-year wealth simulation (1,000 runs)", "Month", currency)
            elif choice == "8":
                amount = number("Amount to allocate: ")
                returns, risks, caps = [], [], []
                for asset in ["Cash", "Bonds", "Stocks"]:
                    print(asset)
                    returns.append(number("Expected annual return percent: ") / 100)
                    risks.append(number("Risk score (0 to 1): "))
                    caps.append(number("Maximum allocation percent: ") / 100)
                risk_limit = number("Maximum weighted risk score: ")
                reserve = number("Minimum cash reserve: ")
                allocation = optimize_allocation(amount, returns, risks, caps, risk_limit, reserve)
                for asset, value in zip(["Cash", "Bonds", "Stocks"], allocation):
                    print(f"{asset}: {value:.2f} {currency}")
            else:
                print("Choose a number from the menu.")
        except (ValueError, ArithmeticError, OSError, KeyError) as error:
            print("Error:", error)


# Start only when this file is run directly.
if __name__ == "__main__":
    main()