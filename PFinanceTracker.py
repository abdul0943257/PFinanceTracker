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


from decimal import Decimal

# Validate money amounts and avoid rounding errors.
def money(value):
    value = Decimal(str(value))

    if not value.is_finite() or value < 0 or value != value.quantize(Decimal("0.01")):
        raise ValueError("Enter a positive amount with at most two decimal places.")

    return value