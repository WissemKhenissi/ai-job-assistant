"""
Objets de résultat du matching.

Structures de données pures, sans dépendance à la base ni au moteur.
"""

from __future__ import annotations

from dataclasses import dataclass


# ============================================================
# OBJETS DE RESULTAT
# ============================================================

@dataclass
class SkillMatch:
    skill: str
    status: str
    score: float
    evidence: list[str]
    explanation: str


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
        return [
            match.skill
            for match in self.matches
            if match.status == "proven"
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

