from sqlalchemy.orm import Session

from database.db import engine
from database.models import EvidenceDB


def create_evidence():

    evidence_list = [

        EvidenceDB(
            id="evidence-001",
            candidate_id="candidate-001",
            skill_id="skill-project-management",
            experience_id="ticketis",
            achievement_id="achievement-001",
            evidence_type="Projet digital",
            description=(
                "Pilotage de la conception et du lancement "
                "d'un dispositif serviciel de bout en bout, "
                "avec coordination des équipes IT, UX, UI, "
                "juridique et de 4 partenaires externes."
            ),
            metric=(
                "4 partenaires ; environ 10 itérations ; "
                "mise en production en 2 à 4 semaines ; "
                "100 kEUR de CA sur 18 mois."
            ),
            context=(
                "Création d'un nouveau produit digital "
                "dans un environnement e-commerce."
            ),
        ),

        EvidenceDB(
            id="evidence-002",
            candidate_id="candidate-001",
            skill_id="skill-process-improvement",
            experience_id="ticketis",
            achievement_id="achievement-003",
            evidence_type="Amélioration de processus",
            description=(
                "Conception et déploiement d'un système partagé "
                "de suivi des campagnes afin de centraliser "
                "les tâches, deadlines, statuts et blocages."
            ),
            metric=(
                "4 à 5 utilisateurs ; gain estimé de "
                "2 à 4 heures par campagne."
            ),
            context=(
                "Process initialement basé principalement "
                "sur des échanges par e-mail."
            ),
        ),

        EvidenceDB(
            id="evidence-003",
            candidate_id="candidate-001",
            skill_id="skill-automation",
            experience_id="ticketis",
            achievement_id="achievement-002",
            evidence_type="Automatisation",
            description=(
                "Automatisation d'un processus administratif "
                "répétitif grâce à Excel et aux macros."
            ),
            metric=(
                "Temps de traitement réduit de "
                "30-60 minutes à 2-5 minutes, "
                "soit environ 90 % de réduction."
            ),
            context=(
                "Industrialisation de la création "
                "des ordres d'insertion."
            ),
        ),

        EvidenceDB(
            id="evidence-004",
            candidate_id="candidate-001",
            skill_id="skill-stakeholder-management",
            experience_id="ticketis",
            achievement_id="achievement-001",
            evidence_type="Coordination transverse",
            description=(
                "Coordination de parties prenantes internes "
                "et externes dans le cadre de la création "
                "d'un nouveau produit digital."
            ),
            metric=(
                "Coordination de 4 partenaires externes "
                "et plusieurs équipes internes."
            ),
            context=(
                "Projet impliquant IT, UX, UI, juridique, "
                "marketing et partenaires."
            ),
        ),

    ]

    with Session(engine) as session:

        for evidence in evidence_list:

            existing = session.get(
                EvidenceDB,
                evidence.id
            )

            if existing:
                print(
                    f"{evidence.id} existe déjà."
                )
                continue

            session.add(evidence)

        session.commit()

        print(
            f"{len(evidence_list)} preuves traitées."
        )


if __name__ == "__main__":
    create_evidence()