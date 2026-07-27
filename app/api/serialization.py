from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal


def format_decimal(value: Decimal) -> str:
    return format(value, "f")


def format_price(value: Decimal, decimals: int) -> str:
    if not 0 <= decimals <= 18:
        raise ValueError("Price display decimals must be between 0 and 18.")
    quantum = Decimal(1).scaleb(-decimals)
    rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
    return format(rounded, f".{decimals}f")


def format_datetime(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
