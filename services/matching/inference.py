"""
Inférence de compétences non déclarées explicitement.

Deux mécanismes cohabitent :

- l'inférence lexicale, à partir d'indices trouvés dans le parcours ;
- l'inférence sémantique, à partir de la proximité de sens.

Les deux sont volontairement bridés : une compétence inférée reste une
hypothèse, et certaines compétences ne peuvent jamais être inférées.

Ce que « certaines » recouvre a changé le 5 septembre 2026. Le moteur
portait deux listes écrites à la main : douze compétences produit
seules autorisées à l'inférence, onze technologies explicitement
interdites. Sur un référentiel de quarante-six entrées choisies pour
un profil, cela passait. Sur treize mille, la liste blanche
condamnait 13 464 compétences au silence — un profil d'infirmière ou
de développeur ne pouvait produire que « prouvé », « déclaré » ou
« manquant », jamais « déduit ».

La distinction n'a pourtant rien de propre à un métier : un
savoir-faire se devine d'un récit d'expérience, un outil ou un corpus
de connaissances non. Elle est donc portée par le référentiel
(`skill_catalog.is_inferable`), qui décrit les compétences et qui
seul peut suivre quand il en accueille treize mille.

Même bascule pour le reste : les indices de l'inférence lexicale
viennent des alias que le référentiel porte déjà, et l'inférence
composite lit la composition qu'il déclare, au lieu des neuf
composantes d'une seule compétence écrites dans le moteur.
"""

from __future__ import annotations

from services.matching.config import (
    MIN_INFERENCE_INDICES,
    SEMANTIC_INFERENCE_STRONG_THRESHOLD,
    SEMANTIC_INFERENCE_THRESHOLD,
    SEMANTIC_SPECIFICITY_THRESHOLD,
)
from services.matching.normalization import (
    _canonical_skill_name,
    _contains_term,
)
from services.skill_catalog_service import find_skill_by_name
from services.skill_semantic_service import (
    _mots_signifiants,
    find_semantic_skill_matches,
)


# ============================================================
# CE QUE LE REFERENTIEL AUTORISE
# ============================================================

def _est_deductible(canonical_skill: str) -> bool:
    """
    Le référentiel autorise-t-il à déduire cette compétence ?

    Une compétence qu'il ne connaît pas n'est pas déduite : sans
    entrée pour la décrire, rien ne permet de dire si elle relève du
    savoir-faire ou de l'outillage, et le doute doit se résoudre du
    côté prudent.
    """

    entree = find_skill_by_name(canonical_skill)

    return entree is not None and entree.is_inferable


# ============================================================
# INFERENCE LEXICALE
# ============================================================

def _indices_possibles(canonical_skill: str) -> tuple[str, ...]:
    """
    Les termes dont la présence dans un parcours trahit la compétence.

    Ce sont ses alias, et rien d'autre : les autres façons de la
    nommer. Les retrouver dans un parcours, c'est y lire la
    compétence sous un autre mot. Elles viennent du référentiel — un
    dictionnaire de mots-clés écrit dans le moteur ne couvrait qu'un
    métier.

    S'y ajoutent les mots marquants de sa description : ce que le
    référentiel dit qu'elle est. C'est le remplaçant direct du
    dictionnaire de mots-clés, qui décrivait à la main le champ
    lexical de douze compétences produit.

    Les NOMS des compétences associées en sont volontairement
    absents, bien que le référentiel les porte : en constater deux,
    c'est faire de l'inférence composite avec un seuil plus bas et
    sans son garde-fou. Le raisonnement « il pratique ces compétences
    voisines, donc il a celle-ci » a un mécanisme dédié, qui exige
    que le référentiel ait déclaré la composition.

    Le nom canonique est lui aussi exclu : s'il figurait dans le
    parcours, la compétence serait déclarée, pas déduite.
    """

    entree = find_skill_by_name(canonical_skill)

    if entree is None:
        return ()

    indices: list[str] = []

    for terme in (
        *entree.aliases,
        *_mots_signifiants(entree.description),
    ):

        terme = (terme or "").strip()

        # Un indice d'un seul caractère (« R ») se retrouve partout
        # dès qu'on cherche par frontière de mot.
        if len(terme) < 2:
            continue

        if _canonical_skill_name(terme) == canonical_skill:
            continue

        if terme not in indices:
            indices.append(terme)

    return tuple(indices)


def _find_inference_evidence(
    canonical_skill: str,
    profile_text: str,
) -> list[str]:

    if not _est_deductible(canonical_skill):
        return []

    found_keywords = []

    for keyword in _indices_possibles(canonical_skill):

        if _contains_term(
            profile_text,
            keyword,
        ):

            found_keywords.append(
                keyword
            )

    if len(found_keywords) < MIN_INFERENCE_INDICES:
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

    - Une compétence que le référentiel déclare non déductible
      n'est jamais inférée.
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

    if not _est_deductible(canonical_skill):
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
