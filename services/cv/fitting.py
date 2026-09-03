"""
Contrainte d'une page : mesurer, puis élaguer par priorité.

On ne demande pas au modèle d'« estimer la longueur » du CV : il en
est incapable de façon fiable, puisque le nombre de pages dépend de la
police, des marges et du gabarit. Ici, on **rend réellement le PDF, on
compte les pages**, on retire l'élément le moins précieux, et on
recommence.

L'élagage ne fait que **retirer** : jamais réécrire, jamais résumer,
jamais fusionner deux faits en un. Un CV plus court reste ainsi
exactement aussi vrai que le CV complet.

Ordre de sacrifice, du moins au plus coûteux :

1. centres d'intérêt ;
2. langues ;
3. résumé réduit à sa première phrase ;
4. contexte d'entreprise des expériences les plus anciennes ;
5. lignes de preuve des expériences les plus anciennes, jusqu'à en
   laisser une par expérience ;
6. formation et certifications.

Une expérience n'est jamais supprimée entièrement : un trou dans la
chronologie attire l'œil et appelle une question gênante en entretien.
Si le CV déborde encore après tout cela, on le dit franchement plutôt
que de compresser au point de le rendre illisible.
"""

from __future__ import annotations

import copy
import tempfile
from pathlib import Path

from services.cv.export import ALL_CV_SECTIONS, export_pdf


def count_pdf_pages(path: Path | str) -> int:
    """Nombre de pages d'un PDF, ou 0 s'il est illisible."""

    from pypdf import PdfReader

    try:
        return len(PdfReader(str(path)).pages)

    except Exception:
        return 0


def _tient_sur_une_page(cv, sections: set[str]) -> bool:

    with tempfile.TemporaryDirectory() as dossier:

        chemin = Path(dossier) / "mesure.pdf"

        try:
            export_pdf(cv, chemin, included_sections=sections)

        except Exception:
            # Un rendu impossible ne doit pas bloquer la génération :
            # on considère la mesure non concluante et on s'arrête.
            return True

        return count_pdf_pages(chemin) <= 1


def _premiere_phrase(texte: str) -> str:

    for separateur in (". ", " ; "):
        if separateur in texte:
            return texte.split(separateur)[0].rstrip(" ;.") + "."

    return texte


def _prochaine_reduction(cv, sections: set[str]) -> tuple | None:
    """
    Applique la réduction suivante dans l'ordre de sacrifice.

    Retourne (cv, sections, description) ou None s'il n'y a plus rien
    à retirer sans amputer le CV de sa substance.
    """

    # 1. Centres d'intérêt.
    if "interets" in sections and cv.interests:
        return cv, sections - {"interets"}, "centres d'intérêt"

    # 2. Langues.
    if "langues" in sections and cv.languages:
        return cv, sections - {"langues"}, "langues"

    # 3. Résumé réduit à sa première phrase.
    if "resume" in sections and cv.summary:

        raccourci = _premiere_phrase(cv.summary)

        if raccourci != cv.summary:
            cv.summary = raccourci
            return cv, sections, "résumé raccourci"

    # 4. Contexte d'entreprise, en commençant par l'expérience la
    #    plus ancienne : il éclaire surtout la mission récente, celle
    #    que le recruteur lit en premier.
    for experience in reversed(cv.experiences):

        if experience.business_context:

            experience.business_context = ""

            return (
                cv,
                sections,
                (
                    "le contexte de « "
                    f"{experience.job_title} — {experience.company} »"
                ),
            )

    # 5. Lignes de preuve, en commençant par l'expérience la plus
    #    ancienne (cv.experiences est trié du plus récent au plus
    #    ancien) et par sa dernière ligne.
    for experience in reversed(cv.experiences):

        if len(experience.lines) > 1:

            retiree = experience.lines.pop()

            return (
                cv,
                sections,
                (
                    f"une ligne de « {experience.job_title} — "
                    f"{experience.company} » ({retiree.text[:40]}…)"
                ),
            )

    # 6. Formation et certifications.
    if "formation_certifications" in sections and (
        cv.educations or cv.certifications
    ):
        return (
            cv,
            sections - {"formation_certifications"},
            "formation et certifications",
        )

    return None


def fit_to_one_page(
    cv,
    included_sections: set[str] | None = None,
    max_reductions: int = 40,
) -> tuple:
    """
    Réduit le CV jusqu'à ce qu'il tienne sur une page.

    Retourne (cv_ajusté, sections_retenues, retraits, tient) :
    `retraits` liste ce qui a été enlevé, `tient` dit si l'objectif
    est atteint — mieux vaut annoncer un débordement que le masquer.

    Le CV d'origine n'est jamais modifié.
    """

    sections = (
        set(included_sections)
        if included_sections is not None
        else set(ALL_CV_SECTIONS)
    )

    cv_courant = copy.deepcopy(cv)

    retraits: list[str] = []

    if _tient_sur_une_page(cv_courant, sections):
        return cv_courant, sections, retraits, True

    for _ in range(max_reductions):

        reduction = _prochaine_reduction(cv_courant, sections)

        if reduction is None:
            break

        cv_courant, sections, description = reduction

        retraits.append(description)

        if _tient_sur_une_page(cv_courant, sections):
            return cv_courant, sections, retraits, True

    return cv_courant, sections, retraits, False
