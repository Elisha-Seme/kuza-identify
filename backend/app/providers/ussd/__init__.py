"""Provider factory: USSD_PROVIDER selects mock (default, no credentials) or
africastalking (real). Mirrors providers/whatsapp/__init__.py."""
from __future__ import annotations

from app.core.config import get_settings
from app.providers.ussd.base import UssdProvider


def get_provider() -> UssdProvider:
    provider = get_settings().ussd_provider
    if provider == "africastalking":
        from app.providers.ussd.africastalking_provider import get_provider as get_at

        return get_at()
    if provider != "mock":
        raise RuntimeError(f"Unknown USSD_PROVIDER '{provider}'. Use 'mock' or 'africastalking'.")
    from app.providers.ussd.mock import get_provider as get_mock

    return get_mock()
