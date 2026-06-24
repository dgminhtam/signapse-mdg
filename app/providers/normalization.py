from decimal import Decimal, InvalidOperation


def parse_decimal(
    value: object,
    *,
    positive: bool,
    allow_numbers: bool = False,
    allow_decimal: bool = False,
) -> Decimal | None:
    allowed_types: tuple[type[object], ...] = (str,)
    if allow_numbers:
        allowed_types += (int, float)
    if allow_decimal:
        allowed_types += (Decimal,)

    if isinstance(value, bool) or not isinstance(value, allowed_types):
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    if not parsed.is_finite() or parsed < 0 or (positive and parsed <= 0):
        return None
    return parsed
