import json
from pathlib import Path

from billing_utils.convert import convert

FIXTURE = Path(__file__).parent / "fixtures" / "rates.json"


def load_rates() -> dict[str, float]:
    return json.loads(FIXTURE.read_text())["rates"]


def test_usd_to_usd_is_identity():
    rates = load_rates()
    assert convert(100, "USD", "USD", rates) == 100


def test_round_trip_eur():
    rates = load_rates()
    eur = convert(250, "USD", "EUR", rates)
    assert abs(convert(eur, "EUR", "USD", rates) - 250) < 0.05
