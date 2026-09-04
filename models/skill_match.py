from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.models import Base


class JobSkillMatchDB(Base):
    """
    Détail du matching, compétence par compétence.

    JobMatchDB ne conserve que des listes de noms et des scores
    agrégés : le score individuel, l'explication et les preuves
    étaient perdus dès la fin de l'analyse. Cette table les
    historise, ce qui permet de justifier a posteriori pourquoi une
    compétence a été jugée prouvée, déclarée, déduite ou manquante.
    """

    __tablename__ = "job_skill_matches"

    __table_args__ = (
        UniqueConstraint(
            "job_match_id",
            "skill",
            name="uq_job_skill_matches_match_skill",
        ),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    job_match_id: Mapped[str] = mapped_column(
        ForeignKey("job_matches.id"),
        nullable=False,
        index=True,
    )

    # Compétence telle que demandée par l'annonce.
    skill: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    # Forme canonique normalisée, pour agréger d'une annonce à l'autre
    # malgré les variations d'écriture.
    canonical_skill: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    # proven / declared / inferred / missing
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    # Ce que l'annonce demande de cette compétence :
    # essentielle / souhaitee / mention.
    #
    # Distinct du statut, qui décrit le candidat. Un écart n'a de
    # sens que croisé avec ce niveau : « Jira manquant, cité en
    # exemple » et « gestion de projet manquante, exigée » ne
    # racontent pas la même candidature.
    importance: Mapped[str] = mapped_column(
        String,
        default="souhaitee",
        server_default="souhaitee",
        nullable=False,
        index=True,
    )

    score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    explanation: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )

    evidence: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
