"""Voice-note transcription — INTERFACE AND TYPES ONLY, no live provider wired.

Requested as an accommodation for dyslexia / writing anxiety: a child answers
by voice instead of text. WhatsApp genuinely supports this both ways (OGG/opus
voice notes, confirmed against Twilio's docs), so this is real once Twilio is
connected — the gap right now is purely "no speech-to-text provider is
configured," not a design limitation.

Important: Claude does not transcribe audio. Speech-to-text needs a dedicated
provider (OpenAI's Whisper API, Google Speech-to-Text, or similar) — a new
external dependency with its own credential, exactly like Twilio or KEMIS.
This module is deliberately built the same way as the KEMIS adapter: an
interface the rest of the system can call today, with a stub that raises
until a real provider and API key are configured. No request is ever silently
sent to an un-configured or un-approved third party.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import get_settings


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    provider: str
    language_hint: str | None = None


class TranscriptionProvider(Protocol):
    def transcribe(self, audio_bytes: bytes, *, mime_type: str, language_hint: str | None = None) -> TranscriptionResult:
        """Convert a voice note to text. Raises on failure; never guesses."""


class NotConfiguredTranscriptionProvider:
    """Default until a real speech-to-text provider is wired in. Mirrors
    NotConnectedKemisAdapter's discipline: fail loudly, never fabricate text."""

    def transcribe(self, audio_bytes: bytes, *, mime_type: str, language_hint: str | None = None) -> TranscriptionResult:
        raise NotImplementedError(
            "No speech-to-text provider is configured. Voice-note answers need "
            "a transcription provider (e.g. OpenAI Whisper, Google Speech-to-Text) "
            "and its own API key — set one up and implement TranscriptionProvider "
            "before wiring this in. Nothing is sent to an unconfigured third party."
        )


def get_provider() -> TranscriptionProvider:
    settings = get_settings()
    if not settings.transcription_provider or settings.transcription_provider == "none":
        return NotConfiguredTranscriptionProvider()
    raise NotImplementedError(
        f"Transcription provider '{settings.transcription_provider}' is not implemented yet. "
        "Add a class here and a credential in config before selecting it."
    )
