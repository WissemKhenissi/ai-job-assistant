"""
Écriture d'un profil lu depuis un CV, après validation par l'utilisateur.

Séparé de l'extraction à dessein : `services.ai.profile_extraction`
propose et ne touche à rien, ce module écrit et ne décide de rien. Ce
qui arrive ici a été relu et coché.

Deux principes :

- **On ajoute, on n'écrase pas.** Un champ d'identité déjà renseigné
  est conservé ; une compétence déjà déclarée n'est pas dupliquée.
  Un import ne doit jamais faire perdre ce qui a été saisi à la main.
- **Une puce devient une preuve.** C'est ce qui fait la valeur de
  l'import : sans preuve rattachée, les compétences importées
  resteraient « déclarées » et ne pourraient jamais figurer sur un CV.
"""

from __future__ import annotations

from dataclasses import dataclass

from database.db import SessionLocal
from database.models import CandidateDB, ExperienceDB, SkillDB

from services.profile_service import (
    add_certification,
    add_education,
    add_evidence,
    add_experience,
    add_skill,
    update_candidate,
)


# Champs d'identité que l'import peut renseigner s'ils sont vides.
CHAMPS_IDENTITE = (
    "first_name",
    "last_name",
    "email",
    "phone",
    "location",
    "linkedin_url",
    "headline",
    "summary",
    "languages",
)


@dataclass(frozen=True)
class ImportSummary:
    """Ce que l'import a réellement écrit."""

    candidate_id: str = ""
    fields_filled: tuple[str, ...] = ()
    experiences: int = 0
    lines: int = 0
    skills: int = 0
    educations: int = 0
    certifications: int = 0
    skipped: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return (
            self.experiences
            + self.lines
            + self.skills
            + self.educations
            + self.certifications
        )


def _identite_a_completer(
    candidate_id: str,
    profile,
    overwrite: bool,
) -> dict:
    """Champs vides que l'import peut renseigner."""

    db = SessionLocal()

    try:
        candidat = db.get(CandidateDB, candidate_id)

        if candidat is None:
            raise ValueError(f"Candidat introuvable : {candidate_id}")

        a_ecrire: dict[str, str] = {}

        for champ in CHAMPS_IDENTITE:

            valeur = (getattr(profile, champ, "") or "").strip()

            if not valeur:
                continue

            actuelle = (getattr(candidat, champ, "") or "").strip()

            if actuelle and not overwrite:
                continue

            if actuelle == valeur:
                continue

            a_ecrire[champ] = valeur

        return a_ecrire

    finally:
        db.close()


def _experience_existante(
    candidate_id: str,
    company: str,
    job_title: str,
) -> bool:
    """
    Une expérience de même entreprise et même poste est-elle déjà là ?

    Réimporter le même CV ne doit pas doubler le parcours.
    """

    db = SessionLocal()

    try:
        return (
            db.query(ExperienceDB)
            .filter(
                ExperienceDB.candidate_id == candidate_id,
                ExperienceDB.company == company,
                ExperienceDB.job_title == job_title,
            )
            .first()
            is not None
        )

    finally:
        db.close()


def _identifiants_des_competences(candidate_id: str) -> dict[str, str]:
    """Nom normalisé -> identifiant, pour rattacher les preuves."""

    db = SessionLocal()

    try:
        return {
            " ".join(skill.name.casefold().split()): skill.id
            for skill in (
                db.query(SkillDB)
                .filter(SkillDB.candidate_id == candidate_id)
                .all()
            )
        }

    finally:
        db.close()


def import_profile(
    candidate_id: str,
    profile,
    overwrite_identity: bool = False,
) -> ImportSummary:
    """
    Écrit le profil validé et retourne ce qui a réellement été créé.

    `profile` est un ExtractedProfile éventuellement réduit par
    l'utilisateur : tout ce qu'il contient est écrit, rien de plus.
    """

    ignores: list[str] = []

    # ----------------------------------------------------------
    # IDENTITE
    # ----------------------------------------------------------

    champs = _identite_a_completer(
        candidate_id, profile, overwrite_identity
    )

    if champs:
        update_candidate(candidate_id, **champs)

    # ----------------------------------------------------------
    # COMPETENCES
    # ----------------------------------------------------------
    #
    # Créées avant les expériences : les preuves ont besoin de leur
    # identifiant. add_skill est idempotent sur le nom.

    deja = _identifiants_des_competences(candidate_id)

    creees = 0

    for nom in profile.skills:

        cle = " ".join(nom.casefold().split())

        if cle in deja:
            continue

        deja[cle] = add_skill(
            candidate_id=candidate_id,
            name=nom,
            category="Importée du CV",
        )

        creees += 1

    # ----------------------------------------------------------
    # EXPERIENCES ET PREUVES
    # ----------------------------------------------------------

    nb_experiences = 0
    nb_lignes = 0

    for experience in profile.experiences:

        if experience.start_date is None:
            ignores.append(
                f"{experience.label} : sans date de début, "
                "non importée."
            )
            continue

        if _experience_existante(
            candidate_id, experience.company, experience.job_title
        ):
            ignores.append(
                f"{experience.label} : déjà présente au Master CV."
            )
            continue

        experience_id = add_experience(
            candidate_id=candidate_id,
            company=experience.company,
            job_title=experience.job_title,
            start_date=experience.start_date,
            end_date=experience.end_date,
            location=experience.location,
            business_context=experience.business_context,
        )

        nb_experiences += 1

        for ligne in experience.lines:

            cle = " ".join(ligne.skill.casefold().split())

            skill_id = deja.get(cle)

            if skill_id is None:

                # Une puce sans compétence rattachée ne peut pas
                # devenir une preuve : elle resterait invisible du
                # moteur. On la rattache à une compétence portant le
                # nom du poste, faute de mieux, plutôt que de la
                # perdre.
                if not ligne.skill:
                    ignores.append(
                        f"{experience.label} : « "
                        f"{ligne.text[:50]}… » sans compétence "
                        "associée, non importée."
                    )
                    continue

                skill_id = add_skill(
                    candidate_id=candidate_id,
                    name=ligne.skill,
                    category="Importée du CV",
                )

                deja[cle] = skill_id
                creees += 1

            add_evidence(
                candidate_id=candidate_id,
                skill_id=skill_id,
                description=ligne.text,
                experience_id=experience_id,
                evidence_type="Expérience professionnelle",
            )

            nb_lignes += 1

    # ----------------------------------------------------------
    # FORMATION ET CERTIFICATIONS
    # ----------------------------------------------------------

    nb_formations = 0

    for formation in profile.educations:

        add_education(
            candidate_id=candidate_id,
            institution=formation.institution,
            degree=formation.degree,
            field_of_study=formation.field_of_study,
            start_year=formation.start_year,
            end_year=formation.end_year,
        )

        nb_formations += 1

    nb_certifications = 0

    for certification in profile.certifications:

        add_certification(
            candidate_id=candidate_id,
            name=certification.name,
            organization=certification.organization,
            obtained_year=certification.obtained_year,
        )

        nb_certifications += 1

    return ImportSummary(
        candidate_id=candidate_id,
        fields_filled=tuple(sorted(champs)),
        experiences=nb_experiences,
        lines=nb_lignes,
        skills=creees,
        educations=nb_formations,
        certifications=nb_certifications,
        skipped=tuple(ignores),
    )
