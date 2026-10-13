"""Re-export every ORM model so `from app.models import X` works and so Alembic
autogenerate / metadata sees the full schema."""
from app.models.entities import (
    CandidateSignal,
    ChannelBinding,
    ConsentRecord,
    ContextAdjustment,
    DecisionAuditLog,
    DomainScore,
    FlagEvent,
    ItemResponse,
    Learner,
    NominationRecord,
    PanelReview,
    PortfolioSubmission,
    School,
    SchoolRecordImport,
    ScreeningSession,
    StaffUser,
)

__all__ = [
    "School",
    "Learner",
    "NominationRecord",
    "ScreeningSession",
    "ItemResponse",
    "DomainScore",
    "ContextAdjustment",
    "FlagEvent",
    "PanelReview",
    "SchoolRecordImport",
    "CandidateSignal",
    "ConsentRecord",
    "DecisionAuditLog",
    "PortfolioSubmission",
    "StaffUser",
    "ChannelBinding",
]
