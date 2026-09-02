from sqlalchemy.orm import Session

from database.db import engine
from database.models import SkillDB


def create_skills():

    skills = [

        SkillDB(
            id="skill-project-management",
            candidate_id="candidate-001",
            name="Gestion de projet",
            category="Project Management",
            level="Avancé",
            years_experience=7,
            description=(
                "Pilotage de projets digitaux, coordination "
                "des parties prenantes, suivi des actions, "
                "gestion des priorités et résolution des blocages."
            ),
        ),

        SkillDB(
            id="skill-product-discovery",
            candidate_id="candidate-001",
            name="Product Discovery",
            category="Product Management",
            level="Intermédiaire",
            years_experience=3,
            description=(
                "Identification des besoins business et clients, "
                "recherche d'opportunités, identification de quick wins "
                "et conception de solutions à forte valeur."
            ),
        ),

        SkillDB(
            id="skill-stakeholder-management",
            candidate_id="candidate-001",
            name="Stakeholder Management",
            category="Soft Skills",
            level="Avancé",
            years_experience=7,
            description=(
                "Coordination de parties prenantes internes et externes, "
                "gestion des attentes, communication, arbitrage "
                "et recherche de consensus."
            ),
        ),

        SkillDB(
            id="skill-business-development",
            candidate_id="candidate-001",
            name="Business Development",
            category="Business",
            level="Avancé",
            years_experience=7,
            description=(
                "Développement de nouvelles offres, identification "
                "d'opportunités commerciales, proposition de solutions "
                "et développement du chiffre d'affaires."
            ),
        ),

        SkillDB(
            id="skill-process-improvement",
            candidate_id="candidate-001",
            name="Amélioration continue",
            category="Project Management",
            level="Avancé",
            years_experience=7,
            description=(
                "Identification des inefficacités, optimisation "
                "des processus, automatisation et amélioration "
                "de la productivité."
            ),
        ),

        SkillDB(
            id="skill-excel",
            candidate_id="candidate-001",
            name="Microsoft Excel",
            category="Tools",
            level="Avancé",
            years_experience=7,
            description=(
                "Utilisation avancée d'Excel pour le suivi, "
                "le reporting, l'automatisation et les processus."
            ),
        ),

        SkillDB(
            id="skill-automation",
            candidate_id="candidate-001",
            name="Automatisation",
            category="Technical",
            level="Intermédiaire",
            years_experience=5,
            description=(
                "Automatisation de tâches répétitives et "
                "industrialisation de processus."
            ),
        ),

        SkillDB(
            id="skill-ecommerce",
            candidate_id="candidate-001",
            name="E-commerce",
            category="Domain",
            level="Avancé",
            years_experience=7,
            description=(
                "Expérience dans un environnement e-commerce "
                "et dans l'exploitation de dispositifs digitaux."
            ),
        ),

        SkillDB(
            id="skill-adtech",
            candidate_id="candidate-001",
            name="Adtech",
            category="Domain",
            level="Expert",
            years_experience=7,
            description=(
                "Expertise des dispositifs publicitaires digitaux, "
                "ad servers, ciblage, tracking et monétisation."
            ),
        ),

        SkillDB(
            id="skill-data",
            candidate_id="candidate-001",
            name="Data Marketing",
            category="Data",
            level="Intermédiaire",
            years_experience=5,
            description=(
                "Utilisation de données d'audience, first-party data, "
                "retargeting, lookalike et ciblage comportemental."
            ),
        ),

    ]

    with Session(engine) as session:

        for skill in skills:

            existing = session.get(
                SkillDB,
                skill.id
            )

            if existing:
                print(
                    f"{skill.name} existe déjà."
                )
                continue

            session.add(skill)

        session.commit()

        print(
            f"{len(skills)} compétences traitées."
        )


if __name__ == "__main__":
    create_skills()