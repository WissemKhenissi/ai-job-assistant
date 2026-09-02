from datetime import date

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ============================================================
# CANDIDAT
# ============================================================

class CandidateDB(Base):

    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    first_name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    last_name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String,
        default=""
    )

    phone: Mapped[str] = mapped_column(
        String,
        default=""
    )

    location: Mapped[str] = mapped_column(
        String,
        default=""
    )

    linkedin_url: Mapped[str] = mapped_column(
        String,
        default=""
    )

    portfolio_url: Mapped[str] = mapped_column(
        String,
        default=""
    )

    summary: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    # Accroche affichée sous le nom sur le CV
    # (ex. "Product / Chef de projet digital — E-commerce & Tech").
    headline: Mapped[str] = mapped_column(
        String,
        default=""
    )

    # Ex. "Disponible immédiatement", "Disponible sous 1 mois".
    availability: Mapped[str] = mapped_column(
        String,
        default=""
    )

    languages: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    interests: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    # Projet professionnel, reconversion, intérêt pour un secteur ou
    # une entreprise : uniquement ce que le candidat a explicitement
    # fourni, jamais déduit. Alimente la lettre de motivation rédigée
    # par l'IA (services/ai/letter_authoring.py).
    motivations: Mapped[str] = mapped_column(
        Text,
        default=""
    )


# ============================================================
# EXPERIENCE
# ============================================================

class ExperienceDB(Base):

    __tablename__ = "experiences"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    candidate_id: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    company: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    job_title: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    location: Mapped[str] = mapped_column(
        String,
        default=""
    )

    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    description: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    business_context: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    team_context: Mapped[str] = mapped_column(
        Text,
        default=""
    )


# ============================================================
# REALISATIONS
# ============================================================

class AchievementDB(Base):

    __tablename__ = "achievements"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    experience_id: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    title: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    situation: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    action: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    result: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    metrics: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    description: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    # ============================================================
# COMPETENCES
# ============================================================

class SkillDB(Base):

    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    candidate_id: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    category: Mapped[str] = mapped_column(
        String,
        default=""
    )

    level: Mapped[str] = mapped_column(
        String,
        default=""
    )

    years_experience: Mapped[float | None] = mapped_column(
        nullable=True
    )

    description: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    # ============================================================
# PREUVES DE COMPETENCES
# ============================================================

class EvidenceDB(Base):

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    candidate_id: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    skill_id: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    experience_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    achievement_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    evidence_type: Mapped[str] = mapped_column(
        String,
        default=""
    )

    description: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    metric: Mapped[str] = mapped_column(
        String,
        default=""
    )

    context: Mapped[str] = mapped_column(
        Text,
        default=""
    )


    # ============================================================
# REFERENTIEL GENERIQUE DES COMPETENCES
# ============================================================

class SkillCatalogDB(Base):

    __tablename__ = "skill_catalog"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    canonical_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
        index=True
    )

    category: Mapped[str] = mapped_column(
        String,
        default=""
    )

    subcategory: Mapped[str] = mapped_column(
        String,
        default=""
    )

    description: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    aliases: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    parent_skill_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    related_skills: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False
    )


# ============================================================
# FORMATION
# ============================================================

class EducationDB(Base):

    __tablename__ = "education"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    candidate_id: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    institution: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    degree: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    field_of_study: Mapped[str] = mapped_column(
        String,
        default=""
    )

    start_year: Mapped[int | None] = mapped_column(
        nullable=True
    )

    end_year: Mapped[int | None] = mapped_column(
        nullable=True
    )

    description: Mapped[str] = mapped_column(
        Text,
        default=""
    )


# ============================================================
# CERTIFICATIONS
# ============================================================

class CertificationDB(Base):

    __tablename__ = "certifications"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    candidate_id: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    organization: Mapped[str] = mapped_column(
        String,
        default=""
    )

    # Année seule, comme pour EducationDB : le mois d'obtention n'est
    # presque jamais connu, et une date complète imposerait de
    # fabriquer un jour arbitraire.
    obtained_year: Mapped[int | None] = mapped_column(
        nullable=True
    )

    credential_url: Mapped[str] = mapped_column(
        String,
        default=""
    )

    description: Mapped[str] = mapped_column(
        Text,
        default=""
    )