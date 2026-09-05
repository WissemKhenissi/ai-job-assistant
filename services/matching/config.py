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
#
# Les indices qui trahissent une compétence dans un parcours venaient
# d'un dictionnaire codé en dur : douze entrées, toutes d'un métier
# produit. Ils viennent maintenant des alias et des compétences
# associées que le référentiel porte déjà — voir
# services.matching.inference._indices_possibles().


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
# CE QUI PEUT ETRE DEDUIT
# ============================================================
#
# Deux listes vivaient ici : douze compétences seules autorisées à
# l'inférence, onze technologies explicitement interdites. Toutes
# choisies pour un seul métier — avec un référentiel de treize mille
# entrées, la première condamnait tout le reste au silence, et un
# profil d'infirmière ou de développeur ne pouvait produire aucune
# compétence « déduite ».
#
# La distinction n'a pourtant rien de propre à un métier : un
# savoir-faire se devine d'un récit d'expérience, un outil ou un
# corpus de connaissances non. Elle est portée par le référentiel,
# colonne `skill_catalog.is_inferable`, et lue par
# services.matching.inference._est_deductible().


# Nombre d'indices distincts à retrouver dans un parcours pour
# qu'une inférence lexicale tienne. Un seul mot commun ne prouve
# rien ; deux indices concordants restent une hypothèse, mais une
# hypothèse défendable.
MIN_INFERENCE_INDICES = 2


# Nombre de composantes à retrouver pour qu'une compétence
# d'ensemble soit déduite de sa composition. Voir l'inférence
# composite dans services.matching.analysis.
MIN_COMPOSITE_COMPONENTS = 3


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
