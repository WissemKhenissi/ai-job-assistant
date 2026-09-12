from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.models import Base


# Statuts de suivi d'une candidature.
#
# Ils sont mis à jour manuellement depuis l'interface : la V1 ne lit
# aucune boîte mail, ce qui nécessiterait un connecteur externe
# explicitement hors périmètre.
APPLICATION_STATUSES = (
    "reperee",
    "generee",
    "envoyee",
    "relancee",
    "entretien",
    "refus",
    "acceptee",
    "sans_reponse",
)

APPLICATION_STATUS_LABELS = {
    "reperee": "Repérée",
    "generee": "Documents générés",
    "envoyee": "Candidature envoyée",
    "relancee": "Relancée",
    "entretien": "Entretien",
    "refus": "Refus",
    "acceptee": "Acceptée",
    "sans_reponse": "Sans réponse",
}


# L'avancement d'une candidature, en colonnes.
#
# Un statut décrit un fait ; une colonne décrit où en est la
# candidature. Les trois issues — acceptée, refus, sans réponse —
# partagent la dernière : ce qui compte alors est que le dossier est
# clos, pas la façon dont il l'est. Les garder séparées aurait fait
# trois colonnes presque toujours vides.
APPLICATION_COLUMNS = (
    ("Repérées", ("reperee",)),
    ("Documents prêts", ("generee",)),
    ("Postulées", ("envoyee", "relancee")),
    ("Entretien", ("entretien",)),
    ("Issue", ("acceptee", "refus", "sans_reponse")),
)


class ApplicationDB(Base):
    """
    Trace d'une candidature.

    Se relie à job_offers plutôt que de recopier le texte et le lien
    de l'annonce : l'offre reste la source unique de ses propres
    informations.

    Ne conserve que les chemins des fichiers produits, relatifs à la
    racine du projet, afin de rester valable si le dossier est
    déplacé.
    """

    __tablename__ = "applications"

    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "job_offer_id",
            name="uq_applications_candidate_job_offer",
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

    status: Mapped[str] = mapped_column(
        String,
        default="generee",
        nullable=False,
        index=True,
    )

    cv_docx_path: Mapped[str] = mapped_column(
        String,
        default="",
        nullable=False,
    )

    cv_pdf_path: Mapped[str] = mapped_column(
        String,
        default="",
        nullable=False,
    )

    letter_docx_path: Mapped[str] = mapped_column(
        String,
        default="",
        nullable=False,
    )

    letter_pdf_path: Mapped[str] = mapped_column(
        String,
        default="",
        nullable=False,
    )

    # Suivi manuel : dates d'envoi, de réponse, notes libres.
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    notes: Mapped[str] = mapped_column(
        Text,
        default="",
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
