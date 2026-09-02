"""
Intégration IA (Gemini) du CV, de la lettre de motivation et de
l'analyse d'offre.

Trois usages, trois garde-fous adaptés au risque de chacun :

- `reformulate_*` (services.ai.reformulation) : reformule un texte
  déjà entièrement déterminé par le Master CV — l'IA ne peut ajouter
  aucune compétence, aucun chiffre, aucun fait absent du texte source.
- `build_ai_letter` (services.ai.letter_authoring) : fait composer à
  l'IA l'argumentaire complet de la lettre à partir d'une fiche de
  faits structurée — même interdiction d'invention, contrôlée sur
  l'ensemble de la fiche plutôt que sur une phrase isolée.
- `analyze_job_offer_with_ai` / `generate_fit_synthesis`
  (services.ai.job_analysis) : catégorise l'offre (type de contrat,
  télétravail, compétences attendues) et commente en langage naturel
  le résultat déjà calculé par le moteur de matching honnête — l'IA
  ne recalcule jamais le score ni les statuts prouvé/déclaré/déduit.
- `generate_interview_questions` / `propose_evidence_from_answers`
  (services.ai.interview) : pose des questions de relance sur le
  Master CV, puis propose des preuves à partir des réponses données
  — jamais écrites automatiquement, toujours soumises à validation
  explicite et éditable par le candidat.

Dans tous les cas, tout repose sur un repli automatique vers le
contenu déterministe si l'IA n'est pas configurée, échoue, ou que le
garde-fou se déclenche.
"""

from services.ai.interview import (
    EvidenceProposal,
    InterviewAnswer,
    InterviewQuestion,
    generate_interview_questions,
    propose_evidence_from_answers,
)
from services.ai.job_analysis import (
    FitSynthesisResult,
    JobOfferAnalysis,
    analyze_job_offer_with_ai,
    generate_fit_synthesis,
)
from services.ai.letter_authoring import build_ai_letter
from services.ai.reformulation import (
    ReformulationResult,
    reformulate_cover_letter,
    reformulate_cv_summary,
    reformulate_targeted_cv,
)

__all__ = [
    "EvidenceProposal",
    "FitSynthesisResult",
    "InterviewAnswer",
    "InterviewQuestion",
    "JobOfferAnalysis",
    "ReformulationResult",
    "analyze_job_offer_with_ai",
    "build_ai_letter",
    "generate_fit_synthesis",
    "generate_interview_questions",
    "propose_evidence_from_answers",
    "reformulate_cover_letter",
    "reformulate_cv_summary",
    "reformulate_targeted_cv",
]
