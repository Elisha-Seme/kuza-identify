"""Mock SMS provider for local development and tests. Mirrors the WhatsApp
mock exactly (see providers/whatsapp/mock.py) — no real Africa's Talking
credentials yet.
"""
from __future__ import annotations

from app.providers.sms.base import InboundSms, OutboundSms, SmsProvider


class MockSmsProvider(SmsProvider):
    def __init__(self) -> None:
        self.outbox: dict[str, list[str]] = {}

    def send(self, message: OutboundSms) -> None:
        self.outbox.setdefault(message.to_number, []).append(message.text)

    def parse_webhook(self, payload: dict) -> InboundSms:
        return InboundSms(from_number=str(payload["from"]), text=str(payload.get("text", "")))

    def last_message_to(self, number: str) -> str | None:
        msgs = self.outbox.get(number)
        return msgs[-1] if msgs else None


_provider = MockSmsProvider()


def get_provider() -> MockSmsProvider:
    return _provider
