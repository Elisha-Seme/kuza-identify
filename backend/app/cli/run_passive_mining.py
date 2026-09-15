"""Passive Candidate Service batch job (Section 4). Run over a grades import.

Usage:
  python -m app.cli.run_passive_mining <school_record_import_id>

Emits grade_variance CandidateSignals (advisory only, confidence 'low').
"""
from __future__ import annotations

import sys
import uuid

from app.core.db import SessionLocal
from app.services.passive_candidate import service as passive


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m app.cli.run_passive_mining <import_id>")
        raise SystemExit(2)
    import_id = uuid.UUID(sys.argv[1])
    db = SessionLocal()
    try:
        signals = passive.run_grade_variance_mining(db, import_id)
        db.commit()
        print(f"Emitted {len(signals)} candidate signal(s):")
        for s in signals:
            print(f"  - {s.signal_type.value}: {s.evidence_text}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
