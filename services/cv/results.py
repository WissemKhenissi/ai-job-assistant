"""
Structures d'un CV ciblé.

Objets de données purs : ils ne contiennent que du contenu issu du
Master CV, chaque élément gardant l'identifiant de sa source pour
rester traçable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class CVEvidenceLine:
    """
    Une ligne de preuve retenue pour le CV.

    `evidence_id` et `skill` permettent de remonter à la donnée du
    Master CV qui justifie cette ligne : aucune ligne ne peut
    apparaître sans source.
    """

    text: str
    skill: str
    evidence_id: str


@dataclass(frozen=True)
class CVAchievementLine:
    """
    Une réalisation, mise en forme pour le CV.

    C'est ici que vivent les chiffres du parcours : aucune preuve du
    Master CV n'en porte. `title` est affiché en gras, `detail` à sa
    suite, et `achievement_id` permet de remonter à la source.
    """

    title: str
    detail: str
    achievement_id: str

    @property
    def text(self) -> str:
        return f"{self.title} — {self.detail}" if self.detail else self.title


@dataclass
class CVExperience:
    experience_id: str
    job_title: str
    company: str
    location: str
    start_date: date
    end_date: date | None
    business_context: str

    # Les réalisations passent avant les preuves : une réussite prime
    # sur une description de tâche (§8, §17).
    achievement_lines: list[CVAchievementLine] = field(
        default_factory=list
    )

    lines: list[CVEvidenceLine] = field(default_factory=list)


@dataclass
class CVAchievement:
    achievement_id: str
    experience_id: str
    title: str
    situation: str
    action: str
    result: str
    metrics: str


@dataclass(frozen=True)
class CVSkillGroup:
    """
    Un regroupement de compétences prouvées par catégorie du
    référentiel skill_catalog (ex. "Product", "Data", "Business").
    """

    category: str
    skills: tuple[str, ...]


@dataclass(frozen=True)
class CVEducation:
    institution: str
    degree: str
    field_of_study: str
    start_year: int | None
    end_year: int | None


@dataclass(frozen=True)
class CVCertification:
    name: str
    organization: str
    obtained_year: int | None


@dataclass
class TargetedCV:
    """
    CV ciblé sur une offre.

    `skills` ne contient que des compétences au statut "proven" : une
    compétence déclarée sans preuve ou seulement déduite ne peut pas
    figurer comme ligne de compétence.

    `declared_skills` et `inferred_skills` sont exposées à titre
    informatif — pour que l'utilisateur voie ce qui a été
    volontairement laissé de côté — mais ne font pas partie du CV.
    """

    candidate_id: str
    full_name: str
    email: str
    phone: str
    location: str
    linkedin_url: str
    summary: str

    headline: str = ""
    availability: str = ""
    languages: str = ""
    interests: str = ""

    job_offer_id: str = ""
    job_offer_title: str = ""
    job_offer_company: str = ""

    # Titre affiché sous le nom : l'intitulé du poste visé. Un CV sans
    # titre oblige le recruteur à deviner la candidature à laquelle il
    # correspond. Ce titre annonce une cible, pas un poste occupé — le
    # parcours, lui, reste dans les expériences.
    cv_title: str = ""

    skills: list[str] = field(default_factory=list)
    skill_groups: list[CVSkillGroup] = field(default_factory=list)

    # Seuil choisi pour la rubrique compétences : ("proven",) laisse
    # le système garantir chaque ligne ; au-delà, c'est le candidat
    # qui atteste. Conservé ici pour que le contrôle et la trace
    # sachent ce qui avait été autorisé.
    skill_levels: tuple[str, ...] = ("proven",)

    experiences: list[CVExperience] = field(default_factory=list)
    achievements: list[CVAchievement] = field(default_factory=list)

    # La formation et les certifications ne sont pas filtrées par
    # offre : elles sont vraies quelle que soit l'annonce visée.
    educations: list[CVEducation] = field(default_factory=list)
    certifications: list[CVCertification] = field(default_factory=list)

    # Transparence : ce que le CV n'affiche volontairement pas.
    declared_skills: list[str] = field(default_factory=list)
    inferred_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)

    @property
    def total_lines(self) -> int:
        """Puces affichées, réalisations comprises."""

        return sum(
            len(experience.lines) + len(experience.achievement_lines)
            for experience in self.experiences
        )
