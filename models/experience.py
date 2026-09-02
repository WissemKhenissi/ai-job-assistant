from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class Achievement(BaseModel):
    """
    Une réalisation concrète obtenue pendant une expérience.
    """

    title: str = ""

    situation: str = ""

    action: str = ""

    description: str = ""

    result: Optional[str] = None

    metrics: List[str] = Field(default_factory=list)


class Experience(BaseModel):
    """
    Représente une expérience professionnelle complète.

    Ce modèle ne correspond pas directement à une ligne de CV.
    Il sert à stocker l'ensemble des informations disponibles
    sur une expérience afin que l'IA puisse ensuite sélectionner
    les éléments pertinents pour chaque candidature.
    """

    # ---------------------------------------------------------
    # IDENTIFICATION
    # ---------------------------------------------------------

    id: str

    company: str

    job_title: str

    start_date: date

    end_date: Optional[date] = None

    current: bool = False

    location: Optional[str] = None

    # ---------------------------------------------------------
    # CONTEXTE
    # ---------------------------------------------------------

    business_context: str = ""

    team_context: str = ""

    description: str = ""

    # ---------------------------------------------------------
    # RESPONSABILITÉS
    # ---------------------------------------------------------

    responsibilities: List[str] = Field(default_factory=list)

    # ---------------------------------------------------------
    # RÉALISATIONS
    # ---------------------------------------------------------

    achievements: List[Achievement] = Field(default_factory=list)

    # ---------------------------------------------------------
    # PROJETS
    # ---------------------------------------------------------

    projects: List[str] = Field(default_factory=list)

    # ---------------------------------------------------------
    # PROBLÈMES ET CHALLENGES
    # ---------------------------------------------------------

    challenges: List[str] = Field(default_factory=list)

    solutions: List[str] = Field(default_factory=list)

    # ---------------------------------------------------------
    # OUTILS ET TECHNOLOGIES
    # ---------------------------------------------------------

    tools: List[str] = Field(default_factory=list)

    technologies: List[str] = Field(default_factory=list)

    # ---------------------------------------------------------
    # COMPÉTENCES
    # ---------------------------------------------------------

    skills: List[str] = Field(default_factory=list)

    transferable_skills: List[str] = Field(default_factory=list)

    # ---------------------------------------------------------
    # PARTIES PRENANTES
    # ---------------------------------------------------------

    stakeholders: List[str] = Field(default_factory=list)

    # ---------------------------------------------------------
    # DONNÉES / KPI
    # ---------------------------------------------------------

    kpis: List[str] = Field(default_factory=list)

    # ---------------------------------------------------------
    # PREUVES
    # ---------------------------------------------------------

    evidence: List[str] = Field(default_factory=list)
