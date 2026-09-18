"""USSD provider interface — the no-smartphone, no-internet, no-airtime-needed
channel (dial a shortcode; no data plan required at all).

USSD is NOT the same shape as WhatsApp/SMS. It is a synchronous, session-bound
menu protocol: the carrier holds one open session per phone while the learner
is dialed in, and the callback must reply within the same HTTP request with
either "CON <text>" (continue — show more, session stays open) or
"END <text>" (terminate the session). There is no separate outbound "send" —
the whole interaction is request-in, response-out, per screen, and Africa's
Talking (Section 6) is the standard Kenya USSD aggregator this is modelled on.

Real constraints worth being honest about, not hidden by this interface:
  * ~182 characters per screen (some handsets show less).
  * Sessions time out (~180s of inactivity) — a slow, careful thinker can be
    cut off mid-answer, which cuts directly against the "no time limit"
    accommodation. USSD suits the forced-choice item (say a letter/number)
    far better than an open-ended one; a long written reasoning answer is a
    poor fit for a numeric keypad and a session clock outside our control.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class UssdTurn:
    """One request in a USSD session. `text` is empty on first dial, and on
    every later screen is the full chain of what the learner has typed so far
    (the aggregator's convention, not just the latest keypress)."""

    session_id: str
    phone_number: str
    text: str


@dataclass(frozen=True)
class UssdReply:
    keep_session_open: bool
    text: str

    def render(self) -> str:
        return f"{'CON' if self.keep_session_open else 'END'} {self.text}"


class UssdProvider(Protocol):
    def parse_request(self, payload: dict) -> UssdTurn:
        """Normalise a raw provider callback body into a UssdTurn."""
