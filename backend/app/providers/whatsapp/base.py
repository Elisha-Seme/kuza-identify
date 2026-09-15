"""WhatsApp provider interface.

The Screening Gateway only ever talks to this interface, never to a concrete
vendor. Swapping in Africa's Talking or Twilio (Section 6) means writing one new
class here and changing WHATSAPP_PROVIDER — no gateway code changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InboundMessage:
    """A message arriving from a learner's handset (normalised across vendors)."""

    from_number: str
    text: str


@dataclass(frozen=True)
class OutboundMessage:
    to_number: str
    text: str


class WhatsAppProvider(Protocol):
    """Minimal surface the gateway depends on."""

    def send(self, message: OutboundMessage) -> None:
        """Deliver a message to the learner."""

    def parse_webhook(self, payload: dict) -> InboundMessage:
        """Normalise a raw provider webhook body into an InboundMessage."""
