from decimal import Decimal


def plain(value: Decimal) -> str:
    """A Decimal without trailing zeros or exponent: 20.00 -> "20", 12.50 -> "12.5"."""
    text = f"{value:f}"
    return text.rstrip("0").rstrip(".") if "." in text else text
