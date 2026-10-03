# billing-utils

Currency and invoice helpers used by the billing service.

## Tests

Run `python -m pytest -q`.

The conversion tests need exchange-rate fixtures in `tests/fixtures/`, which aren't checked in. Generate them with:

    python scripts/fetch_rates.py

The script calls the internal rates service and needs `RATES_TOKEN` set.
