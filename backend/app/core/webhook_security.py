"""Inbound-webhook verification for the real channel providers.

Twilio cryptographically signs every webhook; Africa's Talking does not (no
signing scheme exists in their USSD/SMS product), so a shared secret in the
callback URL's query string is the honest substitute. Neither check invents
security Twilio/AT don't actually offer.
"""
from __future__ import annotations

import base64
import hashlib
import hmac


def twilio_signature_valid(
    *, url: str, params: dict[str, str], signature: str | None, auth_token: str
) -> bool:
    """Replicates Twilio's X-Twilio-Signature algorithm (no twilio SDK needed):
    HMAC-SHA1 over the exact webhook URL followed by each POST param's key and
    value, sorted by key, keyed with the Auth Token, base64-encoded.
    https://www.twilio.com/docs/usage/webhooks/webhooks-security
    """
    if not signature:
        return False
    data = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    digest = hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def shared_secret_valid(*, provided: str | None, expected: str | None) -> bool:
    """For Africa's Talking, which has no request-signing scheme: the callback
    URL registered in their dashboard carries a `?key=...` we chose ourselves.
    If no secret is configured, verification is skipped (local/dev only) —
    the caller decides whether that is acceptable for its environment."""
    if not expected:
        return True
    return bool(provided) and hmac.compare_digest(provided, expected)
