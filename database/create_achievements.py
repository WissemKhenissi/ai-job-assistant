from sqlalchemy.orm import Session

from database.db import engine
from database.models import AchievementDB


def create_achievements():

    achievements = [

        AchievementDB(
            id="achievement-001",
            experience_id="ticketis",
            title="Création d'une page servicielle",
            situation=(
                "Identification d'une opportunité de proposer "
                "des services complémentaires après l'achat "
                "d'un billet de spectacle."
            ),
            action=(
                "Initiation et conception du projet, recherche "
                "de partenaires, construction du business model, "
                "coordination des équipes et conception du dispositif."
            ),
            result=(
                "Création d'un nouveau produit digital générant "
                "environ 100 kEUR de chiffre d'affaires sur les "
                "18 premiers mois."
            ),
            metrics=(
                "100 kEUR de CA sur 18 mois ; "
                "4 partenaires ; environ 10 itérations ; "
                "mise en production en 2 à 4 semaines."
            ),
            description=(
                "Conception d'un dispositif serviciel permettant "
                "de proposer des services complémentaires aux "
                "clients après leur achat."
            ),
        ),

        AchievementDB(
            id="achievement-002",
            experience_id="ticketis",
            title="Automatisation des ordres d'insertion",
            situation=(
                "Création manuelle des ordres d'insertion nécessitant "
                "environ 30 à 60 minutes par opération."
            ),
            action=(
                "Conception d'une automatisation Excel basée sur "
                "des macros afin d'industrialiser le processus."
            ),
            result=(
                "Réduction du temps de traitement à environ "
                "2 à 5 minutes."
            ),
            metrics=(
                "Environ 90 % de réduction du temps de traitement."
            ),
            description=(
                "Automatisation d'un processus administratif répétitif "
                "afin d'améliorer la productivité et standardiser "
                "le traitement."
            ),
        ),

        AchievementDB(
            id="achievement-003",
            experience_id="ticketis",
            title="Mise en place d'un système de suivi des campagnes",
            situation=(
                "Suivi des campagnes principalement réalisé par "
                "e-mails et échanges entre collaborateurs, avec "
                "un risque de perte d'information et de visibilité "
                "sur les deadlines."
            ),
            action=(
                "Création d'un fichier Excel partagé permettant "
                "de centraliser les campagnes, tâches, deadlines, "
                "blocages et statuts."
            ),
            result=(
                "Adoption du système par l'équipe et transformation "
                "en process de suivi collectif."
            ),
            metrics=(
                "4 à 5 utilisateurs ; gain estimé de 2 à 4 heures "
                "par campagne."
            ),
            description=(
                "Optimisation du processus de gestion et de suivi "
                "des campagnes publicitaires."
            ),
        ),
    ]

    with Session(engine) as session:

        for achievement in achievements:

            existing = session.get(
                AchievementDB,
                achievement.id
            )

            if existing:
                print(
                    f"{achievement.id} existe déjà."
                )
                continue

            session.add(achievement)

        session.commit()

        print(
            f"{len(achievements)} réalisations traitées."
        )


if __name__ == "__main__":
    create_achievements()