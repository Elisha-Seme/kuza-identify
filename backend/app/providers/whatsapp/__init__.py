"""Provider factory: WHATSAPP_PROVIDER selects mock (default, no credentials)
or twilio (real). The Screening Gateway and API layer only ever call
get_provider() here, never a concrete class directly.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.providers.whatsapp.base import WhatsAppProvider


def get_provider() -> WhatsAppProvider:
    provider = get_settings().whatsapp_provider
    if provider == "twilio":
        from app.providers.whatsapp.twilio_provider import get_provider as get_twilio

        return get_twilio()
    if provider != "mock":
        raise RuntimeError(f"Unknown WHATSAPP_PROVIDER '{provider}'. Use 'mock' or 'twilio'.")
    from app.providers.whatsapp.mock import get_provider as get_mock

    return get_mock()
