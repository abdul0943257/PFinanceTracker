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
from decimal import Decimal
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import linprog


# Import data files.
DATA_FILE = Path(__file__).with_name("finance_data.json")
OUTPUT = Path(__file__).with_name("finance_exports")

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