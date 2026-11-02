from fastapi import Request

from app.providers.mt5 import MT5Provider


def get_mt5_provider(request: Request) -> MT5Provider | None:
    provider = getattr(request.app.state, "mt5_provider", None)
    return provider if isinstance(provider, MT5Provider) else None
