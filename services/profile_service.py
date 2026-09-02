"""
Lecture et écriture du profil candidat (le Master CV).

Toute écriture ici modifie la source de vérité du projet : ce module
ne doit jamais recevoir une valeur inventée, seulement des données
fournies par le candidat lui-même (saisie manuelle ou import d'un
document existant).
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from database.db import SessionLocal
from database.models import (
    AchievementDB,
    CandidateDB,
    CertificationDB,
    EducationDB,
    EvidenceDB,
    ExperienceDB,
    SkillDB,
)


# ============================================================
# LECTURE
# ============================================================

def get_candidate():
    db = SessionLocal()

    try:
        return db.query(CandidateDB).first()
    finally:
        db.close()


def get_experiences():
    db = SessionLocal()

    try:
        return (
            db.query(ExperienceDB)
            .order_by(ExperienceDB.start_date.desc())
            .all()
        )
    finally:
        db.close()


def get_achievements(experience_id):
    db = SessionLocal()

    try:
        return (
            db.query(AchievementDB)
            .filter(AchievementDB.experience_id == experience_id)
            .all()
        )
    finally:
        db.close()


def get_skills(candidate_id):
    db = SessionLocal()

    try:
        return (
            db.query(SkillDB)
            .filter(SkillDB.candidate_id == candidate_id)
            .order_by(SkillDB.name)
            .all()
        )
    finally:
        db.close()


def get_evidence(candidate_id):
    db = SessionLocal()

    try:
        return (
            db.query(EvidenceDB)
            .filter(EvidenceDB.candidate_id == candidate_id)
            .all()
        )
    finally:
        db.close()


def get_educations(candidate_id):
    db = SessionLocal()

    try:
        return (
            db.query(EducationDB)
            .filter(EducationDB.candidate_id == candidate_id)
            .order_by(EducationDB.end_year.desc())
            .all()
        )
    finally:
        db.close()


def get_certifications(candidate_id):
    db = SessionLocal()

    try:
        return (
            db.query(CertificationDB)
            .filter(CertificationDB.candidate_id == candidate_id)
            .order_by(CertificationDB.obtained_year.desc())
            .all()
        )
    finally:
        db.close()


# ============================================================
# ECRITURE — CANDIDAT
# ============================================================

_CANDIDATE_FIELDS = {
    "first_name",
    "last_name",
    "email",
    "phone",
    "location",
    "linkedin_url",
    "portfolio_url",
    "summary",
    "headline",
    "availability",
    "languages",
    "interests",
    "motivations",
}


def update_candidate(candidate_id: str, **fields) -> None:
    """Met à jour les coordonnées / le résumé du candidat."""

    inconnus = set(fields) - _CANDIDATE_FIELDS

    if inconnus:
        raise ValueError(f"Champs inconnus : {inconnus}")

    db = SessionLocal()

    try:
        candidate = db.get(CandidateDB, candidate_id)

        if candidate is None:
            raise ValueError(f"Candidat introuvable : {candidate_id}")

        for champ, valeur in fields.items():
            setattr(candidate, champ, valeur)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# ECRITURE — EXPERIENCE
# ============================================================

_EXPERIENCE_FIELDS = {
    "company",
    "job_title",
    "location",
    "start_date",
    "end_date",
    "description",
    "business_context",
    "team_context",
}


def add_experience(
    candidate_id: str,
    company: str,
    job_title: str,
    start_date: date,
    end_date: date | None = None,
    location: str = "",
    description: str = "",
    business_context: str = "",
    team_context: str = "",
    experience_id: str | None = None,
) -> str:

    db = SessionLocal()

    try:
        experience = ExperienceDB(
            id=experience_id or f"experience-{uuid4()}",
            candidate_id=candidate_id,
            company=company,
            job_title=job_title,
            location=location,
            start_date=start_date,
            end_date=end_date,
            description=description,
            business_context=business_context,
            team_context=team_context,
        )

        db.add(experience)
        db.commit()

        return experience.id

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def update_experience(experience_id: str, **fields) -> None:

    inconnus = set(fields) - _EXPERIENCE_FIELDS

    if inconnus:
        raise ValueError(f"Champs inconnus : {inconnus}")

    db = SessionLocal()

    try:
        experience = db.get(ExperienceDB, experience_id)

        if experience is None:
            raise ValueError(
                f"Expérience introuvable : {experience_id}"
            )

        for champ, valeur in fields.items():
            setattr(experience, champ, valeur)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# ECRITURE — REALISATION
# ============================================================

_ACHIEVEMENT_FIELDS = {
    "title",
    "situation",
    "action",
    "result",
    "metrics",
    "description",
}


def add_achievement(
    experience_id: str,
    title: str,
    situation: str = "",
    action: str = "",
    result: str = "",
    metrics: str = "",
    description: str = "",
    achievement_id: str | None = None,
) -> str:

    db = SessionLocal()

    try:
        achievement = AchievementDB(
            id=achievement_id or f"achievement-{uuid4()}",
            experience_id=experience_id,
            title=title,
            situation=situation,
            action=action,
            result=result,
            metrics=metrics,
            description=description,
        )

        db.add(achievement)
        db.commit()

        return achievement.id

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def update_achievement(achievement_id: str, **fields) -> None:

    inconnus = set(fields) - _ACHIEVEMENT_FIELDS

    if inconnus:
        raise ValueError(f"Champs inconnus : {inconnus}")

    db = SessionLocal()

    try:
        achievement = db.get(AchievementDB, achievement_id)

        if achievement is None:
            raise ValueError(
                f"Réalisation introuvable : {achievement_id}"
            )

        for champ, valeur in fields.items():
            setattr(achievement, champ, valeur)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# ECRITURE — COMPETENCE
# ============================================================

_SKILL_FIELDS = {
    "name",
    "category",
    "level",
    "years_experience",
    "description",
}


def add_skill(
    candidate_id: str,
    name: str,
    category: str = "",
    level: str = "",
    years_experience: float | None = None,
    description: str = "",
) -> str:
    """
    Ajoute une compétence déclarée.

    Si une compétence de ce nom existe déjà pour ce candidat, son
    identifiant est retourné sans rien créer — c'est cette absence de
    contrôle qui avait produit 13 lignes en double dans le profil.
    """

    db = SessionLocal()

    try:
        existante = (
            db.query(SkillDB)
            .filter(
                SkillDB.candidate_id == candidate_id,
                SkillDB.name == name,
            )
            .one_or_none()
        )

        if existante is not None:
            return existante.id

        skill = SkillDB(
            id=f"skill-{uuid4()}",
            candidate_id=candidate_id,
            name=name,
            category=category,
            level=level,
            years_experience=years_experience,
            description=description,
        )

        db.add(skill)
        db.commit()

        return skill.id

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def update_skill(skill_id: str, **fields) -> None:

    inconnus = set(fields) - _SKILL_FIELDS

    if inconnus:
        raise ValueError(f"Champs inconnus : {inconnus}")

    db = SessionLocal()

    try:
        skill = db.get(SkillDB, skill_id)

        if skill is None:
            raise ValueError(f"Compétence introuvable : {skill_id}")

        for champ, valeur in fields.items():
            setattr(skill, champ, valeur)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# ECRITURE — PREUVE
# ============================================================

def add_evidence(
    candidate_id: str,
    skill_id: str,
    description: str,
    experience_id: str | None = None,
    achievement_id: str | None = None,
    evidence_type: str = "Expérience professionnelle",
    metric: str = "",
    context: str = "",
    evidence_id: str | None = None,
) -> str:
    """
    Ajoute une preuve à l'appui d'une compétence.

    C'est cette table, et elle seule, qui fait passer une compétence
    du statut "declared" au statut "proven" dans le moteur de
    matching.
    """

    db = SessionLocal()

    try:
        evidence = EvidenceDB(
            id=evidence_id or f"evidence-{uuid4()}",
            candidate_id=candidate_id,
            skill_id=skill_id,
            experience_id=experience_id,
            achievement_id=achievement_id,
            evidence_type=evidence_type,
            description=description,
            metric=metric,
            context=context,
        )

        db.add(evidence)
        db.commit()

        return evidence.id

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# ECRITURE — FORMATION
# ============================================================

_EDUCATION_FIELDS = {
    "institution",
    "degree",
    "field_of_study",
    "start_year",
    "end_year",
    "description",
}


def add_education(
    candidate_id: str,
    institution: str,
    degree: str,
    field_of_study: str = "",
    start_year: int | None = None,
    end_year: int | None = None,
    description: str = "",
    education_id: str | None = None,
) -> str:

    db = SessionLocal()

    try:
        education = EducationDB(
            id=education_id or f"education-{uuid4()}",
            candidate_id=candidate_id,
            institution=institution,
            degree=degree,
            field_of_study=field_of_study,
            start_year=start_year,
            end_year=end_year,
            description=description,
        )

        db.add(education)
        db.commit()

        return education.id

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def update_education(education_id: str, **fields) -> None:

    inconnus = set(fields) - _EDUCATION_FIELDS

    if inconnus:
        raise ValueError(f"Champs inconnus : {inconnus}")

    db = SessionLocal()

    try:
        education = db.get(EducationDB, education_id)

        if education is None:
            raise ValueError(f"Formation introuvable : {education_id}")

        for champ, valeur in fields.items():
            setattr(education, champ, valeur)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def delete_education(education_id: str) -> None:

    db = SessionLocal()

    try:
        education = db.get(EducationDB, education_id)

        if education is not None:
            db.delete(education)
            db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# ECRITURE — CERTIFICATION
# ============================================================

_CERTIFICATION_FIELDS = {
    "name",
    "organization",
    "obtained_year",
    "credential_url",
    "description",
}


def add_certification(
    candidate_id: str,
    name: str,
    organization: str = "",
    obtained_year: int | None = None,
    credential_url: str = "",
    description: str = "",
    certification_id: str | None = None,
) -> str:

    db = SessionLocal()

    try:
        certification = CertificationDB(
            id=certification_id or f"certification-{uuid4()}",
            candidate_id=candidate_id,
            name=name,
            organization=organization,
            obtained_year=obtained_year,
            credential_url=credential_url,
            description=description,
        )

        db.add(certification)
        db.commit()

        return certification.id

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def update_certification(certification_id: str, **fields) -> None:

    inconnus = set(fields) - _CERTIFICATION_FIELDS

    if inconnus:
        raise ValueError(f"Champs inconnus : {inconnus}")

    db = SessionLocal()

    try:
        certification = db.get(CertificationDB, certification_id)

        if certification is None:
            raise ValueError(
                f"Certification introuvable : {certification_id}"
            )

        for champ, valeur in fields.items():
            setattr(certification, champ, valeur)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def delete_certification(certification_id: str) -> None:

    db = SessionLocal()

    try:
        certification = db.get(CertificationDB, certification_id)

        if certification is not None:
            db.delete(certification)
            db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
