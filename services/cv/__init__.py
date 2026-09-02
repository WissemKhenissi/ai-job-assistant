"""
Génération de CV ciblé à partir du Master CV et d'une analyse d'offre.

Le contenu est sélectionné, jamais inventé : chaque ligne du CV
généré porte l'identifiant de la donnée du Master CV dont elle est
issue.
"""

from services.cv.export import (
    default_export_path,
    export_docx,
    export_pdf,
)
from services.cv.results import (
    CVAchievement,
    CVEvidenceLine,
    CVExperience,
    TargetedCV,
)
from services.cv.selection import (
    MissingAnalysisError,
    build_targeted_cv,
)

__all__ = [
    "CVAchievement",
    "CVEvidenceLine",
    "CVExperience",
    "MissingAnalysisError",
    "TargetedCV",
    "build_targeted_cv",
    "default_export_path",
    "export_docx",
    "export_pdf",
]
