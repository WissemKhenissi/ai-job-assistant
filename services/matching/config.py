"""
Paramètres du moteur de matching.

Regroupe les listes, seuils et pondérations qui pilotent le
comportement du moteur, séparés de la logique qui les applique.
"""

from __future__ import annotations


# ============================================================
# NORMALISATION / ALIAS
# ============================================================

# Les alias de compétences ne sont plus dupliqués ici : ils viennent
# du référentiel skill_catalog (table skill_catalog, exposée par
# services.skill_catalog_service), seule source de vérité. Voir
# _canonical_skill_name() / _canonical_alias_index() plus bas.


# ============================================================
# INFERENCE LEXICALE
# ============================================================

INFERENCE_KEYWORDS = {
    "agile scrum": (
        "iteration",
        "iterative",
        "mvp",
        "test",
        "amelioration continue",
        "sprint",
        "cycle iteratif",
        "cycles iteratifs",
        "developpement iteratif",
        "developpements iteratifs",
    ),
    "priorisation": (
        "priorite",
        "priorites",
        "arbitrage",
        "mvp",
        "quick win",
        "optimisation",
        "valeur",
        "cout",
        "faisabilite",
    ),
    "backlog management": (
        "priorite",
        "arbitrage",
        "mvp",
        "iteration",
        "fonctionnalite",
        "backlog",
        "user story",
        "stories",
    ),
    "stakeholder management": (
        "coordination",
        "partenaire",
        "equipe",
        "juridique",
        "comptabilite",
        "ux",
        "ui",
        "it",
        "client",
        "parties prenantes",
        "stakeholders",
    ),
    "data kpi": (
        "kpi",
        "performance",
        "marge",
        "chiffre d affaires",
        "ca",
        "reporting",
        "metrique",
        "conversion",
        "roi",
    ),
    "gestion de projet": (
        "pilotage",
        "coordination",
        "mise en production",
        "projet",
        "planning",
        "blocage",
        "deadline",
    ),
    "e commerce": (
        "e commerce",
        "fnac",
        "france billet",
        "post achat",
        "confirmation de commande",
        "achat",
    ),
    "product strategy": (
        "business model",
        "proposition de valeur",
        "opportunite",
        "valeur business",
        "monetisation",
        "offre",
        "strategie",
    ),
    "roadmap produit": (
        "planning",
        "priorite",
        "evolution",
        "iteration",
        "projet",
        "mise en production",
        "roadmap",
    ),
    "experimentation": (
        "test",
        "iteration",
        "optimisation",
        "mvp",
        "mesure",
        "kpi",
    ),
    "ux": (
        "ux",
        "parcours",
        "experience utilisateur",
        "interface",
        "landing page",
    ),
    "ui": (
        "ui",
        "interface",
        "design",
        "landing page",
    ),
}

# ============================================================
# INFERENCE SEMANTIQUE
# ============================================================

SEMANTIC_INFERENCE_THRESHOLD = 0.62

SEMANTIC_INFERENCE_STRONG_THRESHOLD = 0.75

SEMANTIC_SPECIFICITY_THRESHOLD = 0.80


# ============================================================
# PONDERATION DES STATUTS
# ============================================================

# Une compétence explicitement prouvée est la référence.
PROVEN_SCORE = 1.00

# Compétence déclarée dans le CV mais sans preuve détaillée.
DECLARED_SCORE = 0.90

# Inférence sémantique :
# la valeur dépend de la qualité de la correspondance.
INFERRED_VERY_STRONG_SCORE = 0.85
INFERRED_STRONG_SCORE = 0.80
INFERRED_GOOD_SCORE = 0.75
INFERRED_MODERATE_SCORE = 0.70
INFERRED_PRUDENT_SCORE = 0.60

MISSING_SCORE = 0.00


# ============================================================
# PONDERATION DU SCORE D'EXPERIENCE
# ============================================================
#
# Le score d'expérience est exprimé sur 100 : il mesure la part
# des compétences demandées que le candidat sait démontrer.
#
# Une compétence prouvée (preuve EvidenceDB liée) vaut le maximum,
# une compétence seulement déduite vaut nettement moins — une
# inférence reste une hypothèse, pas un fait affirmé.

EXPERIENCE_PROVEN_WEIGHT = 100

EXPERIENCE_INFERRED_WEIGHT = 60


# ============================================================
# COMPETENCES AUTORISEES A L'INFERENCE
# ============================================================

SEMANTIC_INFERENCE_SKILLS = {
    "agile scrum",
    "priorisation",
    "backlog management",
    "stakeholder management",
    "product discovery",
    "product strategy",
    "roadmap produit",
    "product delivery",
    "experimentation",
    # "analyse utilisateur" fusionne désormais dans "user research"
    # (alias du référentiel skill_catalog) via _canonical_skill_name().
    "user research",
    "data analysis",
    "gestion de projet",
}


# ============================================================
# COMPETENCES QUI NE DOIVENT JAMAIS ETRE INDUITES
# ============================================================

SEMANTIC_INFERENCE_EXCLUDED = {
    "product management",
    "python",
    "sql",
    "r",
    "aws",
    "azure",
    "google cloud",
    "machine learning",
    "data science",
    "artificial intelligence",
    "jira",
}



# ============================================================
# PONDERATION DES EXIGENCES
# ============================================================
#
# Les exigences d'une annonce n'ont pas toutes le même poids. Le score
# les moyennait à égalité : un outil cité dans une énumération de fin
# d'annonce comptait autant que la compétence cœur du poste. Avec un
# référentiel large, une annonce citant « Jira, Miro, GitLab, Planner,
# MS Project » voyait son score s'effondrer sur des détails.
#
# Le poids décroît selon le rang d'apparition dans l'annonce :
#
#     rang 0  -> 1,00        rang 9  -> 0,36
#     rang 4  -> 0,56        rang 19 -> 0,21
#
# Plus la valeur est grande, plus la décroissance est douce. À 5, la
# vingtième exigence pèse un cinquième de la première — assez pour
# qu'une longue liste d'outils ne domine pas, pas assez pour qu'elle
# disparaisse.
SKILL_WEIGHT_DECAY = 5.0


# ============================================================
# POIDS DES NIVEAUX D'EXIGENCE
# ============================================================
#
# Le rang d'apparition n'est qu'un indice : il suppose que l'annonce
# range l'essentiel en premier. Ce que l'annonce **dit** du terme en
# est un autre, plus direct — « indispensable » contre
# « environnement : ... ». Voir services.requirement_importance.
#
# Les deux se multiplient : une exigence essentielle citée en tête
# porte le score, une simple mention en fin d'annonce ne le fait
# presque plus bouger, sans pour autant disparaître — une mention
# reste un écart réel, elle est toujours affichée comme telle.
#
# Une compétence essentielle non couverte coûte cinq fois ce que
# coûte un outil cité en exemple.
POIDS_IMPORTANCE = {
    "essentielle": 1.00,
    "souhaitee": 0.55,
    "mention": 0.20,
}
