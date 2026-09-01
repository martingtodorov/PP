"""Currency helpers — imported Shopify orders can be in RON/BGN/etc, amounts are normalised to EUR."""

# Units of foreign currency per 1 EUR
CURRENCY_RATES = {
    "EUR": 1.0,
    "BGN": 1.95583,
    "RON": 4.9750,
    "HUF": 395.0,
    "PLN": 4.30,
    "CZK": 25.20,
    "GBP": 0.845,
    "USD": 1.08,
}


def rate_for(currency: str) -> float:
    return CURRENCY_RATES.get((currency or "EUR").upper().strip(), 1.0)


def to_eur(amount, currency: str) -> float:
    try:
        return round(float(amount or 0) / rate_for(currency), 2)
    except (TypeError, ValueError):
        return 0.0
