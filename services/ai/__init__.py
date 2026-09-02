"""
Reformulation IA du CV et de la lettre de motivation.

L'IA (Gemini) ne fait jamais que reformuler un texte déjà entièrement
déterminé par le Master CV — elle ne peut ajouter aucune compétence,
aucun chiffre, aucun fait absent du texte source. Voir
services.ai.reformulation pour le détail des garde-fous.
"""

from services.ai.reformulation import (
    ReformulationResult,
    reformulate_cover_letter,
    reformulate_targeted_cv,
)

__all__ = [
    "ReformulationResult",
    "reformulate_cover_letter",
    "reformulate_targeted_cv",
]
