"""Currency conversion using a table of rates quoted against USD."""


def convert(amount: float, from_ccy: str, to_ccy: str, rates: dict[str, float]) -> float:
    """Convert amount between currencies. `rates` maps currency code to units per 1 USD."""
    usd = amount / rates[from_ccy]
    return round(usd * rates[to_ccy], 2)
