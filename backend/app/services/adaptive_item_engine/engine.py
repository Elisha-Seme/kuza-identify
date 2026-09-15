"""Adaptive Item Engine (Section 4).

Owns the item bank and selects the next item based on running difficulty. With
the Phase 0 five-item set this mostly walks the set in a difficulty-aware order;
the interface is built so a larger bank later gets real adaptivity for free.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.enums import Language

_BANK_PATH = Path(__file__).parent / "item_bank.json"


@dataclass(frozen=True)
class Item:
    id: str
    domain: str
    difficulty: int
    type: str
    prompt: dict[str, str]
    expected_reasoning: str

    def text(self, language: Language) -> str:
        return self.prompt.get(language.value) or self.prompt["en"]


@lru_cache
def _load_bank() -> list[Item]:
    data = json.loads(_BANK_PATH.read_text())
    return [
        Item(
            id=i["id"],
            domain=i["domain"],
            difficulty=i["difficulty"],
            type=i["type"],
            prompt=i["prompt"],
            expected_reasoning=i.get("expected_reasoning", ""),
        )
        for i in data["items"]
    ]


def all_items() -> list[Item]:
    return list(_load_bank())


def domains() -> list[str]:
    return [i.domain for i in _load_bank()]


def get_item(item_id: str) -> Item | None:
    return next((i for i in _load_bank() if i.id == item_id), None)


def item_count() -> int:
    return len(_load_bank())


def select_next(seen_item_ids: list[str]) -> Item | None:
    """Return the next item to present, or None if the session is complete.

    Running-difficulty policy: present unseen items in ascending difficulty so
    the child eases in and the session escalates. (A richer bank would branch on
    per-response performance; with five one-per-domain items we walk the ordered
    set, which keeps every domain covered exactly once — required for the
    per-domain, non-composite scoring in Section 3.1.)
    """
    remaining = [i for i in _load_bank() if i.id not in seen_item_ids]
    if not remaining:
        return None
    return sorted(remaining, key=lambda i: i.difficulty)[0]
