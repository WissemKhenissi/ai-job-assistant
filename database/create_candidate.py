from sqlalchemy.orm import Session

from database.db import engine
from database.models import CandidateDB


def create_candidate():

    with Session(engine) as session:

        candidate = session.get(
            CandidateDB,
            "candidate-001"
        )

        if candidate:
            print("Le candidat existe déjà.")
            return

        candidate = CandidateDB(
            id="candidate-001",
            first_name="Wissem",
            last_name="Khenissi",
            email="",
            phone="",
            location="France",
            linkedin_url="",
            portfolio_url="",
            summary=(
                "Profil hybride Business / Digital / Produit, "
                "avec plus de 7 ans d'expérience en environnements "
                "e-commerce et adtech."
            )
        )

        session.add(candidate)
        session.commit()

        print("Candidat créé avec succès.")


if __name__ == "__main__":
    create_candidate()