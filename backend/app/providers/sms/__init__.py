"""Provider factory: SMS_PROVIDER selects mock (default, no credentials) or
twilio (real). Mirrors providers/whatsapp/__init__.py."""
from __future__ import annotations

from app.core.config import get_settings
from app.providers.sms.base import SmsProvider


def get_provider() -> SmsProvider:
    provider = get_settings().sms_provider
    if provider == "twilio":
        from app.providers.sms.twilio_provider import get_provider as get_twilio

        return get_twilio()
    if provider != "mock":
        raise RuntimeError(f"Unknown SMS_PROVIDER '{provider}'. Use 'mock' or 'twilio'.")
    from app.providers.sms.mock import get_provider as get_mock

    return get_mock()
