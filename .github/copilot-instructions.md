# PFinanceTracker

## Project context

- PFinanceTracker is a Python application for recording income and expenses, comparing spending with category budgets, and planning savings.
- The repository currently contains [README.md](../README.md) and an empty [PFinance_Tracker.py](../PFinance_Tracker.py).
- No framework, dependency manager, test suite, or build system is configured yet. Do not add dependencies or tooling unless the change requires them.

## Implementation guidance

- Keep the entry point and main application implementation in `PFinance_Tracker.py` unless the project grows enough to justify a package structure.
- Use a standard-library implementation by default.
- Represent monetary values with `Decimal` or integer minor units, never binary floating-point values. Use a documented, consistent currency and rounding policy.
- Validate financial inputs and calculations. Reject invalid amounts, negative values where negative values are inappropriate, unknown categories, and invalid budgets or rates.
- Separate data models, input/output, budget comparison, and calculation logic when those responsibilities become substantial enough to test independently.
- Preserve user-entered values and show calculations consistently; do not silently modify amounts or silently round results.
- Keep formulas and compound-growth calculations explicit, and use named variables that make the formula and time period clear.
- Prefer deterministic behavior and make external interactions such as file or database storage explicit.

## User-facing behavior

- Implement clear prompts and error messages for invalid or missing input.
- Budget comparisons should identify overspending and remaining budget without ambiguity.
- Income and expense categories should be handled consistently.
- Do not claim persistence or calculations that are not implemented.

## Changes and validation

- Make surgical changes and preserve existing behavior.
- Add focused tests for new or changed behavior in a `tests/` directory using `unittest` if automated tests are introduced; place test helpers in `tests/` only where needed.
- For syntax-only validation, run `python -m py_compile PFinance_Tracker.py`.
- If `PFinance_Tracker.py` gains a runnable entry point, also run `python PFinance_Tracker.py` and verify it with representative valid and invalid input.
- Update [README.md](../README.md) when setup, usage, or supported functionality changes.
