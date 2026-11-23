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