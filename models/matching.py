from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.models import Base


class JobMatchDB(Base):
    __tablename__ = "job_matches"

    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "job_offer_id",
            name="uq_job_matches_candidate_job_offer",
        ),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id"),
        nullable=False,
        index=True,
    )

    job_offer_id: Mapped[str] = mapped_column(
        ForeignKey("job_offers.id"),
        nullable=False,
        index=True,
    )

    score_global: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    score_skills: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    score_experience: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    score_domain: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    matched_skills: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    inferred_skills: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    missing_skills: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    strengths: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    weaknesses: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )