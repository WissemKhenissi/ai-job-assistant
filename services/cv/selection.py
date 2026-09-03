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

from services.cv.achievements import (
    build_achievement_line,
    is_redundant,
)
from services.cv.results import (
    CVAchievement,
    CVAchievementLine,
    CVCertification,
    CVEducation,
    CVEvidenceLine,
    CVExperience,
    CVSkillGroup,
    TargetedCV,
)
from services.job_title import clean_job_title
from services.matching.normalization import (
    _canonical_skill_name,
    _contains_term,
)
from services.skill_catalog_service import find_skill_by_name
from services.text_numbers import numbers_in


# Un CV ne peut pas porter les 67 preuves du Master CV : on retient
# les plus pertinentes, compétence par compétence.
DEFAULT_MAX_LINES_PER_SKILL = 4

DEFAULT_MAX_TOTAL_LINES = 16

# Une expérience réduite à une puce ne se défend pas en entretien, et
# une expérience qui en porte dix noie le lecteur. Le cahier des
# charges fixe 2 à 5 puces (§16) ; l'élagage d'une page (services.
# cv.fitting) redescend ensuite si le document déborde.
DEFAULT_MAX_LINES_PER_EXPERIENCE = 5

# Les réalisations sont le contenu le plus fort du CV, mais une
# expérience qui n'affiche que des réussites ne dit plus ce qu'elle
# consistait à faire au quotidien.
DEFAULT_MAX_ACHIEVEMENTS_PER_EXPERIENCE = 2


# ============================================================
# NIVEAUX DE COMPETENCE AFFICHABLES
# ============================================================
#
# Le CV n'a longtemps montré que le prouvé. C'est le réglage le plus
# sûr, mais il rend invisibles des compétences que le candidat a
# lui-même déclarées, faute d'avoir documenté une preuve — et sur un
# profil produit, ce sont justement les compétences cœur du métier.
#
# Le seuil devient donc un choix, assumé et tracé :
#
#   PROVEN_ONLY    le système garantit chaque compétence affichée.
#   WITH_DECLARED  le candidat atteste de ses propres déclarations.
#   WITH_INFERRED  le candidat assume en plus les déductions du
#                  moteur, qu'il n'avait pas formulées lui-même.
#
# « missing » n'y figure pas et n'y figurera pas : une compétence
# absente du Master CV serait une affirmation que le candidat n'a
# jamais faite, écrite à sa place.

PROVEN_ONLY = ("proven",)

WITH_DECLARED = ("proven", "declared")

WITH_INFERRED = ("proven", "declared", "inferred")

DISPLAYABLE_STATUSES = frozenset(WITH_INFERRED)


class MissingAnalysisError(RuntimeError):
    """L'offre n'a pas encore été analysée pour ce candidat."""


def build_targeted_cv(
    candidate_id: str,
    job_offer_id: str,
    max_lines_per_skill: int = DEFAULT_MAX_LINES_PER_SKILL,
    max_total_lines: int = DEFAULT_MAX_TOTAL_LINES,
    max_lines_per_experience: int = DEFAULT_MAX_LINES_PER_EXPERIENCE,
    max_achievements_per_experience: int = (
        DEFAULT_MAX_ACHIEVEMENTS_PER_EXPERIENCE
    ),
    skill_levels: tuple[str, ...] = PROVEN_ONLY,
) -> TargetedCV:
    """
    Construit le CV ciblé d'un candidat pour une offre analysée.

    S'appuie sur le détail persisté par le moteur de matching
    (job_skill_matches) plutôt que de relancer une analyse : le CV
    reflète exactement l'analyse que l'utilisateur a sous les yeux.

    Toutes les expériences du Master CV figurent au CV, y compris
    celles que l'offre ne fait pas ressortir : un trou dans la
    chronologie se remarque et appelle une question gênante en
    entretien (§18). Une expérience sans ligne retenue apparaît alors
    réduite à son poste, son entreprise et ses dates.

    `skill_levels` fixe le seuil de la rubrique compétences. Les
    **lignes** d'expérience, elles, restent toujours issues d'une
    preuve : une compétence déclarée sans preuve peut être annoncée,
    elle ne peut pas être racontée.
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
        # EXPERIENCES DU MASTER CV
        # ====================================================

        experience_rows = (
            db.query(ExperienceDB)
            .filter(ExperienceDB.candidate_id == candidate_id)
            .all()
        )

        experience_rows.sort(
            key=lambda item: item.start_date,
            reverse=True,
        )

        # ====================================================
        # REALISATIONS
        # ====================================================
        #
        # Servies avant les preuves : une réussite prime sur une
        # description de tâche (§8, §17). C'est aussi le seul endroit
        # du Master CV où vivent des chiffres — aucune preuve n'en
        # porte.

        achievements: list[CVAchievement] = []

        achievement_lines_par_experience: dict[
            str, list[CVAchievementLine]
        ] = {}

        achievement_rows = (
            db.query(AchievementDB)
            .filter(
                AchievementDB.experience_id.in_(
                    [item.id for item in experience_rows]
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

        # Une réalisation chiffrée passe devant une réalisation
        # qualitative : c'est elle qui fait la différence à la
        # lecture.
        def _porte_un_chiffre(row) -> bool:

            titre, detail = build_achievement_line(
                row.title,
                row.result or "",
                row.metrics or "",
            )

            return bool(numbers_in(f"{titre} {detail}"))

        for experience in experience_rows:

            candidates = [
                row
                for row in achievement_rows
                if row.experience_id == experience.id
            ]

            candidates.sort(
                key=lambda row: (not _porte_un_chiffre(row), row.id)
            )

            retenues: list[CVAchievementLine] = []

            for row in candidates[:max_achievements_per_experience]:

                titre, detail = build_achievement_line(
                    row.title,
                    row.result or "",
                    row.metrics or "",
                )

                if not titre:
                    continue

                retenues.append(
                    CVAchievementLine(
                        title=titre,
                        detail=detail,
                        achievement_id=row.id,
                    )
                )

            if retenues:
                achievement_lines_par_experience[experience.id] = (
                    retenues
                )

        # ====================================================
        # SELECTION DES LIGNES DE PREUVE
        # ====================================================
        #
        # Deux passes. La première ne retient que les preuves des
        # compétences que l'annonce demande et que le Master CV
        # prouve : c'est le contenu le plus pertinent, il passe en
        # premier et rien ne peut le déloger.
        #
        # La seconde étoffe chaque expérience avec ses autres preuves.
        # Elles viennent du même Master CV et sont donc aussi vraies,
        # simplement moins directement liées à cette annonce — et un
        # CV de trois puces ne se défend pas, même exact.

        lines_par_experience: dict[str, list[CVEvidenceLine]] = {}

        # Un même énoncé du Master CV est rattaché à toutes les
        # compétences qu'il démontre : il existe donc en plusieurs
        # exemplaires. La déduplication porte sur le TEXTE, pas sur
        # l'identifiant — un CV ne doit jamais répéter une puce.
        textes_deja_pris: set[str] = set()

        preuves_deja_prises: set[str] = set()

        total_lines = 0

        def _retenir(evidence, libelle_competence: str) -> bool:
            """Ajoute une preuve au CV si elle y apporte une ligne neuve."""

            nonlocal total_lines

            texte = (evidence.description or "").strip()

            if not texte or evidence.experience_id is None:
                # Une preuve non rattachée à une expérience ne peut
                # pas être placée dans le CV.
                return False

            cle_texte = " ".join(texte.casefold().split())

            if cle_texte in textes_deja_pris:
                return False

            lignes = lines_par_experience.setdefault(
                evidence.experience_id,
                [],
            )

            # Les réalisations occupent déjà des puces : elles
            # comptent dans le budget de l'expérience.
            deja_placees = len(lignes) + len(
                achievement_lines_par_experience.get(
                    evidence.experience_id,
                    [],
                )
            )

            if deja_placees >= max_lines_per_experience:
                return False

            textes_deja_pris.add(cle_texte)
            preuves_deja_prises.add(evidence.id)

            lignes.append(
                CVEvidenceLine(
                    text=texte,
                    skill=libelle_competence,
                    evidence_id=evidence.id,
                )
            )

            total_lines += 1

            return True

        # ----------------------------------------------------
        # PASSE 1 : CE QUE L'ANNONCE DEMANDE ET QUE L'ON PROUVE
        # ----------------------------------------------------

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

                if _retenir(evidence, row.skill):
                    retenues += 1

        # ----------------------------------------------------
        # PASSE 2 : ETOFFEMENT
        # ----------------------------------------------------

        texte_offre = " ".join(
            partie
            for partie in (job_offer.title, job_offer.description)
            if partie
        )

        noms_par_skill_id = {
            skill.id: skill.name for skill in candidate_skills
        }

        # Une preuve que l'analyse n'a pas retenue n'a qu'un signal de
        # pertinence disponible : sa compétence est-elle nommée dans
        # l'annonce ? C'est peu, mais c'est vérifiable.
        nommee_par_l_annonce = {
            skill.id: _contains_term(texte_offre, skill.name)
            for skill in candidate_skills
        }

        preuves_par_experience: dict[str, list] = {}

        for evidence in (
            db.query(EvidenceDB)
            .filter(EvidenceDB.candidate_id == candidate_id)
            .order_by(EvidenceDB.id)
            .all()
        ):

            if evidence.experience_id is None:
                continue

            preuves_par_experience.setdefault(
                evidence.experience_id,
                [],
            ).append(evidence)

        for liste in preuves_par_experience.values():

            liste.sort(
                key=lambda item: not nommee_par_l_annonce.get(
                    item.skill_id,
                    False,
                )
            )

        # Les expériences que l'annonce a fait ressortir sont servies
        # les premières ; à égalité, la plus récente passe devant. On
        # remplit par tours, une ligne à la fois, pour ne pas épuiser
        # le budget sur la première expérience venue.
        ordre_etoffement = sorted(
            experience_rows,
            key=lambda item: (
                -len(lines_par_experience.get(item.id, [])),
                -item.start_date.toordinal(),
            ),
        )

        for cible in range(1, max_lines_per_experience + 1):

            if total_lines >= max_total_lines:
                break

            for experience in ordre_etoffement:

                if total_lines >= max_total_lines:
                    break

                deja_placees = len(
                    lines_par_experience.get(experience.id, [])
                ) + len(
                    achievement_lines_par_experience.get(
                        experience.id, []
                    )
                )

                if deja_placees >= cible:
                    continue

                for evidence in preuves_par_experience.get(
                    experience.id,
                    [],
                ):

                    if evidence.id in preuves_deja_prises:
                        continue

                    if _retenir(
                        evidence,
                        noms_par_skill_id.get(evidence.skill_id, ""),
                    ):
                        break

        # ----------------------------------------------------
        # DOUBLONS ENTRE REALISATION ET PREUVE
        # ----------------------------------------------------
        #
        # Une réalisation qualitative répète parfois une puce déjà
        # retenue, en moins précis. Le contrôle vient après les deux
        # sélections, faute de quoi il ignorerait la moitié du CV.

        for identifiant, realisations in list(
            achievement_lines_par_experience.items()
        ):

            textes = [
                ligne.text
                for ligne in lines_par_experience.get(identifiant, [])
            ]

            conservees = [
                realisation
                for realisation in realisations
                if not is_redundant(
                    realisation.title,
                    realisation.detail,
                    textes,
                )
            ]

            if conservees:
                achievement_lines_par_experience[identifiant] = (
                    conservees
                )
            else:
                del achievement_lines_par_experience[identifiant]

        # ====================================================
        # EXPERIENCES RETENUES
        # ====================================================
        #
        # Toutes, y compris celles restées sans ligne : un trou dans
        # la chronologie appelle une question gênante en entretien.

        experiences: list[CVExperience] = [
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
                achievement_lines=(
                    achievement_lines_par_experience.get(
                        experience.id, []
                    )
                ),
                lines=lines_par_experience.get(experience.id, []),
            )
            for experience in experience_rows
        ]

        # ====================================================
        # COMPETENCES REGROUPEES PAR CATEGORIE
        # ====================================================
        #
        # Reprend la catégorie du référentiel skill_catalog (Product,
        # Data, Business...) pour présenter les compétences groupées,
        # comme sur un CV classique. L'ordre suit celui de l'annonce :
        # ce qu'elle demande en premier apparaît en premier.

        niveaux_affichables = tuple(
            niveau
            for niveau in skill_levels
            if niveau in DISPLAYABLE_STATUSES
        ) or PROVEN_ONLY

        affichables = [
            row for row in skill_matches
            if row.status in niveaux_affichables
        ]

        skill_groups: list[CVSkillGroup] = []

        if affichables:

            par_categorie: dict[str, list[str]] = {}

            for row in affichables:

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
            cv_title=clean_job_title(job_offer.title or ""),
            skills=[row.skill for row in affichables],
            skill_levels=niveaux_affichables,
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
