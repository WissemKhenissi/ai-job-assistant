"""
Sélection déterministe du contenu d'un CV ciblé.

Le générateur n'invente rien : il choisit, parmi les données du Master
CV, celles que l'analyse d'une offre a désignées comme pertinentes.
Deux appels sur la même offre et le même profil produisent exactement
le même CV.

Règle non négociable appliquée ici : seules les compétences au statut
"proven" — déclarées dans le Master CV ET soutenues par au moins une
preuve EvidenceDB — peuvent figurer comme ligne de compétence.
"""

from __future__ import annotations

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
from models.job import JobOfferDB
from models.matching import JobMatchDB
from models.skill_match import JobSkillMatchDB

from services.cv.results import (
    CVAchievement,
    CVCertification,
    CVEducation,
    CVEvidenceLine,
    CVExperience,
    CVSkillGroup,
    TargetedCV,
)
from services.matching.normalization import _canonical_skill_name
from services.skill_catalog_service import find_skill_by_name


# Un CV ne peut pas porter les 58 preuves du Master CV : on retient
# les plus pertinentes, compétence par compétence.
DEFAULT_MAX_LINES_PER_SKILL = 4

DEFAULT_MAX_TOTAL_LINES = 12


class MissingAnalysisError(RuntimeError):
    """L'offre n'a pas encore été analysée pour ce candidat."""


def build_targeted_cv(
    candidate_id: str,
    job_offer_id: str,
    max_lines_per_skill: int = DEFAULT_MAX_LINES_PER_SKILL,
    max_total_lines: int = DEFAULT_MAX_TOTAL_LINES,
) -> TargetedCV:
    """
    Construit le CV ciblé d'un candidat pour une offre analysée.

    S'appuie sur le détail persisté par le moteur de matching
    (job_skill_matches) plutôt que de relancer une analyse : le CV
    reflète exactement l'analyse que l'utilisateur a sous les yeux.
    """

    db = SessionLocal()

    try:

        # ====================================================
        # CONTEXTE
        # ====================================================

        candidate = db.get(CandidateDB, candidate_id)

        if candidate is None:
            raise ValueError(
                f"Candidat introuvable : {candidate_id}"
            )

        job_offer = db.get(JobOfferDB, job_offer_id)

        if job_offer is None:
            raise ValueError(
                f"Annonce introuvable : {job_offer_id}"
            )

        job_match = (
            db.query(JobMatchDB)
            .filter(
                JobMatchDB.candidate_id == candidate_id,
                JobMatchDB.job_offer_id == job_offer_id,
            )
            .one_or_none()
        )

        if job_match is None:
            raise MissingAnalysisError(
                "L'offre doit être analysée avant de générer un "
                f"CV ciblé : {job_offer_id}"
            )

        skill_matches = (
            db.query(JobSkillMatchDB)
            .filter(
                JobSkillMatchDB.job_match_id == job_match.id
            )
            .all()
        )

        if not skill_matches:
            raise MissingAnalysisError(
                "L'analyse de cette offre ne contient aucun détail "
                "par compétence : relancer l'analyse."
            )

        # ====================================================
        # REPARTITION PAR STATUT
        # ====================================================
        #
        # L'ordre suit celui de l'analyse, pour que le CV reflète
        # l'ordre dans lequel l'annonce exprime ses attentes.

        proven = [
            row for row in skill_matches
            if row.status == "proven"
        ]

        declared = [
            row.skill for row in skill_matches
            if row.status == "declared"
        ]

        inferred = [
            row.skill for row in skill_matches
            if row.status == "inferred"
        ]

        missing = [
            row.skill for row in skill_matches
            if row.status == "missing"
        ]

        # ====================================================
        # COMPETENCES DU CANDIDAT, PAR FORME CANONIQUE
        # ====================================================

        candidate_skills = (
            db.query(SkillDB)
            .filter(SkillDB.candidate_id == candidate_id)
            .all()
        )

        skills_par_canon: dict[str, list[SkillDB]] = {}

        for skill in candidate_skills:

            canon = _canonical_skill_name(skill.name)

            skills_par_canon.setdefault(canon, []).append(skill)

        # ====================================================
        # SELECTION DES LIGNES DE PREUVE
        # ====================================================

        lines_par_experience: dict[str, list[CVEvidenceLine]] = {}

        # Un même énoncé du Master CV est rattaché à toutes les
        # compétences qu'il démontre : il existe donc en plusieurs
        # exemplaires. La déduplication porte sur le TEXTE, pas sur
        # l'identifiant — un CV ne doit jamais répéter une puce.
        textes_deja_pris: set[str] = set()

        total_lines = 0

        for row in proven:

            if total_lines >= max_total_lines:
                break

            matching_skills = skills_par_canon.get(
                row.canonical_skill,
                [],
            )

            if not matching_skills:
                continue

            evidence_rows = (
                db.query(EvidenceDB)
                .filter(
                    EvidenceDB.candidate_id == candidate_id,
                    EvidenceDB.skill_id.in_(
                        [skill.id for skill in matching_skills]
                    ),
                )
                .order_by(EvidenceDB.id)
                .all()
            )

            retenues = 0

            for evidence in evidence_rows:

                if retenues >= max_lines_per_skill:
                    break

                if total_lines >= max_total_lines:
                    break

                texte = (evidence.description or "").strip()

                if not texte:
                    continue

                cle_texte = " ".join(texte.casefold().split())

                if cle_texte in textes_deja_pris:
                    continue

                if evidence.experience_id is None:
                    # Une preuve non rattachée à une expérience ne
                    # peut pas être placée dans le CV.
                    continue

                textes_deja_pris.add(cle_texte)

                lines_par_experience.setdefault(
                    evidence.experience_id,
                    [],
                ).append(
                    CVEvidenceLine(
                        text=texte,
                        skill=row.skill,
                        evidence_id=evidence.id,
                    )
                )

                retenues += 1
                total_lines += 1

        # ====================================================
        # EXPERIENCES RETENUES
        # ====================================================
        #
        # Seules les expériences qui portent au moins une ligne
        # sélectionnée figurent au CV.

        experiences: list[CVExperience] = []

        if lines_par_experience:

            experience_rows = (
                db.query(ExperienceDB)
                .filter(
                    ExperienceDB.id.in_(
                        list(lines_par_experience.keys())
                    )
                )
                .all()
            )

            experience_rows.sort(
                key=lambda item: item.start_date,
                reverse=True,
            )

            for experience in experience_rows:

                experiences.append(
                    CVExperience(
                        experience_id=experience.id,
                        job_title=experience.job_title,
                        company=experience.company,
                        location=experience.location or "",
                        start_date=experience.start_date,
                        end_date=experience.end_date,
                        business_context=(
                            experience.business_context or ""
                        ),
                        lines=lines_par_experience[experience.id],
                    )
                )

        # ====================================================
        # REALISATIONS DES EXPERIENCES RETENUES
        # ====================================================

        achievements: list[CVAchievement] = []

        if experiences:

            achievement_rows = (
                db.query(AchievementDB)
                .filter(
                    AchievementDB.experience_id.in_(
                        [item.experience_id for item in experiences]
                    )
                )
                .order_by(AchievementDB.id)
                .all()
            )

            for achievement in achievement_rows:

                achievements.append(
                    CVAchievement(
                        achievement_id=achievement.id,
                        experience_id=achievement.experience_id,
                        title=achievement.title,
                        situation=achievement.situation or "",
                        action=achievement.action or "",
                        result=achievement.result or "",
                        metrics=achievement.metrics or "",
                    )
                )

        # ====================================================
        # COMPETENCES REGROUPEES PAR CATEGORIE
        # ====================================================
        #
        # Reprend la catégorie du référentiel skill_catalog (Product,
        # Data, Business...) pour présenter les compétences prouvées
        # groupées, comme sur un CV classique.

        skill_groups: list[CVSkillGroup] = []

        if proven:

            par_categorie: dict[str, list[str]] = {}

            for row in proven:

                catalog_skill = find_skill_by_name(row.skill)

                categorie = (
                    catalog_skill.category
                    if catalog_skill is not None
                    and catalog_skill.category
                    else "Autres compétences"
                )

                par_categorie.setdefault(categorie, []).append(
                    row.skill
                )

            skill_groups = [
                CVSkillGroup(
                    category=categorie,
                    skills=tuple(skills),
                )
                for categorie, skills in par_categorie.items()
            ]

        # ====================================================
        # FORMATION ET CERTIFICATIONS
        # ====================================================
        #
        # Non filtrées par offre : vraies quelle que soit l'annonce.

        educations = [
            CVEducation(
                institution=row.institution,
                degree=row.degree,
                field_of_study=row.field_of_study or "",
                start_year=row.start_year,
                end_year=row.end_year,
            )
            for row in (
                db.query(EducationDB)
                .filter(EducationDB.candidate_id == candidate_id)
                .order_by(EducationDB.end_year.desc())
                .all()
            )
        ]

        certifications = [
            CVCertification(
                name=row.name,
                organization=row.organization or "",
                obtained_year=row.obtained_year,
            )
            for row in (
                db.query(CertificationDB)
                .filter(CertificationDB.candidate_id == candidate_id)
                .order_by(CertificationDB.obtained_year.desc())
                .all()
            )
        ]

        # ====================================================
        # RESULTAT
        # ====================================================

        return TargetedCV(
            candidate_id=candidate.id,
            full_name=(
                f"{candidate.first_name} "
                f"{candidate.last_name}"
            ).strip(),
            email=candidate.email or "",
            phone=candidate.phone or "",
            location=candidate.location or "",
            linkedin_url=candidate.linkedin_url or "",
            summary=candidate.summary or "",
            headline=candidate.headline or "",
            availability=candidate.availability or "",
            languages=candidate.languages or "",
            interests=candidate.interests or "",
            job_offer_id=job_offer.id,
            job_offer_title=job_offer.title or "",
            job_offer_company=(job_offer.company or "").strip(),
            skills=[row.skill for row in proven],
            skill_groups=skill_groups,
            experiences=experiences,
            achievements=achievements,
            educations=educations,
            certifications=certifications,
            declared_skills=declared,
            inferred_skills=inferred,
            missing_skills=missing,
        )

    finally:

        db.close()
