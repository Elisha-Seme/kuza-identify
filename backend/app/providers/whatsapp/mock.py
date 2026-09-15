"""Mock WhatsApp provider for local development and tests.

No real credentials (no Africa's Talking / Twilio) — outbound messages are
captured in an in-memory outbox that the demo CLI and tests can read back, so a
full screening conversation can be driven end-to-end locally.
"""
from __future__ import annotations

from app.providers.whatsapp.base import InboundMessage, OutboundMessage, WhatsAppProvider


class MockWhatsAppProvider(WhatsAppProvider):
    def __init__(self) -> None:
        # Per-number outbox: {number: [texts...]} — inspectable by the demo/tests.
        self.outbox: dict[str, list[str]] = {}

    def send(self, message: OutboundMessage) -> None:
        self.outbox.setdefault(message.to_number, []).append(message.text)

    def parse_webhook(self, payload: dict) -> InboundMessage:
        # Mirrors the shape the demo/test harness POSTs to the gateway webhook.
        return InboundMessage(
            from_number=str(payload["from"]),
            text=str(payload.get("text", "")),
        )

    def last_message_to(self, number: str) -> str | None:
        msgs = self.outbox.get(number)
        return msgs[-1] if msgs else None


# Process-wide singleton so the FastAPI webhook and any in-process demo share the
# same outbox. A real provider would be stateless and talk to the vendor API.
_provider = MockWhatsAppProvider()


def get_provider() -> MockWhatsAppProvider:
    return _provider
