"""
My project will be a python-based personal finance tracker 
that helps users record and track their income and expenses. 
It will also compare the spending based on category budgets and help users plan 
their savings. Personal finance tracker uses numerical formulas and compound 
growth equations. The system will combine the transaction summaries, 
offer a spending trend for forecasting and additionally provide a 
saving calculator interface. The scope of the project will be local, 
single-user application that will be using a single currency, that is 
manually selected by the user. It will also support CSV-imported transactions. 
This project was my best choice since it addresses everyday need in this modern word.  
"""
# Import tools for files, dates, calculations, and charts.
import csv
import json
import math
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import linprog


# Import data files.
DATA_FILE = Path(__file__).with_name("finance_data.json")
OUTPUT = Path(__file__).with_name("finance_exports")
ZERO = Decimal("0")


def decimal_value(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("Enter a valid numeric value.") from error

    if not result.is_finite():
        raise ValueError("Enter a finite numeric value.")

    return result

# Validate money amounts and avoid rounding errors.
def money(value):
    value = Decimal(str(value))

    if not value.is_finite() or value < 0 or value != value.quantize(Decimal("0.01")):
        raise ValueError("Enter a positive amount with at most two decimal places.")

    return value

from datetime import date

# Check each transaction before saving.
def transaction(day, category, amount, kind):
    date.fromisoformat(day)

    if not category.strip() or kind not in ("income", "expense"):
        raise ValueError("Enter a category and use income or expense as the type.")

    return dict(
        date=day,
        category=category.strip(),
        amount=str(money(amount)),
        type=kind
    )

# Save transactions and budgets to a JSON file.
def save(data):
    temporary = DATA_FILE.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )

    temporary.replace(DATA_FILE)

# Calculate monthly income, expenses, and net balance.
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

            categories[category] = (
                categories.get(category, Decimal("0")) + amount
            )

    return income, expenses, income - expenses, categories

# Calculate the next calendar month.
def next_month(month):
    year, number = map(int, month.split("-"))

    return f"{year + (number == 12):04d}-{number % 12 + 1:02d}"


# Fit a linear regression model to monthly expenses.
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

    totals = np.array([
        float(summary(data, m)[1]) for m in months
    ])

    x = np.arange(len(months))

    slope, intercept = np.polyfit(x, totals, 1)

    fitted = slope * x + intercept
    prediction = float(slope * len(months) + intercept)

    rmse = float(
        np.sqrt(np.mean((totals - fitted) ** 2))
    )

    return months, totals, fitted, prediction, rmse

# Simulate monthly savings with compound interest.
def savings(balance, contribution, annual_rate, months):
    if balance < 0 or contribution < 0 or annual_rate <= -1 or months < 1:
        raise ValueError("Check the balance, deposit, rate, and number of months.")

    rate = annual_rate / 12
    balances = [balance]

    for _ in range(months):
        balances.append(
            balances[-1] * (1 + rate) + contribution
        )

    return balances

# Calculate the savings balance using the compound-interest formula.
def analytical_balance(balance, contribution, annual_rate, months):
    rate = annual_rate / 12

    if rate == 0:
        return balance + contribution * months

    growth = (1 + rate) ** months

    return balance * growth + contribution * (growth - 1) / rate

# Calculate monthly savings needed using the bisection method.
def required_contribution(balance, target, annual_rate, months):
    # Convert all monetary and rate values to validated Decimal values.
    balance = money(balance)
    target = money(target)
    annual_rate = decimal_value(annual_rate)

    # The target cannot be negative and cannot be lower than the balance.
    if target < ZERO:
        raise ValueError("The target cannot be negative.")
    if target < balance:
        return 0.0, 0, 0.0

    # The annual rate must be greater than -100%, and months must be positive.
    if annual_rate <= Decimal("-1"):
        raise ValueError("Annual rate must be greater than -100%.")
    if isinstance(months, bool) or not isinstance(months, int) or months < 1:
        raise ValueError("Months must be a positive integer.")

    # Search in whole cents to avoid floating-point rounding errors.
    low_cents = 0
    high_cents = max(
        100,
        int((target * 100).to_integral_value(rounding=ROUND_CEILING)),
    )

    # Expand the upper bound until it is large enough to reach the target.
    while savings(
        balance,
        Decimal(high_cents) / 100,
        annual_rate,
        months,
    )[-1] < target:
        high_cents *= 2
        if high_cents > 10_000_000_000:
            raise ValueError("Could not bracket the target.")

    iterations = 0

    # Narrow the range between the smallest and largest feasible amounts.
    while high_cents - low_cents > 1 and iterations < 50:
        middle_cents = (low_cents + high_cents) // 2
        middle_contribution = Decimal(middle_cents) / 100

        if savings(
            balance,
            middle_contribution,
            annual_rate,
            months,
        )[-1] >= target:
            high_cents = middle_cents
        else:
            low_cents = middle_cents

        iterations += 1

    # Stop if the bisection search did not converge within 50 iterations.
    if high_cents - low_cents > 1:
        raise ValueError("The search did not converge within 50 iterations.")

    # Convert cents back to dollars and report the remaining search width.
    contribution = high_cents / 100
    search_width = (high_cents - low_cents) / 100

    return contribution, iterations, search_width

# Simulate five years of investment growth using random returns.
def monte_carlo(balance, contribution, annual_return, volatility, runs=1000, seed=None):
    # Validate the model inputs before running the simulations.
    if (
        isinstance(runs, bool)
        or not isinstance(runs, int)
        or runs < 1000
    ):
        raise ValueError("Runs must be an integer of at least 1,000.")

    if (
        not np.isfinite(balance)
        or not np.isfinite(contribution)
        or not np.isfinite(annual_return)
        or not np.isfinite(volatility)
    ):
        raise ValueError("All numeric values must be finite.")

    if balance < 0 or contribution < 0:
        raise ValueError("Balance and contribution cannot be negative.")

    if volatility < 0:
        raise ValueError("Volatility cannot be negative.")

    # Use a dedicated random-number generator for reproducible results.
    rng = np.random.default_rng(seed)

    # Each row represents one simulation; there are 61 points for 60 months
    # plus the starting balance at month zero.
    paths = np.empty((runs, 61), dtype=float)
    paths[:, 0] = balance

    monthly_mean = annual_return / 12
    monthly_volatility = volatility / np.sqrt(12)

    # Simulate five years of monthly investment growth.
    for month in range(60):
        monthly_returns = rng.normal(
            monthly_mean,
            monthly_volatility,
            size=runs,
        )

        # Limit each month's loss to 100% of the invested balance.
        paths[:, month + 1] = (
            paths[:, month] * np.maximum(0.0, 1.0 + monthly_returns)
            + contribution
        )

    # Return the 5th, 50th, and 95th percentiles across all simulations.
    return np.percentile(paths, [5, 50, 95], axis=0)

# Optimize investment allocation using linear programming.
def optimize_allocation(amount, returns, risks, caps, risk_limit, cash_minimum):
    # Validate the overall investment amount and risk settings.
    if not np.isfinite(amount) or amount <= 0:
        raise ValueError("Investment amount must be a positive finite number.")

    if not np.isfinite(cash_minimum) or not 0 <= cash_minimum <= amount:
        raise ValueError("Cash reserve must be between zero and the investment amount.")

    if not np.isfinite(risk_limit) or risk_limit < 0:
        raise ValueError("Risk limit must be a nonnegative finite number.")

    # Cash, bonds, and stocks must each provide a return, risk, and cap.
    if not (
        len(returns) == len(risks)
        and len(risks) == len(caps)
        and len(caps) == 3
    ):
        raise ValueError("Provide three values: cash, bonds, and stocks.")

    # Convert inputs to arrays and reject invalid or nonfinite values.
    returns = np.asarray(returns, dtype=float)
    risks = np.asarray(risks, dtype=float)
    caps = np.asarray(caps, dtype=float)

    if not (
        np.all(np.isfinite(returns))
        and np.all(np.isfinite(risks))
        and np.all(np.isfinite(caps))
    ):
        raise ValueError("Returns, risks, and caps must contain finite numbers.")

    if np.any(risks < 0):
        raise ValueError("Risk values must be nonnegative.")

    if np.any((caps < 0) | (caps > 1)):
        raise ValueError("Allocation caps must be between 0 and 1.")

    # Convert maximum fractions into dollar-based upper bounds.
    bounds = [
        (cash_minimum, caps[0] * amount),
        (0, caps[1] * amount),
        (0, caps[2] * amount),
    ]

    # Minimize negative expected return, which is equivalent to maximizing return.
    result = linprog(
        c=-returns,
        A_ub=[risks],
        b_ub=[risk_limit * amount],
        A_eq=np.ones((1, 3)),
        b_eq=[amount],
        bounds=bounds,
        method="highs",
    )

    # Return an allocation only when all constraints have been satisfied.
    if not result.success:
        raise ValueError("No allocation satisfies the investment constraints.")

    allocation = result.x

    # Guard against tiny solver rounding while avoiding a silent infeasible result.
    if not np.isclose(allocation.sum(), amount, rtol=1e-7, atol=1e-7):
        raise ValueError("The solver returned an invalid allocation.")

    return allocation

# Export directory
def write_csv(name, header, rows):
    # Create the export directory if it does not already exist.
    OUTPUT.mkdir(parents=True, exist_ok=True)

    with (OUTPUT / name).open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)
