"""Structured nomination form definition, including 2e amber-flag checklist items.

The form is data, not free text: every answer is a keyed structured value stored
in NominationRecord.checklist_responses (JSONB). No learner name is ever
collected — the nominator identifies the child out-of-band via the pseudonymous
learner id (Section 5).

2e amber-flag items (Section 3 / the twice-exceptional population in Section 1)
look for the giftedness-masked-by-difficulty pattern, WITHOUT ever asking for or
storing a diagnosis or health label (Section 3.5 / DPA 2019).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ChecklistItem:
    key: str
    prompt_en: str
    prompt_sw: str
    amber_flag: bool  # True => contributes to the 2e amber-flag signal


NOMINATION_CHECKLIST: list[ChecklistItem] = [
    ChecklistItem(
        "quick_grasp",
        "Grasps new ideas quickly once they are explained a different way.",
        "Huelewa mawazo mapya haraka yanapoelezwa kwa njia tofauti.",
        False,
    ),
    ChecklistItem(
        "deep_questions",
        "Asks unusually deep or unexpected questions.",
        "Huuliza maswali ya kina au yasiyotarajiwa.",
        False,
    ),
    ChecklistItem(
        "uneven_performance",
        "Performs very well in some areas but struggles in others (uneven profile).",
        "Hufanya vizuri sana katika baadhi ya maeneo lakini hutatizika katika mengine.",
        True,
    ),
    ChecklistItem(
        "underperforms_on_tests",
        "Seems more capable in conversation than their test scores show.",
        "Anaonekana mwenye uwezo zaidi katika mazungumzo kuliko alama zake za mtihani.",
        True,
    ),
    ChecklistItem(
        "focus_difficulty",
        "Has difficulty sitting still or sustaining attention on routine tasks.",
        "Ana ugumu wa kukaa tuli au kudumisha umakini kwenye kazi za kawaida.",
        True,
    ),
    ChecklistItem(
        "creative_problem_solving",
        "Solves problems in original or surprising ways.",
        "Hutatua matatizo kwa njia za kipekee au za kushangaza.",
        False,
    ),
]


def form_definition() -> list[dict]:
    """Serialisable form definition for the web/WhatsApp nomination UI."""
    return [asdict(i) for i in NOMINATION_CHECKLIST]


def amber_flag_keys() -> set[str]:
    return {i.key for i in NOMINATION_CHECKLIST if i.amber_flag}


def count_amber_flags(checklist_responses: dict) -> int:
    """How many 2e amber-flag items the nominator answered affirmatively."""
    keys = amber_flag_keys()
    return sum(
        1 for k, v in checklist_responses.items() if k in keys and bool(v)
    )
