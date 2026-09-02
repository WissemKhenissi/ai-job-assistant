"""
Intégration IA (Gemini) du CV et de la lettre de motivation.

Deux usages, deux garde-fous équivalents mais adaptés :

- `reformulate_*` (services.ai.reformulation) : reformule un texte
  déjà entièrement déterminé par le Master CV — l'IA ne peut ajouter
  aucune compétence, aucun chiffre, aucun fait absent du texte source.
- `build_ai_letter` (services.ai.letter_authoring) : fait composer à
  l'IA l'argumentaire complet de la lettre à partir d'une fiche de
  faits structurée — même interdiction d'invention, contrôlée sur
  l'ensemble de la fiche plutôt que sur une phrase isolée.

Dans les deux cas, tout repose sur un repli automatique vers le
contenu déterministe si l'IA n'est pas configurée, échoue, ou que le
garde-fou se déclenche.
"""

from services.ai.letter_authoring import build_ai_letter
from services.ai.reformulation import (
    ReformulationResult,
    reformulate_cover_letter,
    reformulate_cv_summary,
    reformulate_targeted_cv,
)

__all__ = [
    "ReformulationResult",
    "build_ai_letter",
    "reformulate_cover_letter",
    "reformulate_cv_summary",
    "reformulate_targeted_cv",
]
