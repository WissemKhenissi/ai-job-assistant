"""
Objets de résultat du matching.

Structures de données pures, sans dépendance à la base ni au moteur.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.requirement_importance import (
    ESSENTIELLE,
    IMPORTANCE_PAR_DEFAUT,
)


# ============================================================
# OBJETS DE RESULTAT
# ============================================================

@dataclass
class SkillMatch:
    skill: str

    # Statuts possibles :
    #
    # - "proven"    : déclarée dans le Master CV ET soutenue par une
    #                 preuve EvidenceDB ;
    # - "declared"  : déclarée dans le Master CV, sans preuve ;
    # - "inferred"  : non déclarée, déduite du parcours — une
    #                 hypothèse, jamais un fait affirmé ;
    # - "missing"   : absente.
    status: str

    score: float
    evidence: list[str]
    explanation: str

    # Ce que l'annonce dit de cette exigence : "essentielle",
    # "souhaitee" ou "mention". Voir services.requirement_importance.
    # Une exigence non classée vaut "souhaitee" — le milieu, qui
    # n'exagère ni ne minimise l'écart.
    importance: str = IMPORTANCE_PAR_DEFAUT


# Compétences que le candidat possède réellement, à un degré de
# documentation près.
PRESENT_STATUSES = frozenset({"proven", "declared"})


@dataclass
class MatchingResult:
    score_global: float
    score_skills: float
    score_experience: float
    score_domain: float
    matches: list[SkillMatch]
    strengths: list[str]
    weaknesses: list[str]

    @property
    def matched_skills(self) -> list[str]:
        """
        Compétences présentes dans le Master CV, prouvées ou non.

        C'est la vision "est-ce que je couvre cette compétence ?",
        utilisée notamment par la mémoire de marché.

        Pour la génération de CV, utiliser proven_skills : seules les
        compétences prouvées peuvent être affichées comme ligne de
        compétence explicite.
        """

        return [
            match.skill
            for match in self.matches
            if match.status in PRESENT_STATUSES
        ]

    @property
    def proven_skills(self) -> list[str]:
        """Compétences soutenues par au moins une preuve EvidenceDB."""

        return [
            match.skill
            for match in self.matches
            if match.status == "proven"
        ]

    @property
    def declared_skills(self) -> list[str]:
        """Compétences déclarées dans le Master CV, sans preuve."""

        return [
            match.skill
            for match in self.matches
            if match.status == "declared"
        ]

    @property
    def inferred_skills(self) -> list[str]:
        return [
            match.skill
            for match in self.matches
            if match.status == "inferred"
        ]

    @property
    def missing_skills(self) -> list[str]:
        return [
            match.skill
            for match in self.matches
            if match.status == "missing"
        ]

    @property
    def missing_essential_skills(self) -> list[str]:
        """
        Les écarts qui décident vraiment : ce que l'annonce pose
        comme condition et que le profil ne couvre pas.

        Un pourcentage ne dit pas si une candidature vaut la peine ;
        cette liste, oui. Les mentions et les souhaits en sont
        exclus : ils restent visibles ailleurs, mais ils ne font pas
        échouer une candidature.
        """

        return [
            match.skill
            for match in self.matches
            if match.status == "missing"
            and match.importance == ESSENTIELLE
        ]

