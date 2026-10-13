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
    ItemResponse,
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


# Realistic, presentable evidence notes per domain and performance band. These
# are illustrative demo profiles (the "Demo mode" banner discloses this); the text
# reads like a scorer's note so the dashboard is legible in a walkthrough.
_EVIDENCE = {
    "numerical_reasoning": {
        "high": "Added the coins to 46, said yes, and gave 6 shillings change; also chose exact coins to hand over (20+10+10). Flexible decomposition.",
        "mid": "Reached the right total but the change figure was off by a coin.",
        "low": "Said yes without totalling the coins, so the method was not shown.",
    },
    "verbal_reasoning": {
        "high": "Ordered the growth pictures correctly (B D A C) and narrated cause and effect ('it needs rain, then it sprouts').",
        "mid": "Correct order, with a short list-like story.",
        "low": "Two pictures out of order; story described pictures one by one.",
    },
    "pattern_recognition": {
        "high": "Chose C and named both rules: row sets the shape, column sets the count.",
        "mid": "Chose C but explained only the counting rule.",
        "low": "Chose A (right shape, wrong count), so the column rule was missed.",
    },
    "logical_reasoning": {
        "high": "Placed Fatuma in the middle and explained the elimination: Otieno can only go on the right.",
        "mid": "Right seating, without explaining why.",
        "low": "Put Otieno in the middle, so the 'not next to' clue was not tracked.",
    },
    "working_memory": {
        "high": "Spotted the new item (cup) and named the missing one (key); described picturing the row left to right.",
        "mid": "Spotted the new item without a described strategy.",
        "low": "Chose an item that was in the first picture.",
    },
}
# Short, plausible learner answers to the v2 core items, keyed by domain.
_DEMO_ANSWERS = {
    "numerical_reasoning": "Yes. 20 + 10 + 10 + 5 + 1 is 46, so 6 shillings are left. I would give the 20 and the two 10s.",
    "verbal_reasoning": "B D A C. First the seed is planted, then rain makes it sprout, then it grows leaves, then it is tall maize with a cob.",
    "pattern_recognition": "C, three triangles. Each row keeps the same shape and each column adds one more.",
    "logical_reasoning": "Fatuma. Wanjiru is on the left, and Otieno cannot sit next to her, so he must be on the right.",
    "working_memory": "B, the cup. The key was not there any more.",
}
_DEMO_MODEL_VERSION = "screening-demo-v1"


def _band(score: int) -> str:
    return "high" if score >= 70 else "mid" if score >= 45 else "low"


def _insert_completed_scored_session(
    db, learner: Learner, domain_scores: dict[str, int]
) -> ScreeningSession:
    """A completed demo session with realistic per-domain evidence and a full set
    of responses, so the panel dashboard reads professionally in a walkthrough.
    Uses a demo scoring version; live screenings use the real Claude model."""
    session = ScreeningSession(
        learner_id=learner.id,
        channel=Channel.whatsapp,
        language=Language.en,
        status="completed",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.flush()
    for item in items.all_items():
        db.add(
            ItemResponse(
                session_id=session.id,
                item_id=item.id,
                raw_response=_DEMO_ANSWERS.get(item.domain, "Answered."),
                response_time_ms=11000,
            )
        )
    for domain, score in domain_scores.items():
        db.add(
            DomainScore(
                session_id=session.id,
                domain=domain,
                score=score,
                evidence_text=_EVIDENCE.get(domain, {}).get(_band(score), "Answer recorded."),
                scoring_model_version=_DEMO_MODEL_VERSION,
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
        # Uneven profile: strong numeracy, weaker verbal and memory.
        session_a = _insert_completed_scored_session(
            db,
            learner_a,
            {
                "numerical_reasoning": 84,
                "verbal_reasoning": 41,
                "pattern_recognition": 63,
                "logical_reasoning": 58,
                "working_memory": 47,
            },
        )

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
