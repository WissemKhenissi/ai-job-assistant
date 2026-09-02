from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.models import Base


class JobOfferDB(Base):

    __tablename__ = "job_offers"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    title: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    company: Mapped[str] = mapped_column(
        String,
        default=""
    )

    location: Mapped[str] = mapped_column(
        String,
        default=""
    )

    contract_type: Mapped[str] = mapped_column(
        String,
        default=""
    )

    remote_policy: Mapped[str] = mapped_column(
        String,
        default=""
    )

    # Précision libre sur le télétravail (ex. "2 jours/semaine"),
    # quand l'annonce le dit explicitement — remote_policy reste la
    # catégorie grossière (Sur site / Hybride / Télétravail complet),
    # ce champ porte le détail que ces trois catégories ne capturent
    # pas.
    remote_details: Mapped[str] = mapped_column(
        String,
        default=""
    )

    salary: Mapped[str] = mapped_column(
        String,
        default=""
    )

    url: Mapped[str] = mapped_column(
        String,
        default=""
    )

    source: Mapped[str] = mapped_column(
        String,
        default=""
    )

    description: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    status: Mapped[str] = mapped_column(
        String,
        default="new"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )