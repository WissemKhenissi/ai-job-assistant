from database.db import SessionLocal
from models.job import JobOfferDB


def get_job_offer_text(job_offer_id: str) -> str:
    """
    Texte complet (titre + description) d'une offre, tel qu'analysé
    par le moteur de matching — utilisé par la reformulation IA pour
    aligner le vocabulaire sur celui de l'annonce.
    """

    db = SessionLocal()

    try:

        job_offer = db.get(JobOfferDB, job_offer_id)

        if job_offer is None:
            return ""

        return "\n".join(
            [job_offer.title or "", job_offer.description or ""]
        )

    finally:

        db.close()


def save_job_offer(
    job_offer_id: str,
    title: str,
    description: str,
    company: str = "",
    location: str = "",
    contract_type: str = "",
    remote_policy: str = "",
    remote_details: str = "",
    salary: str = "",
    url: str = "",
    source: str = "manual",
    status: str = "selected",
) -> str:
    db = SessionLocal()

    try:
        job_offer = db.get(JobOfferDB, job_offer_id)

        if job_offer is None:
            job_offer = JobOfferDB(
                id=job_offer_id,
                title=title,
                description=description,
            )
            db.add(job_offer)

        job_offer.title = title
        job_offer.description = description
        job_offer.company = company
        job_offer.location = location
        job_offer.contract_type = contract_type
        job_offer.remote_policy = remote_policy
        job_offer.remote_details = remote_details
        job_offer.salary = salary
        job_offer.url = url
        job_offer.source = source
        job_offer.status = status

        db.commit()

        return job_offer.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_job_offer_summary(job_offer_id: str) -> dict | None:
    """
    Champs d'affichage d'une offre (catégorisation incluse), en dict
    de primitives — jamais l'objet ORM lui-même, pour ne pas exposer
    une instance détachée de sa session en dehors de ce module.
    """

    db = SessionLocal()

    try:

        job_offer = db.get(JobOfferDB, job_offer_id)

        if job_offer is None:
            return None

        return {
            "title": job_offer.title or "",
            "company": job_offer.company or "",
            "location": job_offer.location or "",
            "contract_type": job_offer.contract_type or "",
            "remote_policy": job_offer.remote_policy or "",
            "remote_details": job_offer.remote_details or "",
        }

    finally:

        db.close()