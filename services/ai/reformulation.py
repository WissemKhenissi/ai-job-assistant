"""
Reformulation IA du CV et de la lettre, avec garde-fous anti-invention.

Principe non négociable du projet, appliqué ici : l'IA reformule un
texte déjà entièrement déterminé par le Master CV. Elle ne peut ni
ajouter une compétence, ni un chiffre, ni un fait absent du texte
source — seulement le rendre plus fluide et plus adapté au vocabulaire
de l'offre.

Deux lignes de défense :

1. Le prompt l'interdit explicitement.
2. Un garde-fou automatique vérifie qu'aucun nombre nouveau (donc
   potentiellement un chiffre ou un pourcentage inventé) n'apparaît
   dans le résultat ; si c'est le cas, la reformulation est rejetée.

Si la reformulation échoue pour n'importe quelle raison — clé absente,
erreur API, garde-fou déclenché — le texte déterministe d'origine est
utilisé sans que rien ne casse. La reformulation est un plus, jamais
une dépendance : le CV et la lettre restent générables sans elle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from services.ai.gemini_client import (
    GeminiNotConfiguredError,
    GeminiRequestError,
    generate_text,
    is_configured,
)
from services.cv.results import CVEvidenceLine, TargetedCV
from services.letter.results import CoverLetter, LetterParagraph


# Longueur d'extrait d'offre transmise au prompt : assez pour donner
# le vocabulaire et le ton, sans faire exploser le coût du prompt sur
# une annonce de plusieurs milliers de caractères.
MAX_JOB_EXCERPT = 2000


def _digits(text: str) -> set[str]:
    """Tous les nombres (suites de chiffres) présents dans un texte."""

    return set(re.findall(r"\d+", text))


@dataclass(frozen=True)
class ReformulationResult:
    text: str
    was_reformulated: bool
    warning: str = ""


def _safe_reformulate(
    source_text: str,
    instructions: str,
) -> ReformulationResult:
    """
    Reformule un texte via Gemini, avec repli automatique sur le texte
    source en cas d'échec ou de garde-fou déclenché.
    """

    if not source_text.strip():
        return ReformulationResult(
            text=source_text,
            was_reformulated=False,
        )

    if not is_configured():
        return ReformulationResult(
            text=source_text,
            was_reformulated=False,
            warning=(
                "Clé GEMINI_API_KEY non configurée : texte "
                "déterministe utilisé."
            ),
        )

    prompt = (
        "Tu reformules un extrait de candidature déjà entièrement "
        "exact.\n\n"
        "RÈGLES ABSOLUES :\n"
        "- N'ajoute AUCUNE compétence, entreprise, chiffre, "
        "pourcentage, durée ou fait qui n'est pas déjà présent dans "
        "le texte source.\n"
        "- N'affirme jamais une compétence ou une réussite qui n'y "
        "figure pas.\n"
        "- N'ajoute AUCUNE activité, action ou étape supplémentaire, "
        "même plausible ou habituelle pour ce type de mission "
        "(exemple interdit : transformer \"identification "
        "d'opportunités\" en \"analyse de marché et identification "
        "d'opportunités\" — \"analyse de marché\" n'était pas dans "
        "le texte source, même si c'est un préalable plausible).\n"
        "- Le texte reformulé doit décrire exactement les mêmes "
        "actions que le texte source, ni plus, ni moins — seuls les "
        "mots changent, jamais le nombre d'actions décrites.\n"
        "- Tu peux reformuler, réordonner, rendre plus fluide et "
        "plus direct — jamais enrichir le contenu factuel.\n"
        "- Si tu ne peux pas reformuler sans ajouter d'information, "
        "renvoie le texte source tel quel.\n"
        "- Réponds uniquement avec le texte reformulé : pas de "
        "commentaire, pas de guillemets, pas d'introduction.\n\n"
        f"{instructions}\n\n"
        f"Texte source :\n{source_text}"
    )

    try:
        reformule = generate_text(prompt)

    except (GeminiNotConfiguredError, GeminiRequestError) as error:
        return ReformulationResult(
            text=source_text,
            was_reformulated=False,
            warning=(
                f"Reformulation IA indisponible ({error}) : texte "
                "déterministe utilisé."
            ),
        )

    # ------------------------------------------------------------
    # GARDE-FOU : aucun nombre nouveau ne doit apparaître.
    # ------------------------------------------------------------
    #
    # Un chiffre absent du texte source (marge, pourcentage, durée...)
    # serait la forme la plus grave d'invention : un fait chiffré
    # fabriqué. On ne tente pas de tout vérifier — seuls les nombres
    # sont assez concrets pour être contrôlés de façon fiable.

    nombres_inventes = _digits(reformule) - _digits(source_text)

    if nombres_inventes:
        return ReformulationResult(
            text=source_text,
            was_reformulated=False,
            warning=(
                "Reformulation rejetée : elle introduisait des "
                f"chiffres absents du texte source "
                f"({', '.join(sorted(nombres_inventes))}). Texte "
                "déterministe utilisé."
            ),
        )

    return ReformulationResult(text=reformule, was_reformulated=True)


# ============================================================
# LETTRE DE MOTIVATION
# ============================================================

def reformulate_letter_paragraph(
    text: str,
    job_text: str,
    poste: str,
) -> ReformulationResult:

    instructions = (
        f"Ce paragraphe fait partie d'une lettre de motivation pour "
        f"le poste de {poste}. Reformule-le pour qu'il soit plus "
        "naturel et mieux adapté au vocabulaire de l'offre "
        "ci-dessous, sans changer le fond.\n\n"
        f"Extrait de l'offre :\n{job_text[:MAX_JOB_EXCERPT]}"
    )

    return _safe_reformulate(text, instructions)


def reformulate_cover_letter(
    letter: CoverLetter,
    job_text: str,
) -> tuple[CoverLetter, list[str]]:
    """
    Reformule les paragraphes de contenu de la lettre (pas les
    formules fixes : objet, salutation, formule de politesse,
    signature — aucune valeur à en attendre, seulement un risque de
    dérive).

    Retourne une nouvelle lettre (jamais validée d'office, comme
    toute lettre générée) et la liste des avertissements rencontrés.
    """

    avertissements: list[str] = []
    nouveaux_paragraphes: list[LetterParagraph] = []

    for paragraphe in letter.paragraphs:

        resultat = reformulate_letter_paragraph(
            paragraphe.text,
            job_text,
            letter.job_offer_title,
        )

        if resultat.warning:
            avertissements.append(resultat.warning)

        nouveaux_paragraphes.append(
            LetterParagraph(
                text=resultat.text,
                sources=paragraphe.sources,
            )
        )

    lettre_reformulee = replace(
        letter,
        paragraphs=nouveaux_paragraphes,
        validated_by_user=False,
    )

    return lettre_reformulee, avertissements


# ============================================================
# CV CIBLE
# ============================================================

def reformulate_cv_line(
    text: str,
    job_text: str,
) -> ReformulationResult:

    instructions = (
        "Cette ligne fait partie des compétences démontrées sur un "
        "CV ciblé pour l'offre ci-dessous. Reformule-la pour "
        "qu'elle soit plus percutante et reprenne, si pertinent, le "
        "vocabulaire de l'offre — sans changer le fond.\n\n"
        f"Extrait de l'offre :\n{job_text[:MAX_JOB_EXCERPT]}"
    )

    return _safe_reformulate(text, instructions)


def reformulate_targeted_cv(
    cv: TargetedCV,
    job_text: str,
) -> tuple[TargetedCV, list[str]]:
    """
    Reformule les lignes de preuve de chaque expérience retenue.

    Le reste du CV (compétences, formation, certifications, en-tête)
    n'est volontairement pas passé à l'IA : ce sont des données
    factuelles courtes, sans valeur à en attendre d'une reformulation.
    """

    avertissements: list[str] = []
    nouvelles_experiences = []

    for experience in cv.experiences:

        nouvelles_lignes: list[CVEvidenceLine] = []

        for ligne in experience.lines:

            resultat = reformulate_cv_line(ligne.text, job_text)

            if resultat.warning:
                avertissements.append(resultat.warning)

            nouvelles_lignes.append(
                CVEvidenceLine(
                    text=resultat.text,
                    skill=ligne.skill,
                    evidence_id=ligne.evidence_id,
                )
            )

        nouvelles_experiences.append(
            replace(experience, lines=nouvelles_lignes)
        )

    cv_reformule = replace(cv, experiences=nouvelles_experiences)

    return cv_reformule, avertissements
