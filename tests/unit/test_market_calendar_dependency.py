import importlib


def test_pandas_market_calendars_dependency_is_importable() -> None:
    module = importlib.import_module("pandas_market_calendars")

    assert module is not None
