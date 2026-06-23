import importlib
from pathlib import Path


def test_yfinance_dependency_is_importable() -> None:
    module = importlib.import_module("yfinance")

    assert module is not None


def test_yfinance_imports_stay_inside_provider_package() -> None:
    root = Path(__file__).parents[2] / "app"
    offenders = []
    for path in root.rglob("*.py"):
        if path.parent.name == "providers":
            continue
        text = path.read_text(encoding="utf-8")
        if "import yfinance" in text.lower() or "from yfinance" in text.lower():
            offenders.append(path.relative_to(root))

    assert offenders == []


def test_yfinance_is_wired_into_quote_candle_and_stream_providers() -> None:
    root = Path(__file__).parents[2] / "app"
    quote_route = root / "api" / "routes_quotes.py"
    candle_route = root / "api" / "routes_candles.py"
    main = root / "main.py"
    stream_provider = root / "providers" / "yfinance_market_data_stream.py"

    assert "YFINANCE" in quote_route.read_text(encoding="utf-8")
    assert "YFINANCE" in candle_route.read_text(encoding="utf-8")
    assert "YFINANCE" in main.read_text(encoding="utf-8")
    assert "AsyncWebSocket" in stream_provider.read_text(encoding="utf-8")
