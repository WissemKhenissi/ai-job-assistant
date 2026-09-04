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

def list_candidates() -> list[dict]:
    """
    Les profils existants, en primitives, du plus ancien au plus
    récent — l'ordre de création est le plus lisible dans un
    sélecteur.
    """

    db = SessionLocal()

    try:
        return [
            {
                "id": candidat.id,
                "full_name": (
                    f"{candidat.first_name} {candidat.last_name}"
                ).strip()
                or "Profil sans nom",
                "headline": candidat.headline or "",
            }
            for candidat in db.query(CandidateDB)
            .order_by(CandidateDB.id)
            .all()
        ]

    finally:
        db.close()


def get_candidate(candidate_id: str | None = None):
    """
    Le profil demandé, ou le premier de la base si aucun n'est
    précisé.

    Le repli existe pour le démarrage de l'application, quand aucun
    profil n'a encore été choisi. Partout ailleurs, passer
    l'identifiant : sans lui, deux profils en base se mélangeraient.
    """

    db = SessionLocal()

    try:

        if candidate_id:
            return db.get(CandidateDB, candidate_id)

        return db.query(CandidateDB).order_by(CandidateDB.id).first()

    finally:
        db.close()


def get_experiences(candidate_id: str | None = None):
    """
    Les expériences d'un candidat, de la plus récente à la plus
    ancienne.

    `candidate_id` est facultatif pour ne pas casser les appels
    existants, mais l'omettre retourne le parcours de **tous** les
    candidats : ne l'omettre que s'il est certain qu'il n'y en a
    qu'un.
    """

    db = SessionLocal()

    try:
        requete = db.query(ExperienceDB)

        if candidate_id:
            requete = requete.filter(
                ExperienceDB.candidate_id == candidate_id
            )

        return requete.order_by(
            ExperienceDB.start_date.desc()
        ).all()

    finally:
        db.close()


def create_candidate(
    first_name: str = "",
    last_name: str = "",
    candidate_id: str | None = None,
) -> str:
    """Crée un profil vide et retourne son identifiant."""

    db = SessionLocal()

    try:
        identifiant = candidate_id or f"candidate-{uuid4()}"

        db.add(
            CandidateDB(
                id=identifiant,
                first_name=first_name.strip(),
                last_name=last_name.strip(),
            )
        )

        db.commit()

        return identifiant

    except Exception:
        db.rollback()
        raise

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


def delete_skill(skill_id: str) -> None:
    """
    Supprime une compétence ET les preuves qui lui sont rattachées.

    Supprimer la compétence seule laisserait des EvidenceDB orphelines,
    pointant vers un skill_id inexistant : elles resteraient comptées
    par le moteur de matching, qui continuerait de croire la compétence
    "prouvée". La suppression doit donc emporter ses preuves.
    """

    db = SessionLocal()

    try:
        skill = db.get(SkillDB, skill_id)

        if skill is None:
            return

        (
            db.query(EvidenceDB)
            .filter(EvidenceDB.skill_id == skill_id)
            .delete(synchronize_session=False)
        )

        db.delete(skill)
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


def count_candidate_data(candidate_id: str) -> dict[str, int]:
    """
    Ce qu'un profil contient, table par table.

    Sert d'abord à l'écran de suppression : on ne détruit pas un
    parcours sans dire ce qu'il contenait.
    """

    from database.models import GeneratedCVDB, InterviewExchangeDB
    from models.application import ApplicationDB
    from models.matching import JobMatchDB

    db = SessionLocal()

    try:
        experiences = (
            db.query(ExperienceDB)
            .filter(ExperienceDB.candidate_id == candidate_id)
            .all()
        )

        identifiants = [item.id for item in experiences]

        realisations = (
            db.query(AchievementDB)
            .filter(AchievementDB.experience_id.in_(identifiants))
            .count()
            if identifiants
            else 0
        )

        def _compter(modele) -> int:
            return (
                db.query(modele)
                .filter(modele.candidate_id == candidate_id)
                .count()
            )

        return {
            "experiences": len(experiences),
            "realisations": realisations,
            "competences": _compter(SkillDB),
            "preuves": _compter(EvidenceDB),
            "formations": _compter(EducationDB),
            "certifications": _compter(CertificationDB),
            "analyses": _compter(JobMatchDB),
            "candidatures": _compter(ApplicationDB),
            "cv_generes": _compter(GeneratedCVDB),
            "echanges_entretien": _compter(InterviewExchangeDB),
        }

    finally:
        db.close()


def delete_candidate(candidate_id: str) -> dict[str, int]:
    """
    Supprime un profil et tout ce qui lui est rattaché.

    Irréversible, et sans filet : aucune corbeille, aucune
    restauration. L'appelant doit avoir fait confirmer explicitement.
    Retourne le décompte de ce qui a été supprimé, pour que
    l'utilisateur voie l'ampleur de ce qu'il vient de faire.

    Les annonces ne sont pas touchées : elles ne sont pas la propriété
    d'un candidat, seules les analyses qui les relient à lui le sont.
    """

    from database.models import GeneratedCVDB, InterviewExchangeDB
    from models.application import ApplicationDB
    from models.matching import JobMatchDB
    from models.skill_match import JobSkillMatchDB

    decompte = count_candidate_data(candidate_id)

    db = SessionLocal()

    try:
        candidat = db.get(CandidateDB, candidate_id)

        if candidat is None:
            raise ValueError(f"Profil introuvable : {candidate_id}")

        # Le détail par compétence pend aux analyses : sans cette
        # première passe, il resterait des lignes orphelines.
        analyses = (
            db.query(JobMatchDB)
            .filter(JobMatchDB.candidate_id == candidate_id)
            .all()
        )

        for analyse in analyses:
            db.query(JobSkillMatchDB).filter(
                JobSkillMatchDB.job_match_id == analyse.id
            ).delete(synchronize_session=False)

        experiences = (
            db.query(ExperienceDB)
            .filter(ExperienceDB.candidate_id == candidate_id)
            .all()
        )

        identifiants = [item.id for item in experiences]

        if identifiants:
            db.query(AchievementDB).filter(
                AchievementDB.experience_id.in_(identifiants)
            ).delete(synchronize_session=False)

        for modele in (
            EvidenceDB,
            SkillDB,
            ExperienceDB,
            EducationDB,
            CertificationDB,
            JobMatchDB,
            ApplicationDB,
            GeneratedCVDB,
            InterviewExchangeDB,
        ):
            db.query(modele).filter(
                modele.candidate_id == candidate_id
            ).delete(synchronize_session=False)

        db.delete(candidat)
        db.commit()

        return decompte

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
