from __future__ import annotations

import json

from database.db import SessionLocal
from database.models import SkillCatalogDB


# ============================================================
# REFERENTIEL DES COMPETENCES
# ============================================================

SKILLS = [

    # ========================================================
    # PRODUCT
    # ========================================================

    {
        "id": "catalog-product-management",
        "canonical_name": "Product Management",
        "category": "Product",
        "subcategory": "Product Management",
        "description": (
            "Gestion globale d'un produit de la définition "
            "de sa vision et de sa stratégie jusqu'à sa livraison, "
            "son adoption, son amélioration continue et la mesure "
            "de sa valeur business et utilisateur."
        ),
        "aliases": [
            "Product Management",
            "Product Manager",
            "Gestion de produit",
            "Management produit",
        ],
        "parent": None,
        "related_skills": [
            "Product Discovery",
            "Product Strategy",
            "Product Delivery",
            "Roadmap produit",
        ],
    },

    {
        "id": "catalog-product-discovery",
        "canonical_name": "Product Discovery",
        "category": "Product",
        "subcategory": "Discovery",
        "description": (
            "Identification et compréhension des besoins "
            "utilisateurs, problèmes, opportunités et usages "
            "afin de définir et valider les problèmes à résoudre "
            "avant ou pendant la conception d'un produit."
        ),
        "aliases": [
            "Product Discovery",
            "Discovery produit",
            "Discovery",
            "Découverte produit",
            "Discovery phase",
        ],
        "parent": "catalog-product-management",
        "related_skills": [
            "User Research",
            "Product Strategy",
            "Experimentation",
            "UX",
        ],
    },

    {
        "id": "catalog-user-research",
        "canonical_name": "User Research",
        "category": "Product",
        "subcategory": "Discovery",
        "description": (
            "Recherche et analyse des besoins, comportements, "
            "attentes, usages et problèmes des utilisateurs "
            "à travers des entretiens, sondages, observations, "
            "analytics et autres méthodes qualitatives ou "
            "quantitatives."
        ),
        "aliases": [
            "User Research",
            "Recherche utilisateur",
            "Analyse utilisateur",
            "Comportement utilisateur",
            "Étude utilisateur",
            "Customer Research",
            "Recherche utilisateurs",
        ],
        "parent": "catalog-product-discovery",
        "related_skills": [
            "Product Discovery",
            "UX",
            "Data Analysis",
            "Experimentation",
        ],
    },

    {
        "id": "catalog-experimentation",
        "canonical_name": "Experimentation",
        "category": "Product",
        "subcategory": "Discovery",
        "description": (
            "Conception et réalisation d'expérimentations, "
            "tests, prototypes, tests utilisateurs ou A/B tests "
            "afin de valider des hypothèses produit et mesurer "
            "leur impact."
        ),
        "aliases": [
            "Expérimentation",
            "A/B Testing",
            "AB Testing",
            "Testing",
            "Tests",
            "Experiment",
            "Tests utilisateurs",
            "Experimentation",
        ],
        "parent": "catalog-product-discovery",
        "related_skills": [
            "Product Discovery",
            "User Research",
            "Data Analysis",
            "UX",
        ],
    },

    {
        "id": "catalog-product-strategy",
        "canonical_name": "Product Strategy",
        "category": "Product",
        "subcategory": "Strategy",
        "description": (
            "Définition de la stratégie produit, de la vision, "
            "des objectifs, de la proposition de valeur et des "
            "orientations permettant de maximiser la valeur "
            "business et utilisateur."
        ),
        "aliases": [
            "Product Strategy",
            "Stratégie produit",
            "Strategie produit",
            "Strategie Product",
            "Product Strategy Management",
        ],
        "parent": "catalog-product-management",
        "related_skills": [
            "Product Management",
            "Product Discovery",
            "Roadmap produit",
            "Priorisation",
        ],
    },

    {
        "id": "catalog-roadmap",
        "canonical_name": "Roadmap produit",
        "category": "Product",
        "subcategory": "Strategy",
        "description": (
            "Définition, planification, communication et suivi "
            "de la trajectoire d'évolution d'un produit en fonction "
            "des objectifs stratégiques, priorités, contraintes "
            "et opportunités."
        ),
        "aliases": [
            "Product Roadmap",
            "Roadmap",
            "Roadmap produit",
            "Product roadmap management",
        ],
        "parent": "catalog-product-strategy",
        "related_skills": [
            "Product Strategy",
            "Priorisation",
            "Product Management",
            "Backlog Management",
        ],
    },

    {
        "id": "catalog-product-delivery",
        "canonical_name": "Product Delivery",
        "category": "Product",
        "subcategory": "Delivery",
        "description": (
            "Pilotage de la réalisation et de la livraison "
            "d'un produit, coordination des équipes, suivi "
            "des itérations, qualité, mise en production et "
            "création de valeur."
        ),
        "aliases": [
            "Product Delivery",
            "Delivery produit",
            "Product delivery management",
        ],
        "parent": "catalog-product-management",
        "related_skills": [
            "Agile / Scrum",
            "Backlog Management",
            "Gestion de projet",
            "Product Management",
        ],
    },

    {
        "id": "catalog-priorisation",
        "canonical_name": "Priorisation",
        "category": "Product",
        "subcategory": "Delivery",
        "description": (
            "Arbitrage entre différentes opportunités, "
            "fonctionnalités ou tâches selon leur valeur "
            "business, valeur utilisateur, coût, effort, "
            "urgence, impact et faisabilité."
        ),
        "aliases": [
            "Priorisation",
            "Prioritization",
            "Prioritize",
            "Gestion des priorités",
            "Priorisation produit",
            "Priorisation des fonctionnalités",
        ],
        "parent": "catalog-product-delivery",
        "related_skills": [
            "Product Strategy",
            "Product Management",
            "Backlog Management",
            "Roadmap produit",
        ],
    },

    {
        "id": "catalog-backlog",
        "canonical_name": "Backlog Management",
        "category": "Product",
        "subcategory": "Delivery",
        "description": (
            "Gestion, organisation, qualification, priorisation "
            "et suivi du backlog produit ou projet afin de "
            "préparer les travaux à réaliser et maximiser "
            "la valeur délivrée."
        ),
        "aliases": [
            "Backlog Management",
            "Backlog",
            "Product backlog",
            "Gestion du backlog",
            "Backlog produit",
            "Product Backlog Management",
        ],
        "parent": "catalog-product-delivery",
        "related_skills": [
            "Priorisation",
            "Agile / Scrum",
            "Product Delivery",
            "Roadmap produit",
        ],
    },

    # ========================================================
    # PROJECT MANAGEMENT
    # ========================================================

    {
        "id": "catalog-project-management",
        "canonical_name": "Gestion de projet",
        "category": "Project Management",
        "subcategory": "Project Management",
        "description": (
            "Planification, organisation, coordination, "
            "pilotage et suivi d'un projet afin d'atteindre "
            "des objectifs définis dans le respect des délais, "
            "ressources, coûts, risques et contraintes."
        ),
        "aliases": [
            "Gestion de projet",
            "Project Management",
            "Pilotage de projet",
            "Conduite de projet",
            "Project Delivery",
        ],
        "parent": None,
        "related_skills": [
            "Agile / Scrum",
            "Stakeholder Management",
            "Coordination transverse",
            "Priorisation",
        ],
    },

    {
        "id": "catalog-agile",
        "canonical_name": "Agile / Scrum",
        "category": "Project Management",
        "subcategory": "Agile",
        "description": (
            "Méthodes de gestion et de développement itératives "
            "reposant notamment sur les sprints, l'amélioration "
            "continue, la livraison incrémentale, la collaboration "
            "d'équipe et l'adaptation aux changements."
        ),
        "aliases": [
            "Agile",
            "Scrum",
            "Agile Scrum",
            "Méthodologie Agile",
            "Agile methodology",
            "Sprints",
            "Sprint",
        ],
        "parent": "catalog-project-management",
        "related_skills": [
            "Gestion de projet",
            "Product Delivery",
            "Backlog Management",
            "Kanban",
        ],
    },

    {
        "id": "catalog-kanban",
        "canonical_name": "Kanban",
        "category": "Project Management",
        "subcategory": "Agile",
        "description": (
            "Méthode de gestion du travail basée sur la "
            "visualisation des tâches, la limitation du travail "
            "en cours, la gestion des flux et l'amélioration "
            "continue des processus."
        ),
        "aliases": [
            "Kanban",
        ],
        "parent": "catalog-project-management",
        "related_skills": [
            "Agile / Scrum",
            "Gestion de projet",
            "Backlog Management",
        ],
    },

    {
        "id": "catalog-stakeholder-management",
        "canonical_name": "Stakeholder Management",
        "category": "Management",
        "subcategory": "Stakeholders",
        "description": (
            "Gestion et coordination des parties prenantes "
            "internes et externes, équipes métiers, équipes "
            "techniques, clients et partenaires afin d'assurer "
            "l'alignement des objectifs, la communication et "
            "la bonne réalisation des projets."
        ),
        "aliases": [
            "Stakeholder Management",
            "Stakeholders Management",
            "Gestion des parties prenantes",
            "Gestion des stakeholders",
            "Stakeholders",
            "Stakeholder",
        ],
        "parent": "catalog-project-management",
        "related_skills": [
            "Gestion de projet",
            "Coordination transverse",
            "Communication",
            "Product Management",
        ],
    },

    # ========================================================
    # DATA / AI
    # ========================================================

    {
        "id": "catalog-data-analysis",
        "canonical_name": "Data Analysis",
        "category": "Data",
        "subcategory": "Analytics",
        "description": (
            "Analyse, interprétation et exploitation de données "
            "afin d'identifier des tendances, mesurer des performances, "
            "produire des insights et soutenir la prise de décision."
        ),
        "aliases": [
            "Data Analysis",
            "Analyse de données",
            "Analyse des données",
            "Data Analytics",
            "Analyse de performance",
            "Performance Analysis",
        ],
        "parent": None,
        "related_skills": [
            "Data Science",
            "SQL",
            "Data / KPI",
            "Business Intelligence",
        ],
    },

    {
        "id": "catalog-data-kpi",
        "canonical_name": "Data / KPI",
        "category": "Data",
        "subcategory": "Reporting",
        "description": (
            "Suivi et pilotage d'indicateurs clés de performance "
            "(KPI), production de reportings et analyse orientée "
            "décision business à partir de données chiffrées."
        ),
        "aliases": [
            "Data / KPI",
            "KPI",
            "Reporting",
            "Data Driven",
            "Data Driven Decision Making",
            "Data Marketing",
        ],
        "parent": "catalog-data-analysis",
        "related_skills": [
            "Data Analysis",
            "Microsoft Excel",
            "Product Management",
        ],
    },

    {
        "id": "catalog-data-science",
        "canonical_name": "Data Science",
        "category": "Data",
        "subcategory": "Data Science",
        "description": (
            "Utilisation de méthodes statistiques, mathématiques "
            "et informatiques pour analyser des données, construire "
            "des modèles prédictifs et produire des insights "
            "permettant de résoudre des problèmes business."
        ),
        "aliases": [
            "Data Science",
            "Science des données",
            "Data Scientist",
        ],
        "parent": None,
        "related_skills": [
            "Machine Learning",
            "Data Analysis",
            "Python",
            "SQL",
        ],
    },

    {
        "id": "catalog-machine-learning",
        "canonical_name": "Machine Learning",
        "category": "AI",
        "subcategory": "Machine Learning",
        "description": (
            "Conception et utilisation de modèles permettant "
            "à des systèmes d'apprendre à partir de données "
            "afin de réaliser des prédictions, classifications "
            "ou autres tâches automatisées."
        ),
        "aliases": [
            "Machine Learning",
            "Apprentissage automatique",
            "Machine Learning Engineering",
            "ML",
        ],
        "parent": None,
        "related_skills": [
            "Artificial Intelligence",
            "Data Science",
            "Python",
            "Data Analysis",
        ],
    },

    {
        "id": "catalog-artificial-intelligence",
        "canonical_name": "Artificial Intelligence",
        "category": "AI",
        "subcategory": "Artificial Intelligence",
        "description": (
            "Conception, utilisation et pilotage de systèmes "
            "capables de réaliser des tâches nécessitant "
            "habituellement des capacités cognitives humaines, "
            "notamment l'apprentissage, le raisonnement, "
            "la compréhension du langage ou la génération de contenu."
        ),
        "aliases": [
            "Artificial Intelligence",
            "AI",
            "IA",
            "Intelligence Artificielle",
        ],
        "parent": None,
        "related_skills": [
            "Machine Learning",
            "Data Science",
            "Product Management",
            "Data Analysis",
        ],
    },

    {
        "id": "catalog-sql",
        "canonical_name": "SQL",
        "category": "Data",
        "subcategory": "Database",
        "description": (
            "Langage utilisé pour interroger, manipuler, "
            "transformer et analyser des données stockées "
            "dans des bases de données relationnelles."
        ),
        "aliases": [
            "SQL",
            "Requêtes SQL",
            "Langage SQL",
            "SQL queries",
        ],
        "parent": "catalog-data-analysis",
        "related_skills": [
            "Data Analysis",
            "Data Science",
            "Python",
            "Business Intelligence",
        ],
    },

    # ========================================================
    # TECHNOLOGIES
    # ========================================================

    {
        "id": "catalog-python",
        "canonical_name": "Python",
        "category": "Technology",
        "subcategory": "Programming",
        "description": (
            "Langage de programmation généraliste utilisé "
            "notamment pour le développement logiciel, "
            "l'automatisation, l'analyse de données, "
            "la data science et l'intelligence artificielle."
        ),
        "aliases": [
            "Python",
            "Programmation Python",
            "Développement Python",
            "Python programming",
        ],
        "parent": None,
        "related_skills": [
            "Data Science",
            "Machine Learning",
            "Data Analysis",
            "Automatisation",
        ],
    },

    {
        "id": "catalog-automatisation",
        "canonical_name": "Automatisation",
        "category": "Technology",
        "subcategory": "Process Automation",
        "description": (
            "Conception et mise en place de processus ou d'outils "
            "permettant d'automatiser des tâches répétitives, "
            "notamment via des scripts, macros ou intégrations "
            "entre outils."
        ),
        "aliases": [
            "Automatisation",
            "Automation",
            "Process Automation",
        ],
        "parent": None,
        "related_skills": [
            "Python",
            "Microsoft Excel",
        ],
    },

    {
        "id": "catalog-r",
        "canonical_name": "R",
        "category": "Technology",
        "subcategory": "Programming",
        "description": (
            "Langage de programmation principalement utilisé "
            "pour l'analyse statistique, la data science, "
            "la visualisation et le traitement de données."
        ),
        "aliases": [
            "R",
            "Langage R",
            "R Programming",
            "R programming language",
        ],
        "parent": None,
        "related_skills": [
            "Data Science",
            "Data Analysis",
            "Machine Learning",
        ],
    },

    {
        "id": "catalog-aws",
        "canonical_name": "AWS",
        "category": "Technology",
        "subcategory": "Cloud",
        "description": (
            "Plateforme de services cloud Amazon Web Services "
            "fournissant notamment des capacités de calcul, "
            "stockage, bases de données, réseau, sécurité "
            "et services d'intelligence artificielle."
        ),
        "aliases": [
            "AWS",
            "Amazon Web Services",
        ],
        "parent": None,
        "related_skills": [
            "Azure",
            "Google Cloud",
            "Cloud Computing",
        ],
    },

    {
        "id": "catalog-azure",
        "canonical_name": "Azure",
        "category": "Technology",
        "subcategory": "Cloud",
        "description": (
            "Plateforme cloud Microsoft fournissant des services "
            "de calcul, stockage, données, réseau, sécurité, "
            "développement et intelligence artificielle."
        ),
        "aliases": [
            "Azure",
            "Microsoft Azure",
        ],
        "parent": None,
        "related_skills": [
            "AWS",
            "Google Cloud",
            "Cloud Computing",
        ],
    },

    {
        "id": "catalog-google-cloud",
        "canonical_name": "Google Cloud",
        "category": "Technology",
        "subcategory": "Cloud",
        "description": (
            "Plateforme cloud Google fournissant des services "
            "de calcul, stockage, données, intelligence artificielle, "
            "machine learning, réseau et développement."
        ),
        "aliases": [
            "Google Cloud",
            "GCP",
            "Google Cloud Platform",
        ],
        "parent": None,
        "related_skills": [
            "AWS",
            "Azure",
            "Cloud Computing",
            "Machine Learning",
        ],
    },

    # ========================================================
    # OUTILS
    # ========================================================

    {
        "id": "catalog-jira",
        "canonical_name": "Jira",
        "category": "Tools",
        "subcategory": "Project Management Tools",
        "description": (
            "Outil de gestion de projets et de suivi du travail "
            "permettant notamment de gérer les tickets, tâches, "
            "backlogs, sprints, workflows et avancement des équipes."
        ),
        "aliases": [
            "Jira",
            "Atlassian Jira",
        ],
        "parent": None,
        "related_skills": [
            "Agile / Scrum",
            "Backlog Management",
            "Gestion de projet",
        ],
    },

    {
        "id": "catalog-microsoft-excel",
        "canonical_name": "Microsoft Excel",
        "category": "Tools",
        "subcategory": "Office",
        "description": (
            "Tableur utilisé pour organiser, calculer, analyser "
            "et visualiser des données, construire des tableaux "
            "de suivi, produire des reportings et automatiser "
            "certaines tâches à l'aide notamment de formules, "
            "macros ou VBA."
        ),
        "aliases": [
            "Excel",
            "Microsoft Excel",
            "Excel macros",
            "Macros Excel",
            "VBA Excel",
            "VBA",
        ],
        "parent": None,
        "related_skills": [
            "Data Analysis",
            "Reporting",
            "Data / KPI",
            "Automatisation",
        ],
    },

    # ========================================================
    # DESIGN
    # ========================================================

    {
        "id": "catalog-ux",
        "canonical_name": "UX",
        "category": "Design",
        "subcategory": "User Experience",
        "description": (
            "Conception et amélioration de l'expérience utilisateur "
            "d'un produit ou service en étudiant les besoins, "
            "parcours, usages, interactions, frustrations et "
            "objectifs des utilisateurs."
        ),
        "aliases": [
            "UX",
            "User Experience",
            "Expérience utilisateur",
            "UX Design",
        ],
        "parent": None,
        "related_skills": [
            "User Research",
            "Product Discovery",
            "UI",
            "Experimentation",
        ],
    },

    {
        "id": "catalog-ui",
        "canonical_name": "UI",
        "category": "Design",
        "subcategory": "User Interface",
        "description": (
            "Conception de l'interface utilisateur d'un produit "
            "numérique, incluant les composants visuels, écrans, "
            "interactions, navigation, design system et cohérence "
            "visuelle."
        ),
        "aliases": [
            "UI",
            "User Interface",
            "Interface utilisateur",
            "UI Design",
        ],
        "parent": None,
        "related_skills": [
            "UX",
            "Figma",
            "Product Discovery",
        ],
    },

    # ========================================================
    # BUSINESS
    # ========================================================

    {
        "id": "catalog-ecommerce",
        "canonical_name": "E-commerce",
        "category": "Business",
        "subcategory": "Digital Business",
        "description": (
            "Connaissance et gestion des activités commerciales "
            "digitales permettant de vendre des produits ou services "
            "en ligne, notamment les parcours d'achat, conversion, "
            "catalogue, acquisition, fidélisation et expérience "
            "client digitale."
        ),
        "aliases": [
            "E-commerce",
            "E commerce",
            "Ecommerce",
            "Ecommerce experience",
            "Commerce électronique",
            "Commerce electronique",
            "Digital Commerce",
        ],
        "parent": None,
        "related_skills": [
            "Product Management",
            "UX",
            "Data Analysis",
            "Product Discovery",
        ],
    },

    {
        "id": "catalog-adtech",
        "canonical_name": "AdTech",
        "category": "Business",
        "subcategory": "Digital Advertising",
        "description": (
            "Connaissance des technologies et écosystèmes de la "
            "publicité digitale : diffusion, ciblage, mesure de "
            "performance et monétisation publicitaire en ligne."
        ),
        "aliases": [
            "AdTech",
            "Advertising Technology",
            "Publicité digitale",
        ],
        "parent": None,
        "related_skills": [
            "E-commerce",
            "Product Management",
            "Data / KPI",
        ],
    },
]

# ============================================================
# SEED
# ============================================================

def seed_skill_catalog() -> None:

    db = SessionLocal()

    created_count = 0
    updated_count = 0

    try:

        # ====================================================
        # 1. VALIDATION DU REFERENTIEL EN MEMOIRE
        # ====================================================

        canonical_names: set[str] = set()

        for skill_data in SKILLS:

            canonical_name = skill_data["canonical_name"]

            if canonical_name in canonical_names:
                raise ValueError(
                    "Doublon dans le référentiel : "
                    f"{canonical_name}"
                )

            canonical_names.add(canonical_name)

        # ====================================================
        # 2. IMPORT / MISE A JOUR
        # ====================================================

        for skill_data in SKILLS:

            skill_id = skill_data["id"]
            canonical_name = skill_data["canonical_name"]

            aliases_json = json.dumps(
                skill_data.get("aliases", []),
                ensure_ascii=False,
            )

            related_skills_json = json.dumps(
                skill_data.get("related_skills", []),
                ensure_ascii=False,
            )

            # ------------------------------------------------
            # Recherche 1 : ID exact
            # ------------------------------------------------

            existing = (
                db.query(SkillCatalogDB)
                .filter(
                    SkillCatalogDB.id == skill_id
                )
                .first()
            )

            # ------------------------------------------------
            # Recherche 2 : canonical_name
            #
            # Utile si une compétence existe déjà avec
            # un ancien ID.
            # ------------------------------------------------

            if existing is None:

                existing = (
                    db.query(SkillCatalogDB)
                    .filter(
                        SkillCatalogDB.canonical_name
                        == canonical_name
                    )
                    .first()
                )

            # =================================================
            # 3. COMPETENCE EXISTANTE
            # =================================================

            if existing is not None:

                changed = False

                fields = {
                    "canonical_name": canonical_name,
                    "category": skill_data.get(
                        "category",
                        "",
                    ),
                    "subcategory": skill_data.get(
                        "subcategory",
                        "",
                    ),
                    "description": skill_data.get(
                        "description",
                        "",
                    ),
                    "aliases": aliases_json,
                    "related_skills": related_skills_json,
                    "is_active": True,
                }

                for field, value in fields.items():

                    if getattr(
                        existing,
                        field,
                        None,
                    ) != value:

                        setattr(
                            existing,
                            field,
                            value,
                        )

                        changed = True

                # ---------------------------------------------
                # Parent
                # ---------------------------------------------

                if hasattr(
                    existing,
                    "parent_skill_id",
                ):

                    parent_id = skill_data.get(
                        "parent"
                    )

                    if (
                        existing.parent_skill_id
                        != parent_id
                    ):

                        existing.parent_skill_id = (
                            parent_id
                        )

                        changed = True

                if changed:
                    updated_count += 1

            # =================================================
            # 4. NOUVELLE COMPETENCE
            # =================================================

            else:

                skill = SkillCatalogDB(
                    id=skill_id,

                    canonical_name=canonical_name,

                    category=skill_data.get(
                        "category",
                        "",
                    ),

                    subcategory=skill_data.get(
                        "subcategory",
                        "",
                    ),

                    description=skill_data.get(
                        "description",
                        "",
                    ),

                    aliases=aliases_json,

                    related_skills=related_skills_json,

                    is_active=True,
                )

                if hasattr(
                    skill,
                    "parent_skill_id",
                ):

                    skill.parent_skill_id = (
                        skill_data.get(
                            "parent"
                        )
                    )

                db.add(skill)

                created_count += 1

        # ====================================================
        # 5. COMMIT
        # ====================================================

        db.commit()

        print(
            f"{created_count} compétences créées."
        )

        print(
            f"{updated_count} compétences mises à jour."
        )

        print()

        print(
            "=" * 42
        )

        print(
            "REFERENTIEL DE COMPETENCES IMPORTE"
        )

        print(
            "=" * 42
        )

    except Exception:

        db.rollback()

        raise

    finally:

        db.close()


# ============================================================
# EXECUTION DIRECTE
# ============================================================

if __name__ == "__main__":
    seed_skill_catalog()