"""SMS provider interface — the no-smartphone, no-internet channel.

Same shape as the WhatsApp provider on purpose: SMS is async, sequential text
in both directions, so the Screening Gateway can drive it identically. The
real difference is delivery (works on any phone with signal, no app, no data
plan) and a tighter length budget (a single SMS is ~160 GSM-7 characters;
longer messages are concatenated by the carrier, at extra cost per segment).
Africa's Talking (Section 6) is the standard Kenya SMS/USSD provider — this
interface is written so their SDK becomes one new class, no gateway changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InboundSms:
    from_number: str
    text: str


@dataclass(frozen=True)
class OutboundSms:
    to_number: str
    text: str


class SmsProvider(Protocol):
    def send(self, message: OutboundSms) -> None:
        """Deliver a message to the learner's phone."""

    def parse_webhook(self, payload: dict) -> InboundSms:
        """Normalise a raw provider webhook body into an InboundSms."""
