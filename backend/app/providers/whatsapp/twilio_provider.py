"""Real Twilio WhatsApp provider.

Uses Twilio's plain REST API over httpx (Basic Auth with Account SID + Auth
Token) rather than the twilio SDK, keeping this a thin adapter like the mock
it replaces. Requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and
TWILIO_WHATSAPP_FROM (a WhatsApp-enabled Twilio number, "whatsapp:+1415...",
the sandbox number while testing) — see .env.example.

A first, business-initiated message to a learner outside an existing 24h
conversation window requires a Twilio-approved WhatsApp template; this class
sends free-form text, which is Twilio's only requirement for a *reply* within
an already-open conversation (the shape every message here is: the learner
messaged in first). If outbound-initiated invites are added later, route
those through an approved template SID instead of this method.
"""
from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.providers.whatsapp.base import InboundMessage, OutboundMessage, WhatsAppProvider

_API_BASE = "https://api.twilio.com/2010-04-01"


class TwilioWhatsAppProvider(WhatsAppProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_whatsapp_from):
            raise RuntimeError(
                "WHATSAPP_PROVIDER=twilio needs TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
                "and TWILIO_WHATSAPP_FROM set. Nothing is sent to an unconfigured account."
            )
        self._sid = settings.twilio_account_sid
        self._token = settings.twilio_auth_token
        self._from = settings.twilio_whatsapp_from

    def send(self, message: OutboundMessage) -> None:
        to = message.to_number
        if not to.startswith("whatsapp:"):
            to = f"whatsapp:{to}"
        resp = httpx.post(
            f"{_API_BASE}/Accounts/{self._sid}/Messages.json",
            auth=(self._sid, self._token),
            data={"From": self._from, "To": to, "Body": message.text},
            timeout=15.0,
        )
        resp.raise_for_status()

    def parse_webhook(self, payload: dict) -> InboundMessage:
        # Twilio's real webhook: form fields "From" ("whatsapp:+254...") and
        # "Body". Strip the "whatsapp:" prefix so the learner's number is
        # stored/matched the same way across every channel.
        from_number = str(payload.get("From", "")).removeprefix("whatsapp:")
        return InboundMessage(from_number=from_number, text=str(payload.get("Body", "")))


_provider: TwilioWhatsAppProvider | None = None


def get_provider() -> TwilioWhatsAppProvider:
    global _provider
    if _provider is None:
        _provider = TwilioWhatsAppProvider()
    return _provider
