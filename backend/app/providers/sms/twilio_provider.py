"""Real Twilio SMS provider. Mirrors providers/whatsapp/twilio_provider.py —
same REST API, no "whatsapp:" prefix, and a plain Twilio phone number as the
sender (TWILIO_SMS_FROM) instead of a WhatsApp-enabled one.
"""
from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.providers.sms.base import InboundSms, OutboundSms, SmsProvider

_API_BASE = "https://api.twilio.com/2010-04-01"


class TwilioSmsProvider(SmsProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_sms_from):
            raise RuntimeError(
                "SMS_PROVIDER=twilio needs TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
                "and TWILIO_SMS_FROM set. Nothing is sent to an unconfigured account."
            )
        self._sid = settings.twilio_account_sid
        self._token = settings.twilio_auth_token
        self._from = settings.twilio_sms_from

    def send(self, message: OutboundSms) -> None:
        resp = httpx.post(
            f"{_API_BASE}/Accounts/{self._sid}/Messages.json",
            auth=(self._sid, self._token),
            data={"From": self._from, "To": message.to_number, "Body": message.text},
            timeout=15.0,
        )
        resp.raise_for_status()

    def parse_webhook(self, payload: dict) -> InboundSms:
        return InboundSms(from_number=str(payload.get("From", "")), text=str(payload.get("Body", "")))


_provider: TwilioSmsProvider | None = None


def get_provider() -> TwilioSmsProvider:
    global _provider
    if _provider is None:
        _provider = TwilioSmsProvider()
    return _provider
