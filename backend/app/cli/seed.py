"""Seed script — 2-3 fake learner profiles across all three pathways, so the
dashboard and pipeline are testable immediately (spec Section 8 deliverable).

Run:  python -m app.cli.seed        (inside the api container / venv)

Idempotency: intended for a fresh database. Re-running appends more data; it does
not de-duplicate. `docker compose down -v` resets.

No real names, diagnoses, or health data anywhere — consistent with Section 5.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.core.db import SessionLocal
from app.core.enums import (
    Channel,
    ConsentScope,
    Language,
    LearnerSource,
    NominatorRole,
    RecordType,
    SourceSystem,
)
from app.models import (
    ConsentRecord,
    ContextAdjustment,
    DomainScore,
    Learner,
    School,
    SchoolRecordImport,
    ScreeningSession,
)
from app.services.adaptive_item_engine import engine as items
from app.services.aggregation_flag.context import factor_for_tier
from app.services.aggregation_flag.engine import evaluate_and_flag
from app.services.nomination import service as nomination
from app.services.passive_candidate import service as passive
from app.services.screening_gateway import service as gateway

SAMPLE_GRADES = Path(__file__).parent / "sample_data" / "grades_sample.csv"


def _seed_context_adjustments(db, school: School) -> None:
    """Populate ContextAdjustment from the tier lookup (Section 3.2, Phase 0)."""
    factor = factor_for_tier(school.tier)
    for domain in dict.fromkeys(items.domains()):  # unique, order-preserving
        db.add(
            ContextAdjustment(
                school_id=school.id, domain=domain, adjustment_factor=factor
            )
        )
    db.flush()


def _insert_completed_scored_session(
    db, learner: Learner, domain_scores: dict[str, int]
) -> ScreeningSession:
    """Deterministic demo fixture: a completed session with hand-set DomainScores
    (a clear spike), so the panel dashboard always has flagged content regardless
    of whether the live LLM or the mock scorer is in use. Marked as seed data via
    scoring_model_version."""
    session = ScreeningSession(
        learner_id=learner.id,
        channel=Channel.whatsapp,
        language=Language.en,
        status="completed",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.flush()
    for domain, score in domain_scores.items():
        db.add(
            DomainScore(
                session_id=session.id,
                domain=domain,
                score=score,
                evidence_text=f"[seed fixture] illustrative evidence for {domain}.",
                scoring_model_version="seed-fixture",
            )
        )
    db.flush()
    evaluate_and_flag(db, session.id)  # writes FlagEvents + opens audit trail
    return session


def main() -> None:
    db = SessionLocal()
    try:
        # --- Schools (different resource tiers) -------------------------------
        kibera = School(
            name="Kibera APBET Primary (demo)",
            tier="low_resource",
            network="APBET / Kibera-Mukuru pilot",
        )
        mukuru = School(
            name="Mukuru Community School (demo)",
            tier="medium_resource",
            network="APBET / Kibera-Mukuru pilot",
        )
        db.add_all([kibera, mukuru])
        db.flush()
        _seed_context_adjustments(db, kibera)
        _seed_context_adjustments(db, mukuru)

        # --- Learner A: ACTIVE SCREENING via the real gateway path ------------
        learner_a = Learner(
            school_id=kibera.id, cohort_id="2026-G4", gender="f",
            source=LearnerSource.active_screening,
        )
        db.add(learner_a)
        db.flush()
        db.add(
            ConsentRecord(
                learner_id=learner_a.id,
                guardian_identifier="guardian-a-pseudo",
                scope=ConsentScope.screening,
            )
        )
        db.flush()
        # Drive the genuine end-to-end flow: consent -> items -> responses ->
        # scoring -> flagging. (Uses the mock scorer unless ANTHROPIC_API_KEY set.)
        session_a, prompt = gateway.start_session(
            db, learner_id=learner_a.id, channel=Channel.whatsapp, language=Language.en
        )
        answers = [
            "She spends 60 and gets 96 so profit is 36. I multiplied 12 by 8 first.",
            "Net, because a net is the tool a fisherman needs like rain helps a farmer.",
            "42. The gaps go 4,6,8,10 so next gap is 12.",
            "No we cannot be sure, maybe she still passed another way.",
            "blue seven river chair mango. I made a little story to remember them.",
        ]
        for ans in answers:
            prompt = gateway.submit_response(
                db, session_id=session_a.id, raw_response=ans, response_time_ms=12000
            )
        db.flush()

        # --- Learner B: NOMINATION + a screened session that spikes -----------
        nom = nomination.submit_nomination(
            db,
            school_id=mukuru.id,
            nominator_role=NominatorRole.teacher,
            checklist_responses={
                "quick_grasp": True,
                "deep_questions": True,
                "uneven_performance": True,       # amber
                "underperforms_on_tests": True,   # amber
                "focus_difficulty": True,         # amber
                "creative_problem_solving": True,
            },
            gender="m",
            cohort_id="2026-G4",
            guardian_identifier="guardian-b-pseudo",
        )
        learner_b = db.get(Learner, nom.learner_id)
        db.add(
            ConsentRecord(
                learner_id=learner_b.id,
                guardian_identifier="guardian-b-pseudo",
                scope=ConsentScope.screening,
            )
        )
        db.flush()
        # Deterministic spike: strong pattern_recognition, uneven elsewhere.
        _insert_completed_scored_session(
            db,
            learner_b,
            {
                "numerical_reasoning": 55,
                "verbal_reasoning": 48,
                "pattern_recognition": 90,
                "logical_reasoning": 52,
                "working_memory": 44,
            },
        )

        # --- Learner C: PASSIVE SIGNAL + a moderate screened session ----------
        learner_c = Learner(
            school_id=kibera.id, cohort_id="2026-G4", gender=None,
            source=LearnerSource.passive_signal,
        )
        db.add(learner_c)
        db.flush()
        db.add(
            ConsentRecord(
                learner_id=learner_c.id,
                guardian_identifier="guardian-c-pseudo",
                scope=ConsentScope.secondary_use_of_school_records,
            )
        )
        db.flush()
        # A grades import + passive mining -> CandidateSignals (advisory only).
        imp = SchoolRecordImport(
            school_id=kibera.id,
            record_type=RecordType.grades,
            source_system=SourceSystem.school_local,
            raw_reference=str(SAMPLE_GRADES),
        )
        db.add(imp)
        db.flush()
        signals = passive.run_grade_variance_mining(db, imp.id)
        # For the demo, attach one signal to learner C so it shows as evidence on
        # their profile (in production the link forms when the invited child screens).
        if signals:
            signals[0].learner_id = learner_c.id
        _insert_completed_scored_session(
            db,
            learner_c,
            {
                "numerical_reasoning": 82,
                "verbal_reasoning": 40,
                "pattern_recognition": 78,
                "logical_reasoning": 45,
                "working_memory": 50,
            },
        )

        db.commit()
        print("Seed complete:")
        print(f"  schools: {kibera.name} (low_resource), {mukuru.name} (medium_resource)")
        print(f"  learner A (active_screening): {learner_a.id}  session {session_a.id}")
        print(f"  learner B (nomination):       {learner_b.id}  amber_flags={nom.amber_flag_count}")
        print(f"  learner C (passive_signal):   {learner_c.id}  passive_signals={len(signals)}")
        print("Open the dashboard to review flagged profiles.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
