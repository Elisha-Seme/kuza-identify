"""Mock USSD provider for local development and tests. Mirrors Africa's
Talking's real webhook field names (sessionId, phoneNumber, text) so swapping
in the real aggregator later is a parsing no-op.
"""
from __future__ import annotations

from app.providers.ussd.base import UssdProvider, UssdTurn


class MockUssdProvider(UssdProvider):
    def parse_request(self, payload: dict) -> UssdTurn:
        return UssdTurn(
            session_id=str(payload.get("sessionId", "")),
            phone_number=str(payload.get("phoneNumber", "")),
            text=str(payload.get("text", "")),
        )


_provider = MockUssdProvider()


def get_provider() -> MockUssdProvider:
    return _provider
