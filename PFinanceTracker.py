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

def normalize_date(value):
    """Validate a YYYY-MM-DD date and return its canonical ISO form."""
    try:
        year, month, day = map(int, value.strip().split("-"))
        return date(year, month, day).isoformat()
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("Enter a valid date in YYYY-MM-DD format.") from error


def normalize_month(value):
    """Validate a YYYY-MM month and return its canonical ISO form."""
    try:
        year, month = map(int, value.strip().split("-"))
        return date(year, month, 1).isoformat()[:7]
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("Enter a valid month in YYYY-MM format.") from error


# Check each transaction before saving.
def transaction(day, category, amount, kind):
    day = normalize_date(day)

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

# Convert the supplied path to a Path object and open the CSV for reading.
def import_csv(path, data):
    
    # utf-8-sig also handles files that include a UTF-8 byte-order mark.
    with Path(path).open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        # DictReader maps each CSV row to a dictionary using the header names.
        reader = csv.DictReader(file)

        # Check that all required columns are present.
        # Strip spaces and ignore capitalization when checking the headers.
        required = {"date", "category", "amount", "type"}
        headers = {
            name.strip().lower()
            for name in (reader.fieldnames or [])
        }

        if not required.issubset(headers):
            raise ValueError(
                "CSV requires date, category, amount, and type columns."
            )

        # Count successfully imported transactions.
        imported = 0

        # Validate each CSV row with transaction() before adding it to the data.
        for row in reader:
            # Normalize column names so they match the required lowercase names.
            normalized = {
                key.strip().lower(): value
                for key, value in row.items()
            }

            # Create a validated transaction from the CSV values.
            item = transaction(
                normalized["date"].strip(),
                normalized["category"].strip(),
                normalized["amount"].strip(),
                normalized["type"].strip().lower(),
            )

            # Add the validated transaction to the in-memory data.
            data["transactions"].append(item)
            imported += 1

    # Return the number of transactions added.
    return imported

# Calculate the selected month's totals and expense categories.
def export_month_csv(data, month, directory=OUTPUT):
    
    # This keeps the exported figures consistent with the monthly summary.
    income, expenses, net, categories = summary(data, month)

    # Convert the output directory to a Path and create it if needed.
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    # Build the output filename using the selected month.
    path = directory / f"summary-{month}.csv"

    # Open the CSV file for writing, preserving correct CSV newline handling.
    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        # Create a CSV writer and write the monthly report details.
        writer = csv.writer(file)
        writer.writerow(["Month", month])
        writer.writerow(["Currency", data["currency"]])
        writer.writerow(["Income", income])
        writer.writerow(["Expenses", expenses])
        writer.writerow(["Net cash flow", net])

        # Add a blank row to separate the totals from category details.
        writer.writerow([])
        writer.writerow(["Category", "Expenses"])

        # Write each expense category in alphabetical order.
        for category in sorted(categories):
            writer.writerow([
                category,
                categories[category],
            ])

    # Return the output path so the caller can display or reuse it.
    return path

# Label and save financial charts as PNG images.
def finish_chart(name, title, xlabel, ylabel):
    # Create the output folder if it does not exist yet.
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # Add labels and format the current Matplotlib figure.
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.xticks(rotation=30)
    plt.tight_layout()

    # Save the chart as a PNG file and close the figure to free resources.
    path = OUTPUT / name
    plt.savefig(path)
    plt.close()

    return path


def export_trend_png(months, totals, fitted, prediction, rmse, filename="expense-trend.png"):
    # Add the forecast month so it can be shown after the historical data.
    forecast_month = next_month(months[-1])
    chart_months = months + [forecast_month]
    trend_values = list(fitted) + [prediction]

    # Plot actual monthly expenses and the fitted trend with its forecast.
    plt.figure()
    plt.plot(months, totals, "o-", label="Actual expenses")
    plt.plot(chart_months, trend_values, "--", label="Trend and forecast")
    plt.scatter([forecast_month], [prediction], label="Forecast")

    # Save the chart using the shared chart-export helper.
    return finish_chart(
        filename,
        f"Expense trend (RMSE: {rmse:.2f})",
        "Month",
        "Expenses",
    )

# Read and validate numerical input from the keyboard.
def number(prompt):
    value = float(input(prompt))

    if not math.isfinite(value):
        raise ValueError("Enter a finite number.")

    return value

def main():
    # Load saved tracker data if it exists; otherwise create a new data file.
    if DATA_FILE.exists():
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    else:
        # Ask for the currency label when setting up the tracker for the first time.
        currency = input("Currency label (for example USD or KES): ").strip()
        if not currency:
            print("A currency label is required.")
            return

        # Initialize the expected data structure and save it.
        data = {
            "currency": currency,
            "transactions": [],
            "budgets": {},
        }
        save(data)

    # Keep the selected currency available for displaying amounts.
    currency = data["currency"]

    # Repeat the menu until the user chooses to quit.
    while True:
        print("\nPERSONAL FINANCE TRACKER")
        print("1. Add transaction")
        print("2. Import transactions from CSV")
        print("3. Monthly summary")
        print("4. Export monthly summary to CSV")
        print("5. Expense trend")
        print("6. Savings target")
        print("7. Monte Carlo simulation")
        print("8. Investment allocation")
        print("0. Quit")

        # Read the user's menu selection.
        choice = input("Choose: ").strip()

        try:
            # Exit the menu loop and end the program.
            if choice == "0":
                break

            elif choice == "1":
                # Validate a new transaction, add it to the data, and save it.
                item = transaction(
                    input("Date (YYYY-MM-DD): ").strip(),
                    input("Category: ").strip(),
                    input("Amount: ").strip(),
                    input("Type (income/expense): ").strip().lower(),
                )
                data["transactions"].append(item)
                save(data)
                print("Transaction added.")

            elif choice == "2":
                # Import transactions from a CSV file and save the updated data.
                count = import_csv(input("CSV path: ").strip(), data)
                save(data)
                print(f"Imported {count} transactions.")

            elif choice == "3":
                # Calculate and display the selected month's financial summary.
                month = input("Month (YYYY-MM): ").strip()
                income, expenses, net, categories = summary(data, month)

                print(f"\nCurrency: {currency}")
                print(f"Income:   {income:.2f}")
                print(f"Expenses: {expenses:.2f}")
                print(f"Net:      {net:.2f}")

                # Show expense totals grouped by category.
                for category, total in sorted(categories.items()):
                    print(f"{category}: {total:.2f}")

            elif choice == "4":
                # Export the selected month's totals and category expenses to CSV.
                month = input("Month (YYYY-MM): ").strip()
                path = export_month_csv(data, month)
                print(f"Monthly report saved to: {path}")

            elif choice == "5":
                # Ask for a range of completed months to analyze.
                start = input("First complete month (YYYY-MM): ").strip()
                end = input("Last complete month (YYYY-MM): ").strip()

                # Calculate historical expenses, fitted trend, forecast, and error.
                months, totals, fitted, prediction, rmse = expense_trend(
                    data, start, end
                )

                # Display the forecast for the month after the selected range.
                forecast_month = next_month(months[-1])
                print(
                    f"Projected expenses for {forecast_month}: "
                    f"{prediction:.2f} {currency}"
                )
                print(f"Trend RMSE: {rmse:.2f}")

                # Export a chart of the historical trend and forecast.
                path = export_trend_png(
                    months, totals, fitted, prediction, rmse, data
                )
                print(f"Trend chart saved to: {path}")

            elif choice == "6":
                # Collect savings inputs and convert the annual percentage to a rate.
                balance = money(input("Initial balance: ").strip())
                target = money(input("Savings target: ").strip())
                annual_rate = (
                    decimal_value(
                        input("Annual interest rate (percent): ").strip()
                    )
                    / Decimal("100")
                )
                months_to_save = int(input("Months until deadline: ").strip())

                # Calculate the monthly contribution needed to reach the target.
                contribution, iterations, width = required_contribution(
                    balance, target, annual_rate, months_to_save
                )

                # Generate the balance at the start and end of each month.
                balances = savings(
                    balance,
                    money(contribution),
                    annual_rate,
                    months_to_save,
                )

                # Show the contribution, projected result, and search details.
                print(f"Monthly contribution: {contribution:.2f} {currency}")
                print(f"Projected final balance: {balances[-1]:.2f} {currency}")
                print(f"Search iterations: {iterations}")
                print(f"Search interval width: {width:.2f}")

                # Optionally export the monthly schedule and its chart.
                if input("Export savings schedule and chart? (y/n): ").strip().lower() == "y":
                    write_csv(
                        "savings.csv",
                        ["month", f"balance_{currency}"],
                        enumerate(balances),
                    )

                    # Plot the savings balance for each month.
                    plt.figure()
                    plt.plot(
                        range(len(balances)),
                        [float(value) for value in balances],
                    )

                    # Label and save the chart using the chart helper.
                    chart_path = finish_chart(
                        "savings.png",
                        "Savings balance schedule",
                        "Month",
                        currency,
                    )
                    print(f"Savings files saved in: {OUTPUT}")
                    print(f"Chart saved to: {chart_path}")

            elif choice == "7":
                # Run simulations using the entered balance, contribution, return, and volatility.
                bands = monte_carlo(
                    number("Initial balance: "),
                    number("Monthly contribution: "),
                    number("Expected annual return (percent): ") / 100,
                    number("Annual volatility (percent): ") / 100,
                )

                # Display the final 5th, 50th, and 95th percentile balances.
                print(
                    "Final balance percentiles (5th, 50th, 95th):",
                    np.round(bands[:, -1], 2),
                    currency,
                )

                # Plot the percentile range and median across all simulated months.
                plt.figure()
                months = range(bands.shape[1])
                plt.fill_between(
                    months,
                    bands[0],
                    bands[2],
                    alpha=0.3,
                    label="5th–95th percentiles",
                )
                plt.plot(months, bands[1], label="Median")
                plt.legend()

                # Label and save the simulation chart.
                chart_path = finish_chart(
                    "monte_carlo.png",
                    "Five-year wealth simulation",
                    "Month",
                    currency,
                )
                print(f"Simulation chart saved to: {chart_path}")

            elif choice == "8":
                # Ask for the investment amount and gather inputs for each asset.
                amount = number("Amount to allocate: ")
                returns = []
                risks = []
                caps = []

                # Collect the expected return, risk score, and maximum allocation per asset.
                for asset in ("Cash", "Bonds", "Stocks"):
                    print(f"\n{asset}")
                    returns.append(
                        number("Expected annual return (percent): ") / 100
                    )
                    risks.append(number("Risk score: "))
                    caps.append(
                        number("Maximum allocation (percent): ") / 100
                    )

                # Gather the overall risk limit and minimum cash reserve.
                risk_limit = number("Maximum weighted risk score: ")
                cash_minimum = number("Minimum cash reserve: ")

                # Calculate the allocation that satisfies the supplied constraints.
                allocation = optimize_allocation(
                    amount,
                    returns,
                    risks,
                    caps,
                    risk_limit,
                    cash_minimum,
                )

                # Display the allocated amount for each asset.
                for asset, value in zip(("Cash", "Bonds", "Stocks"), allocation):
                    print(f"{asset}: {value:.2f} {currency}")

            else:
                # Handle menu selections that do not match an available option.
                print("Choose a number from the menu.")

        # Show expected input, calculation, file, or data errors without exiting.
        except (ValueError, ArithmeticError, OSError, KeyError) as error:
            print(f"Error: {error}")


# Start the tracker only when this file is run directly.
if __name__ == "__main__":
    main()
