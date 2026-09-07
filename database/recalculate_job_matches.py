from __future__ import annotations

from database.db import SessionLocal
from models.job import JobOfferDB
from services.job_requirements_service import extract_required_skills
from services.matching import analyze_and_save_job_match


def recalculate_all_job_matches() -> None:
    db = SessionLocal()

    try:
        job_offers = (
            db.query(JobOfferDB)
            .order_by(JobOfferDB.created_at.asc())
            .all()
        )

        if not job_offers:
            print("Aucune annonce trouvée.")
            return

        print()
        print("=" * 70)
        print("RECALCUL DES MATCHINGS")
        print("=" * 70)

        for job_offer in job_offers:

            print()
            print(f"Annonce : {job_offer.title}")
            print(f"ID      : {job_offer.id}")

            text = "\n".join(
                [
                    job_offer.title or "",
                    job_offer.description or "",
                ]
            )

            required_skills = extract_required_skills(text)

            print(
                f"Compétences détectées : "
                f"{len(required_skills)}"
            )

            if required_skills:
                print(
                    " → "
                    + ", ".join(required_skills)
                )
            else:
                print(" → Aucune compétence détectée.")

            if not required_skills:
                print("MATCHING IGNORÉ")
                continue

            # Le candidat actuellement utilisé
            # dans l'application.
            candidate_id = "candidate-demo"

            try:
                result = analyze_and_save_job_match(
                    candidate_id=candidate_id,
                    job_offer_id=job_offer.id,
                    required_skills=required_skills,
                )

                print(
                    f"Score : {result.score_global:.1f}/100"
                )

                print(
                    f"  Prouvées  : "
                    f"{len(result.matched_skills)}"
                )

                print(
                    f"  Déduites  : "
                    f"{len(result.inferred_skills)}"
                )

                print(
                    f"  Manquantes: "
                    f"{len(result.missing_skills)}"
                )

            except Exception as error:
                print(
                    f"ERREUR lors du matching : {error}"
                )

    finally:
        db.close()

    print()
    print("=" * 70)
    print("RECALCUL TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    recalculate_all_job_matches()