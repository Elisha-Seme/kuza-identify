"""Bias Audit Service batch job (Section 4 / Section 7).

Usage:  python -m app.cli.run_bias_audit

Prints flag/advance rates by pathway, school tier, and gender. Pathway is a
first-class slice because passive mining must be audited separately (Section 3.7).
"""
from __future__ import annotations

from app.core.db import SessionLocal
from app.services.bias_audit import service as bias


def _print_slice(title: str, stats: dict) -> None:
    print(f"\n{title}")
    print(f"  {'slice':<24}{'sessions':>9}{'flag_rate':>11}{'advance_rate':>14}")
    for key, s in sorted(stats.items()):
        print(f"  {key:<24}{s.sessions:>9}{s.flag_rate:>11}{s.advance_rate:>14}")


def main() -> None:
    db = SessionLocal()
    try:
        report = bias.run_bias_audit(db)
        _print_slice("By pathway (active / nomination / passive):", report.by_pathway)
        _print_slice("By school tier:", report.by_school_tier)
        _print_slice("By gender:", report.by_gender)
    finally:
        db.close()


if __name__ == "__main__":
    main()
