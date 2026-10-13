"""Real Africa's Talking USSD provider.

USSD has no separate "send" (see base.py) — the whole interaction is the
synchronous callback request/response, and the mock already mirrors Africa's
Talking's real field names (sessionId, phoneNumber, text) exactly, so parsing
doesn't change. What differs from the mock is validating that a callback is
actually well-formed AT traffic (missing sessionId/phoneNumber means a
misconfigured callback URL, not a real dial-in) rather than treating any
malformed payload as an empty first dial. AFRICASTALKING_USERNAME/API_KEY are
required to exist so a deployment can't drift into "real" mode with nothing
configured; the USSD callback itself needs no outbound API call.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.providers.ussd.base import UssdProvider, UssdTurn


class AfricasTalkingUssdProvider(UssdProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not (settings.africastalking_username and settings.africastalking_api_key):
            raise RuntimeError(
                "USSD_PROVIDER=africastalking needs AFRICASTALKING_USERNAME and "
                "AFRICASTALKING_API_KEY set, even though the USSD callback itself "
                "makes no outbound API call, so a deployment can't silently run "
                "unconfigured."
            )

    def parse_request(self, payload: dict) -> UssdTurn:
        session_id = str(payload.get("sessionId") or "")
        phone_number = str(payload.get("phoneNumber") or "")
        if not session_id or not phone_number:
            raise ValueError("Malformed Africa's Talking USSD callback: missing sessionId/phoneNumber.")
        return UssdTurn(session_id=session_id, phone_number=phone_number, text=str(payload.get("text", "")))


_provider: AfricasTalkingUssdProvider | None = None


def get_provider() -> AfricasTalkingUssdProvider:
    global _provider
    if _provider is None:
        _provider = AfricasTalkingUssdProvider()
    return _provider
