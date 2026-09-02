"""
Normalisation du texte et résolution des noms de compétences.

skill_catalog est l'unique source de vérité pour les alias : ce module
ne contient aucune table d'alias en dur, il lit le référentiel.
"""

from __future__ import annotations

import re
import unicodedata

from services.skill_catalog_service import (
    get_active_skills,
    normalize_skill_text,
)


# ============================================================
# NORMALISATION
# ============================================================

def _normalize(value: str) -> str:

    if not value:
        return ""

    normalized = unicodedata.normalize(
        "NFKD",
        value,
    )

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    normalized = normalized.casefold()

    normalized = re.sub(
        r"[-_/]",
        " ",
        normalized,
    )

    normalized = re.sub(
        r"[^a-z0-9 ]",
        " ",
        normalized,
    )

    return re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()


def _contains_term(
    text: str,
    term: str,
) -> bool:

    normalized_text = _normalize(text)
    normalized_term = _normalize(term)

    if not normalized_term:
        return False

    pattern = (
        rf"(?<![a-z0-9])"
        rf"{re.escape(normalized_term)}"
        rf"(?![a-z0-9])"
    )

    return (
        re.search(
            pattern,
            normalized_text,
            flags=re.IGNORECASE,
        )
        is not None
    )


_canonical_alias_index_cache: dict[str, str] | None = None


def _canonical_alias_index() -> dict[str, str]:
    """
    Construit (une seule fois par process) l'index
    "alias normalisé -> nom canonique normalisé" à partir du
    référentiel skill_catalog.

    Remplace l'ancien dictionnaire SKILL_ALIASES codé en dur :
    skill_catalog est désormais l'unique source de vérité pour les
    alias de compétences.
    """

    global _canonical_alias_index_cache

    if _canonical_alias_index_cache is None:

        index: dict[str, str] = {}

        for skill in get_active_skills():

            canonical_key = normalize_skill_text(
                skill.canonical_name
            )

            for name in (
                skill.canonical_name,
                *skill.aliases,
            ):

                index[normalize_skill_text(name)] = canonical_key

        _canonical_alias_index_cache = index

    return _canonical_alias_index_cache


def _canonical_skill_name(
    value: str,
) -> str:

    normalized_value = _normalize(value)

    return _canonical_alias_index().get(
        normalized_value,
        normalized_value,
    )

