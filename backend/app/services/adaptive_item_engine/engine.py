"""Adaptive Item Engine (Section 4).

Owns the item bank and selects the next item based on running difficulty. With
the Phase 0 five-item set this mostly walks the set in a difficulty-aware order;
the interface is built so a larger bank later gets real adaptivity for free.

Items carry a `tier`: "core" items are the automatic 5-question session (the
shape existing sessions/scoring/completeness assume — unchanged, no
regression). "bonus_*" items (off-level, creativity) are additional evidence
content, exposed separately, not yet wired into the automatic session flow —
that would need adaptive branching logic in the gateway, a bigger structural
change than adding content.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.enums import Language

_BANK_PATH = Path(__file__).parent / "item_bank.json"
CORE_TIER = "core"


@dataclass(frozen=True)
class Item:
    id: str
    domain: str
    difficulty: int
    type: str
    prompt: dict[str, str]
    expected_reasoning: str
    tier: str = CORE_TIER

    def text(self, language: Language) -> str:
        return self.prompt.get(language.value) or self.prompt["en"]


@lru_cache
def _load_raw() -> dict:
    return json.loads(_BANK_PATH.read_text())


@lru_cache
def _load_bank() -> list[Item]:
    data = _load_raw()
    return [
        Item(
            id=i["id"],
            domain=i["domain"],
            difficulty=i["difficulty"],
            type=i["type"],
            prompt=i["prompt"],
            expected_reasoning=i.get("expected_reasoning", ""),
            tier=i.get("tier", CORE_TIER),
        )
        for i in data["items"]
    ]


def session_intro(language: Language) -> str | None:
    """The untimed / no-penalty framing shown once, before the first item
    (UDL practice: state the accommodation explicitly, don't just leave it
    unenforced). Returns None if the bank defines no intro."""
    intro = _load_raw().get("session_intro")
    if not intro:
        return None
    return intro.get(language.value) or intro.get("en")


def all_items() -> list[Item]:
    """The core 5-question set — what an automatic session actually presents."""
    return [i for i in _load_bank() if i.tier == CORE_TIER]


def bonus_items() -> list[Item]:
    """Off-level / creativity items — additional evidence, previewable, not yet
    part of the automatic session (see module docstring)."""
    return [i for i in _load_bank() if i.tier != CORE_TIER]


def domains() -> list[str]:
    return [i.domain for i in all_items()]


def get_item(item_id: str) -> Item | None:
    """Looks across every tier — scoring needs to resolve a bonus item too."""
    return next((i for i in _load_bank() if i.id == item_id), None)


def item_count() -> int:
    return len(all_items())


def select_next(seen_item_ids: list[str]) -> Item | None:
    """Return the next core item to present, or None if the session is
    complete.

    Running-difficulty policy: present unseen items in ascending difficulty so
    the child eases in and the session escalates. (A richer bank would branch on
    per-response performance; with five one-per-domain items we walk the ordered
    set, which keeps every domain covered exactly once — required for the
    per-domain, non-composite scoring in Section 3.1.)
    """
    remaining = [i for i in all_items() if i.id not in seen_item_ids]
    if not remaining:
        return None
    return sorted(remaining, key=lambda i: i.difficulty)[0]
