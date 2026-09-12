"""
Suivi des candidatures.

Une candidature est enregistrée automatiquement dès qu'un CV et une
lettre ont été générés pour une offre : ce qui a été produit doit
rester retrouvable.

Les statuts suivants (envoyée, entretien, refus...) sont mis à jour
manuellement depuis l'interface. La V1 ne lit aucune boîte mail.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from database.db import SessionLocal
from models.application import (
    APPLICATION_STATUS_LABELS,
    APPLICATION_STATUSES,
    ApplicationDB,
)
from models.job import JobOfferDB


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _chemin_relatif(chemin: Path | str | None) -> str:
    """
    Convertit un chemin en chemin relatif à la racine du projet.

    Stocker un chemin absolu rendrait le suivi invalide dès que le
    dossier du projet est déplacé ou synchronisé sur une autre
    machine.
    """

    if not chemin:
        return ""

    chemin = Path(chemin)

    try:
        return chemin.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        # Fichier hors du projet : on conserve le chemin tel quel
        # plutôt que d'inventer une localisation.
        return chemin.as_posix()


@dataclass
class ApplicationSummary:
    """Vue d'une candidature, offre incluse, pour l'affichage."""

    id: str
    job_offer_id: str
    job_offer_title: str
    company: str
    status: str
    status_label: str
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    notes: str
    cv_docx_path: str
    cv_pdf_path: str
    letter_docx_path: str
    letter_pdf_path: str

    @property
    def a_ses_documents(self) -> bool:
        return bool(
            (self.cv_docx_path or self.cv_pdf_path)
            and (self.letter_docx_path or self.letter_pdf_path)
        )


def record_application(
    candidate_id: str,
    job_offer_id: str,
    cv_docx_path: Path | str | None = None,
    cv_pdf_path: Path | str | None = None,
    letter_docx_path: Path | str | None = None,
    letter_pdf_path: Path | str | None = None,
    statut_initial: str = "generee",
) -> str:
    """
    Crée ou met à jour la trace d'une candidature.

    Idempotent : régénérer les documents d'une offre met à jour la
    candidature existante au lieu d'en créer une seconde. Le statut
    de suivi déjà saisi par l'utilisateur n'est jamais écrasé.

    `statut_initial` ne vaut qu'à la création. Il existe parce que le
    suivi ne commençait qu'après la génération des documents : une
    annonce repérée, ou une candidature envoyée à la main, ne pouvait
    pas être suivie. « reperee » ouvre le cycle plus tôt.

    Une exception à la règle du statut préservé : produire des
    documents pour une annonce simplement repérée la fait passer à
    « generee ». Laisser « Repérée » sur une candidature dont le CV
    est prêt serait faux, et c'est le seul cas où le système en sait
    plus que ce que l'utilisateur a saisi.

    Retourne l'identifiant de la candidature.
    """

    db = SessionLocal()

    try:

        application = (
            db.query(ApplicationDB)
            .filter(
                ApplicationDB.candidate_id == candidate_id,
                ApplicationDB.job_offer_id == job_offer_id,
            )
            .one_or_none()
        )

        if application is None:

            application = ApplicationDB(
                id=f"application-{uuid4()}",
                candidate_id=candidate_id,
                job_offer_id=job_offer_id,
                status=statut_initial,
            )

            db.add(application)

        # Seuls les chemins fournis sont mis à jour : régénérer un
        # seul document ne doit pas effacer la trace de l'autre.
        documents_produits = False

        for champ, valeur in (
            ("cv_docx_path", cv_docx_path),
            ("cv_pdf_path", cv_pdf_path),
            ("letter_docx_path", letter_docx_path),
            ("letter_pdf_path", letter_pdf_path),
        ):

            if valeur is not None:
                setattr(application, champ, _chemin_relatif(valeur))
                documents_produits = True

        # La seule promotion automatique, et elle ne remonte jamais
        # au-delà : une candidature déjà envoyée ou en entretien
        # garde son statut si on régénère ses documents.
        if documents_produits and application.status == "reperee":
            application.status = "generee"

        db.commit()

        return application.id

    except Exception:

        db.rollback()

        raise

    finally:

        db.close()


def get_application(
    candidate_id: str,
    job_offer_id: str,
) -> ApplicationSummary | None:
    """
    La candidature d'un candidat pour une offre, si elle existe.

    Permet à l'écran d'analyse de savoir si l'annonce est déjà suivie
    plutôt que de proposer de la suivre une seconde fois.
    """

    for candidature in list_applications(candidate_id):

        if candidature.job_offer_id == job_offer_id:
            return candidature

    return None


def list_applications(
    candidate_id: str,
) -> list[ApplicationSummary]:
    """Candidatures d'un candidat, de la plus récente à la plus ancienne."""

    db = SessionLocal()

    try:

        rows = (
            db.query(ApplicationDB, JobOfferDB)
            .join(
                JobOfferDB,
                ApplicationDB.job_offer_id == JobOfferDB.id,
            )
            .filter(ApplicationDB.candidate_id == candidate_id)
            .order_by(ApplicationDB.created_at.desc())
            .all()
        )

        return [
            ApplicationSummary(
                id=application.id,
                job_offer_id=application.job_offer_id,
                job_offer_title=job_offer.title or "",
                company=job_offer.company or "",
                status=application.status,
                status_label=APPLICATION_STATUS_LABELS.get(
                    application.status,
                    application.status,
                ),
                created_at=application.created_at,
                updated_at=application.updated_at,
                sent_at=application.sent_at,
                notes=application.notes or "",
                cv_docx_path=application.cv_docx_path or "",
                cv_pdf_path=application.cv_pdf_path or "",
                letter_docx_path=application.letter_docx_path or "",
                letter_pdf_path=application.letter_pdf_path or "",
            )
            for application, job_offer in rows
        ]

    finally:

        db.close()


def update_application_status(
    application_id: str,
    status: str,
    notes: str | None = None,
    sent_at: datetime | None = None,
) -> None:
    """
    Met à jour le suivi d'une candidature.

    Saisie manuelle uniquement : rien dans la V1 ne déduit un statut
    automatiquement.
    """

    if status not in APPLICATION_STATUSES:
        raise ValueError(
            f"Statut inconnu : {status!r}. "
            f"Attendu parmi {APPLICATION_STATUSES}."
        )

    db = SessionLocal()

    try:

        application = db.get(ApplicationDB, application_id)

        if application is None:
            raise ValueError(
                f"Candidature introuvable : {application_id}"
            )

        application.status = status

        if notes is not None:
            application.notes = notes

        if sent_at is not None:
            application.sent_at = sent_at

        db.commit()

    except Exception:

        db.rollback()

        raise

    finally:

        db.close()
