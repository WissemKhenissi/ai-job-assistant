"""
Construction des représentations textuelles du profil candidat.

Le moteur compare des compétences attendues à du texte issu du Master
CV : ce module assemble ce texte, en un bloc global ou découpé par
élément de parcours.
"""

from __future__ import annotations

from typing import Iterable

from database.models import (
    AchievementDB,
    EvidenceDB,
    ExperienceDB,
    SkillDB,
)

from services.matching.normalization import _normalize


# ============================================================
# PROFIL — TEXTE GLOBAL
# ============================================================

def _text_from_profile(
    skills: Iterable[SkillDB],
    experiences: Iterable[ExperienceDB],
    achievements: Iterable[AchievementDB],
    evidence: Iterable[EvidenceDB],
) -> str:

    parts: list[str] = []

    # --------------------------------------------------------
    # COMPETENCES
    # --------------------------------------------------------

    for skill in skills:

        parts.extend(
            [
                skill.name or "",
                skill.description or "",
                skill.category or "",
            ]
        )

    # --------------------------------------------------------
    # EXPERIENCES
    # --------------------------------------------------------

    for experience in experiences:

        parts.extend(
            [
                experience.company or "",
                experience.job_title or "",
                experience.description or "",
                experience.business_context or "",
                experience.team_context or "",
            ]
        )

    # --------------------------------------------------------
    # REALISATIONS
    # --------------------------------------------------------

    for achievement in achievements:

        parts.extend(
            [
                achievement.title or "",
                achievement.situation or "",
                achievement.action or "",
                achievement.result or "",
                achievement.metrics or "",
                achievement.description or "",
            ]
        )

    # --------------------------------------------------------
    # PREUVES
    # --------------------------------------------------------

    for item in evidence:

        parts.extend(
            [
                item.description or "",
                item.metric or "",
                item.context or "",
            ]
        )

    return _normalize(
        " ".join(parts)
    )


# ============================================================
# PROFIL — BLOCS POUR L'INFERENCE SEMANTIQUE
# ============================================================

def _profile_text_blocks(
    skills: Iterable[SkillDB],
    experiences: Iterable[ExperienceDB],
    achievements: Iterable[AchievementDB],
    evidence: Iterable[EvidenceDB],
) -> list[str]:

    blocks: list[str] = []

    # --------------------------------------------------------
    # COMPETENCES DECLAREES
    # --------------------------------------------------------

    for skill in skills:

        text = " ".join(
            [
                skill.name or "",
                skill.description or "",
                skill.category or "",
            ]
        ).strip()

        if text:

            blocks.append(
                _normalize(text)
            )

    # --------------------------------------------------------
    # EXPERIENCES
    # --------------------------------------------------------

    for experience in experiences:

        text = " ".join(
            [
                experience.company or "",
                experience.job_title or "",
                experience.description or "",
                experience.business_context or "",
                experience.team_context or "",
            ]
        ).strip()

        if text:

            blocks.append(
                _normalize(text)
            )

    # --------------------------------------------------------
    # REALISATIONS
    # --------------------------------------------------------

    for achievement in achievements:

        text = " ".join(
            [
                achievement.title or "",
                achievement.situation or "",
                achievement.action or "",
                achievement.result or "",
                achievement.metrics or "",
                achievement.description or "",
            ]
        ).strip()

        if text:

            blocks.append(
                _normalize(text)
            )

    # --------------------------------------------------------
    # PREUVES
    # --------------------------------------------------------

    for item in evidence:

        text = " ".join(
            [
                item.description or "",
                item.metric or "",
                item.context or "",
            ]
        ).strip()

        if text:

            blocks.append(
                _normalize(text)
            )

    return blocks


# ============================================================
# FORMATAGE DES PREUVES
# ============================================================

def _format_evidence(
    item: EvidenceDB,
) -> str:

    parts = []

    if item.description:
        parts.append(
            item.description
        )

    if item.metric:
        parts.append(
            item.metric
        )

    if item.context:
        parts.append(
            item.context
        )

    return " — ".join(parts)

