from datetime import datetime
from decimal import Decimal


def format_decimal(value: Decimal) -> str:
    return format(value, "f")


def format_datetime(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
