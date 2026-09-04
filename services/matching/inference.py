"""
Inférence de compétences non déclarées explicitement.

Deux mécanismes cohabitent :

- l'inférence lexicale, à partir de mots-clés de contexte ;
- l'inférence sémantique, à partir de la proximité de sens.

Les deux sont volontairement bridés : une compétence inférée reste une
hypothèse, et certaines compétences (techniques notamment) ne peuvent
jamais être inférées.
"""

from __future__ import annotations

from services.matching.config import (
    INFERENCE_KEYWORDS,
    SEMANTIC_INFERENCE_EXCLUDED,
    SEMANTIC_INFERENCE_SKILLS,
    SEMANTIC_INFERENCE_STRONG_THRESHOLD,
    SEMANTIC_INFERENCE_THRESHOLD,
    SEMANTIC_SPECIFICITY_THRESHOLD,
)
from services.matching.normalization import (
    _canonical_skill_name,
    _contains_term,
)
from services.skill_semantic_service import (
    find_semantic_skill_matches,
)


# ============================================================
# INFERENCE LEXICALE
# ============================================================

def _find_inference_evidence(
    canonical_skill: str,
    profile_text: str,
) -> list[str]:

    keywords = INFERENCE_KEYWORDS.get(
        canonical_skill,
        (),
    )

    found_keywords = []

    for keyword in keywords:

        if _contains_term(
            profile_text,
            keyword,
        ):

            found_keywords.append(
                keyword
            )

    if len(found_keywords) < 2:
        return []

    return [
        "Indices indirects trouvés : "
        + ", ".join(
            found_keywords[:5]
        )
    ]


# ============================================================
# INFERENCE SEMANTIQUE
# ============================================================

def _find_semantic_inference_evidence(
    canonical_skill: str,
    profile_texts: list[str],
) -> tuple[list[str], float] | None:
    """
    Recherche une compétence pouvant être déduite
    sémantiquement du parcours.

    L'analyse est effectuée bloc par bloc.

    IMPORTANT :

    - Les compétences explicitement exclues ne sont jamais
      inférées.
    - Un score sémantique faible ne suffit jamais.
    - Une formulation très spécifique peut renforcer
      une correspondance.
    - On conserve le meilleur bloc du parcours.
    """

    if not profile_texts:
        return None

    # ========================================================
    # SECURITE
    # ========================================================

    if canonical_skill in SEMANTIC_INFERENCE_EXCLUDED:
        return None

    if canonical_skill not in SEMANTIC_INFERENCE_SKILLS:
        return None

    best_match = None

    # ========================================================
    # ANALYSE BLOC PAR BLOC
    # ========================================================

    for profile_block in profile_texts:

        if not profile_block.strip():
            continue

        try:

            # On ne cherche qu'une compétence : inutile de faire
            # comparer tout le référentiel, et le restreindre évite
            # qu'elle soit évincée du classement par dix autres.
            semantic_matches = (
                find_semantic_skill_matches(
                    profile_block,
                    threshold=0.45,
                    limit=10,
                    restrict_to={canonical_skill},
                )
            )

        except Exception:

            continue

        # ====================================================
        # RECHERCHE DE LA COMPETENCE
        # ====================================================

        for semantic_match in semantic_matches:

            matched_skill = _canonical_skill_name(
                semantic_match.skill.canonical_name
            )

            if matched_skill != canonical_skill:
                continue

            semantic_score = float(
                getattr(
                    semantic_match,
                    "semantic_score",
                    semantic_match.score,
                )
            )

            specificity_score = float(
                getattr(
                    semantic_match,
                    "specificity_score",
                    0.0,
                )
            )

            context_score = float(
                getattr(
                    semantic_match,
                    "context_score",
                    0.0,
                )
            )

            final_score = float(
                semantic_match.score
            )

            candidate = (
                final_score,
                semantic_score,
                specificity_score,
                context_score,
                profile_block,
            )

            if (
                best_match is None
                or candidate[:4] > best_match[:4]
            ):

                best_match = candidate

    # ========================================================
    # AUCUNE CORRESPONDANCE
    # ========================================================

    if best_match is None:
        return None

    (
        final_score,
        semantic_score,
        specificity_score,
        context_score,
        matched_text,
    ) = best_match

    # ========================================================
    # REGLE SPECIALE :
    # FORMULATION TRES SPECIFIQUE
    # ========================================================

    # Une formulation très spécifique peut compenser une
    # similarité sémantique moyenne, mais uniquement lorsque
    # le contexte est également cohérent.

    if (
        semantic_score >= 0.48
        and specificity_score >= 0.90
        and context_score >= 0.20
    ):

        return (
            [
                (
                    "Correspondance sémantique renforcée "
                    "par une formulation très spécifique "
                    f"(sem={semantic_score:.2f}, "
                    f"spec={specificity_score:.2f}, "
                    f"ctx={context_score:.2f})."
                )
            ],
            semantic_score,
        )

    # ========================================================
    # REGLE 1 :
    # SEMANTIQUE TRES FORTE
    # ========================================================

    if (
        semantic_score
        >= SEMANTIC_INFERENCE_STRONG_THRESHOLD
        and (
            specificity_score >= 0.50
            or context_score >= 0.30
        )
    ):

        return (
            [
                (
                    "Correspondance sémantique forte "
                    f"(score={semantic_score:.2f}) "
                    "avec un élément précis du parcours."
                )
            ],
            semantic_score,
        )

    # ========================================================
    # REGLE 2 :
    # SEMANTIQUE FORTE + SPECIFICITE
    # ========================================================

    if (
        semantic_score >= 0.68
        and specificity_score
        >= SEMANTIC_SPECIFICITY_THRESHOLD
    ):

        return (
            [
                (
                    "Correspondance sémantique "
                    f"(score={semantic_score:.2f}) "
                    "renforcée par une formulation "
                    "spécifique "
                    f"(score={specificity_score:.2f})."
                )
            ],
            semantic_score,
        )

    # ========================================================
    # REGLE 3 :
    # SEMANTIQUE + CONTEXTE
    # ========================================================

    if (
        semantic_score
        >= SEMANTIC_INFERENCE_THRESHOLD
        and context_score >= 0.30
    ):

        return (
            [
                (
                    "Correspondance sémantique "
                    f"(score={semantic_score:.2f}) "
                    "renforcée par le contexte "
                    f"(score={context_score:.2f})."
                )
            ],
            semantic_score,
        )

    # ========================================================
    # RIEN DE SUFFISAMMENT FIABLE
    # ========================================================

    return None

