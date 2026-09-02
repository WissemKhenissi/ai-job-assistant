"""
Génération de lettre de motivation.

La lettre est assemblée de façon déterministe à partir du Master CV et
de l'offre, sans intervention d'un modèle de langage : elle ne peut
affirmer que ce que le Master CV documente.

Une lettre générée n'est jamais finale tant que l'utilisateur ne l'a
pas relue et validée.
"""

from services.letter.export import (
    default_letter_path,
    export_letter_docx,
    export_letter_pdf,
)
from services.letter.generation import build_cover_letter
from services.letter.results import CoverLetter, LetterParagraph

__all__ = [
    "CoverLetter",
    "LetterParagraph",
    "build_cover_letter",
    "default_letter_path",
    "export_letter_docx",
    "export_letter_pdf",
]
