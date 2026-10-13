"""Adaptive Item Engine (Section 4).

Owns the item bank and selects the next item. Tiers:

* "core"            - the automatic 5-question session (one per domain), in
                      ascending difficulty. Unchanged shape, so sessions,
                      scoring and completeness checks keep working.
* "pool"            - extra items per domain at a range of difficulties, for
                      adaptive branching and for the Kuza Play / facilitator
                      modes. Not yet in the automatic WhatsApp/SMS flow.
* "bonus_*"         - off-level and creativity items (richer evidence).
* "warmup_unscored" - interest picker that opens a session; never scored.

v2 items are multimedia: a picture (`image`), an optional second picture shown
after a memory item hides the first (`image_after`), tap choices, a plain-text
version for SMS/USSD/voice (`text_fallback`), and a hint ladder (`hints`) whose
use is recorded as learning-velocity evidence.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.core.enums import Channel, Language

_BANK_PATH = Path(__file__).parent / "item_bank.json"
CORE_TIER = "core"

# Fields that must never leave the server (answer keys, scorer guidance).
PRIVATE_FIELDS = {"expected_reasoning", "answer"}


@dataclass(frozen=True)
class Item:
    id: str
    domain: str
    difficulty: int
    type: str
    prompt: dict[str, str]
    expected_reasoning: str
    tier: str = CORE_TIER
    raw: dict = field(default_factory=dict, compare=False, hash=False)

    def text(self, language: Language) -> str:
        return self.prompt.get(language.value) or self.prompt["en"]

    # ---- multimedia / channel helpers --------------------------------------
    @property
    def choices(self) -> list[dict]:
        return self.raw.get("choices") or []

    @property
    def hints(self) -> list[dict]:
        return self.raw.get("hints") or []

    @property
    def image_png(self) -> str | None:
        return self.raw.get("image_png")

    def fallback(self, language: Language) -> str | None:
        fb = self.raw.get("text_fallback")
        return (fb.get(language.value) or fb.get("en")) if fb else None

    @property
    def is_memory(self) -> bool:
        return bool(self.raw.get("show_seconds"))

    def staged(self, channel: Channel) -> bool:
        """Memory items run in two messages on phone channels, so the things
        to remember and the question never sit side by side. (Kuza Play does
        its own timed show/hide, so the web channel is not staged.)"""
        return self.is_memory and channel != Channel.web

    def _opts(self, language: Language) -> str:
        return "\n".join(f"{i + 1}) {c.get(language.value) or c['en']}" for i, c in enumerate(self.choices))

    def text_for(self, channel: Channel, language: Language, stage: int = 0) -> str:
        """What to send on a given channel. SMS/USSD have no pictures, so they
        get the self-contained text version; WhatsApp gets the full prompt
        (the picture is attached separately) plus numbered options."""
        lang = language.value
        if self.staged(channel):
            if stage == 0:
                remember = ""
                if channel != Channel.whatsapp and self.raw.get("show_script"):
                    sc = self.raw["show_script"]
                    remember = "\n" + ("Kumbuka: " if lang == "sw" else "Remember: ") + (sc.get(lang) or sc["en"])
                ready = "Ukiwa tayari, jibu OK." if lang == "sw" else "When you're ready, reply OK."
                return f"{self.text(language)}{remember}\n{ready}"
            ask = self.raw.get("ask_prompt") or self.prompt
            out = ask.get(lang) or ask["en"]
            return f"{out}\n{self._opts(language)}" if self.choices else out
        if channel in (Channel.sms, Channel.ussd):
            return self.fallback(language) or self.text(language)
        out = self.text(language)
        if self.choices and self.type in ("choice", "multi_choice"):
            out = f"{out}\n{self._opts(language)}"
        return out

    def image_for(self, channel: Channel, stage: int = 0) -> str | None:
        if self.staged(channel) and stage == 1:
            return self.raw.get("image_after_png")
        if self.staged(channel) and stage == 0:
            return self.raw.get("image_png")
        return self.raw.get("image_png")

    def hint(self, n: int, language: Language) -> str | None:
        """The n-th hint (0-based), or None when the ladder is used up."""
        if n < len(self.hints):
            h = self.hints[n]
            return h.get(language.value) or h["en"]
        return None

    def describe_response(self, raw_response: str, language: Language) -> str:
        """Turn '2' / 'b' / 'B D A C' into words for the scorer, keeping the
        original. The scorer can't see the picture, so it also gets the text
        version of the question via `scoring_prompt`."""
        if not self.choices:
            return raw_response
        picked = parse_choice_indices(raw_response, len(self.choices))
        if not picked:
            return raw_response
        labels = [self.choices[i].get("en", "?") for i in picked]
        letters = " ".join("abcdefgh"[i] for i in picked)
        return f"{raw_response}  [selected: {letters} = {', '.join(labels)}]"

    def scoring_prompt(self, language: Language) -> str:
        fb = self.fallback(Language.en)
        base = self.text(language)
        return f"{base}\n(Text version of the picture: {fb})" if fb else base


_CHOICE_TOKEN = re.compile(r"\b([1-8]|[a-hA-H])\b")


def parse_choice_indices(text: str, n_choices: int) -> list[int]:
    """'2' -> [1]; 'b' -> [1]; 'BDAC' or 'b, d, a, c' -> [1,3,0,2]."""
    t = text.strip()
    if re.fullmatch(r"[a-hA-H]{2,8}", t):  # 'BDAC'
        tokens = list(t)
    else:
        tokens = _CHOICE_TOKEN.findall(t)
    out = []
    for tok in tokens:
        i = int(tok) - 1 if tok.isdigit() else ord(tok.lower()) - ord("a")
        if 0 <= i < n_choices:
            out.append(i)
    return out


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
            raw=i,
        )
        for i in data["items"]
    ]


def public_view(item: Item) -> dict:
    """Everything a client may see: no answer key, no scorer guidance."""
    return {k: v for k, v in item.raw.items() if k not in PRIVATE_FIELDS}


def session_intro(language: Language) -> str | None:
    """Untimed / no-penalty / skip-and-hint framing shown once before the
    first item (UDL practice: say the accommodation out loud)."""
    intro = _load_raw().get("session_intro")
    if not intro:
        return None
    return intro.get(language.value) or intro.get("en")


def control_word(text: str) -> str | None:
    """'skip' / 'ruka' -> 'skip', 'hint' / 'dokezo' -> 'hint', etc."""
    t = text.strip().lower()
    for action, langs in (_load_raw().get("control_words") or {}).items():
        for words in langs.values():
            if t in words:
                return action
    return None


def all_items() -> list[Item]:
    """The core 5-question set — what an automatic session actually presents."""
    return [i for i in _load_bank() if i.tier == CORE_TIER]


def bonus_items() -> list[Item]:
    return [i for i in _load_bank() if i.tier.startswith("bonus")]


def pool_items() -> list[Item]:
    return [i for i in _load_bank() if i.tier != CORE_TIER]


def every_item() -> list[Item]:
    return list(_load_bank())


def domains() -> list[str]:
    return [i.domain for i in all_items()]


def get_item(item_id: str) -> Item | None:
    """Looks across every tier — scoring needs to resolve any item."""
    return next((i for i in _load_bank() if i.id == item_id), None)


def item_count() -> int:
    return len(all_items())


def select_next(seen_item_ids: list[str]) -> Item | None:
    """Next core item, ascending difficulty, or None when complete.

    With one core item per domain this walks the ordered set so every domain
    is covered exactly once (needed for per-domain, non-composite scoring).
    The pool is there for the next step: branch to a harder/easier item in the
    same domain based on the previous response.
    """
    remaining = [i for i in all_items() if i.id not in seen_item_ids]
    if not remaining:
        return None
    return sorted(remaining, key=lambda i: i.difficulty)[0]
