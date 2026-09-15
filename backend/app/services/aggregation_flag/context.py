"""Context adjustment via a simple school-tier lookup table (Section 3.2 / 8).

Phase 0 uses a lookup table, NOT a trained model (explicitly out of scope). A
lower-resourced tier gets a factor > 1.0 so an equivalent raw answer is credited
against the tougher baseline the child actually faced — the equity mechanism.
"""
from __future__ import annotations

# tier -> multiplicative adjustment factor applied to every domain's raw score.
# These are placeholder, defensible starting values — tune against pilot data.
TIER_ADJUSTMENT_FACTORS: dict[str, float] = {
    "low_resource": 1.20,
    "medium_resource": 1.05,
    "high_resource": 1.00,
}

DEFAULT_FACTOR = 1.0


def factor_for_tier(tier: str) -> float:
    return TIER_ADJUSTMENT_FACTORS.get(tier, DEFAULT_FACTOR)
