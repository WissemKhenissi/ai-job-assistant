from database.db import SessionLocal
from models.job import JobOfferDB


def save_job_offer(
    job_offer_id: str,
    title: str,
    description: str,
    company: str = "",
    location: str = "",
    contract_type: str = "",
    remote_policy: str = "",
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