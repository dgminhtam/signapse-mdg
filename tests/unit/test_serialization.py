from decimal import Decimal

import pytest

from app.api.serialization import format_price


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [
        (Decimal("2934.564"), 2, "2934.56"),
        (Decimal("2934.565"), 2, "2934.57"),
        (Decimal("2934.5"), 2, "2934.50"),
        (Decimal("63.2049"), 3, "63.205"),
        (Decimal("1.083456"), 5, "1.08346"),
        (Decimal("12.5"), 0, "13"),
    ],
)
def test_format_price_rounds_half_up_and_pads(
    value: Decimal,
    decimals: int,
    expected: str,
) -> None:
    assert format_price(value, decimals) == expected


@pytest.mark.parametrize("decimals", [-1, 19])
def test_format_price_rejects_invalid_decimals(decimals: int) -> None:
    with pytest.raises(ValueError):
        format_price(Decimal("1"), decimals)
