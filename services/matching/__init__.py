"""
Moteur de matching Master CV ↔ offre d'emploi.

Découpage du module :

- config        : listes, seuils et pondérations ;
- results       : objets de résultat (SkillMatch, MatchingResult) ;
- normalization : normalisation du texte, résolution des alias via
                  le référentiel skill_catalog ;
- profile_text  : représentations textuelles du profil candidat ;
- inference     : inférence lexicale et sémantique, avec ses garde-fous ;
- analysis      : orchestration et sauvegarde du résultat.

Seule l'API réexportée ici est destinée à être utilisée depuis
l'extérieur du package.
"""

from services.matching.analysis import (
    analyze_and_save_job_match,
    analyze_candidate_against_skills,
)
from services.matching.results import (
    MatchingResult,
    SkillMatch,
)

__all__ = [
    "MatchingResult",
    "SkillMatch",
    "analyze_and_save_job_match",
    "analyze_candidate_against_skills",
]
