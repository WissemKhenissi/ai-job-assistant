"""
Analyse d'une offre face au profil candidat, et sauvegarde du résultat.

C'est le point d'entrée du moteur : il orchestre la normalisation, la
recherche de preuves, l'inférence et le calcul des scores.
"""

from __future__ import annotations

from uuid import uuid4

from database.db import SessionLocal
from database.models import (
    AchievementDB,
    EvidenceDB,
    ExperienceDB,
    SkillDB,
)
from models.job import JobOfferDB
from models.matching import JobMatchDB

from services.matching.config import (
    DECLARED_SCORE,
    EXPERIENCE_INFERRED_WEIGHT,
    EXPERIENCE_PROVEN_WEIGHT,
    INFERRED_GOOD_SCORE,
    INFERRED_MODERATE_SCORE,
    INFERRED_PRUDENT_SCORE,
    INFERRED_STRONG_SCORE,
    INFERRED_VERY_STRONG_SCORE,
    PROVEN_SCORE,
    SEMANTIC_INFERENCE_EXCLUDED,
)
from services.matching.inference import (
    _find_inference_evidence,
    _find_semantic_inference_evidence,
)
from services.matching.normalization import (
    _canonical_skill_name,
    _normalize,
)
from services.matching.profile_text import (
    _format_evidence,
    _profile_text_blocks,
    _text_from_profile,
)
from services.matching.results import (
    MatchingResult,
    SkillMatch,
)


# ============================================================
# ANALYSE
# ============================================================

def analyze_candidate_against_skills(
    candidate_id: str,
    required_skills: list[str],
    job_text: str = "",
) -> MatchingResult:

    if not required_skills:

        raise ValueError(
            "La liste des compétences attendues "
            "ne peut pas être vide."
        )

    db = SessionLocal()

    try:

        # ====================================================
        # COMPETENCES
        # ====================================================

        skills = (
            db.query(SkillDB)
            .filter(
                SkillDB.candidate_id
                == candidate_id
            )
            .all()
        )

        # ====================================================
        # EXPERIENCES
        # ====================================================

        experiences = (
            db.query(ExperienceDB)
            .filter(
                ExperienceDB.candidate_id
                == candidate_id
            )
            .all()
        )

        experience_ids = [
            experience.id
            for experience in experiences
        ]

        # ====================================================
        # REALISATIONS
        # ====================================================

        achievements = (
            db.query(AchievementDB)
            .filter(
                AchievementDB.experience_id.in_(
                    experience_ids
                )
            )
            .all()
            if experience_ids
            else []
        )

        # ====================================================
        # PREUVES
        # ====================================================

        evidence = (
            db.query(EvidenceDB)
            .filter(
                EvidenceDB.candidate_id
                == candidate_id
            )
            .all()
        )

    finally:

        db.close()

    # ========================================================
    # INDEX COMPETENCES
    # ========================================================

    skills_by_name: dict[
        str,
        list[SkillDB],
    ] = {}

    for skill in skills:

        canonical_name = _canonical_skill_name(
            skill.name
        )

        skills_by_name.setdefault(
            canonical_name,
            [],
        ).append(skill)

    # ========================================================
    # INDEX PREUVES
    # ========================================================

    evidence_by_skill_id: dict[
        str,
        list[EvidenceDB],
    ] = {}

    for item in evidence:

        evidence_by_skill_id.setdefault(
            item.skill_id,
            [],
        ).append(item)

    # ========================================================
    # TEXTE GLOBAL
    # ========================================================

    profile_text = _text_from_profile(
        skills=skills,
        experiences=experiences,
        achievements=achievements,
        evidence=evidence,
    )

    # ========================================================
    # BLOCS SEMANTIQUES
    # ========================================================

    profile_text_blocks = _profile_text_blocks(
        skills=skills,
        experiences=experiences,
        achievements=achievements,
        evidence=evidence,
    )

    # ========================================================
    # MATCHING
    # ========================================================

    matches: list[SkillMatch] = []

    seen_skills: set[str] = set()

    for required_skill in required_skills:

        canonical_skill = _canonical_skill_name(
            required_skill
        )

        # ----------------------------------------------------
        # EVITE LES DOUBLONS
        # ----------------------------------------------------

        if canonical_skill in seen_skills:
            continue

        seen_skills.add(
            canonical_skill
        )

        # ====================================================
        # 1. COMPETENCE EXPLICITE
        # ====================================================

        direct_skills = skills_by_name.get(
            canonical_skill,
            [],
        )

        if direct_skills:

            evidence_texts: list[str] = []

            for direct_skill in direct_skills:

                linked_evidence = (
                    evidence_by_skill_id.get(
                        direct_skill.id,
                        [],
                    )
                )

                for item in linked_evidence:

                    formatted = _format_evidence(
                        item
                    )

                    if formatted:

                        evidence_texts.append(
                            formatted
                        )

            evidence_texts = list(
                dict.fromkeys(
                    evidence_texts
                )
            )

            # ------------------------------------------------
            # COMPETENCE + PREUVE
            # ------------------------------------------------

            if evidence_texts:

                matches.append(
                    SkillMatch(
                        skill=required_skill,
                        status="proven",
                        score=PROVEN_SCORE,
                        evidence=evidence_texts,
                        explanation=(
                            "Compétence explicitement "
                            "présente dans le Master CV "
                            "et soutenue par une ou plusieurs "
                            "preuves issues du parcours."
                        ),
                    )
                )

            # ------------------------------------------------
            # COMPETENCE DECLAREE SANS PREUVE
            # ------------------------------------------------

            else:

                declared_evidence = [
                    (
                        "Compétence déclarée : "
                        f"{skill.name}"
                    )
                    for skill in direct_skills
                ]

                matches.append(
                    SkillMatch(
                        skill=required_skill,
                        status="proven",
                        score=DECLARED_SCORE,
                        evidence=declared_evidence,
                        explanation=(
                            "Compétence explicitement "
                            "déclarée dans le Master CV, "
                            "mais encore insuffisamment "
                            "documentée par des preuves."
                        ),
                    )
                )

            continue

        # ====================================================
        # 2. COMPETENCES EXCLUES :
        #    PAS D'INFERENCE
        # ====================================================

        if canonical_skill in SEMANTIC_INFERENCE_EXCLUDED:

            matches.append(
                SkillMatch(
                    skill=required_skill,
                    status="missing",
                    score=0.0,
                    evidence=[],
                    explanation=(
                        "Compétence non déclarée "
                        "explicitement. Elle ne peut pas "
                        "être déduite automatiquement par "
                        "proximité sémantique."
                    ),
                )
            )

            continue

        # ====================================================
        # 3. INFERENCE LEXICALE
        # ====================================================

        inferred_evidence = (
            _find_inference_evidence(
                canonical_skill=canonical_skill,
                profile_text=profile_text,
            )
        )

        if inferred_evidence:

            matches.append(
                SkillMatch(
                    skill=required_skill,
                    status="inferred",
                    score=0.60,
                    evidence=inferred_evidence,
                    explanation=(
                        "Compétence non déclarée "
                        "explicitement, mais déduite "
                        "de plusieurs éléments du parcours."
                    ),
                )
            )

            continue

        # ====================================================
        # 4. INFERENCE SEMANTIQUE
        # ====================================================

        semantic_inference = (
            _find_semantic_inference_evidence(
                canonical_skill=canonical_skill,
                profile_texts=profile_text_blocks,
            )
        )

        if semantic_inference:

            (
                semantic_evidence,
                semantic_score,
            ) = semantic_inference

            # ------------------------------------------------
            # Score d'inférence proportionnel à la qualité
            # de la correspondance sémantique.
            # ------------------------------------------------

            if semantic_score >= 0.80:

                inference_score = INFERRED_VERY_STRONG_SCORE

            elif semantic_score >= 0.75:

                inference_score = INFERRED_STRONG_SCORE

            elif semantic_score >= 0.70:

                inference_score = INFERRED_GOOD_SCORE

            elif semantic_score >= 0.65:

                inference_score = INFERRED_MODERATE_SCORE

            else:

                inference_score = INFERRED_PRUDENT_SCORE

            matches.append(
                SkillMatch(
                    skill=required_skill,
                    status="inferred",
                    score=inference_score,
                    evidence=semantic_evidence,
                    explanation=(
                        "Compétence non déclarée "
                        "explicitement, mais déduite "
                        "par analyse sémantique "
                        "du parcours du candidat. "
                        "Elle ne doit pas être présentée "
                        "comme une maîtrise certaine."
                    ),
                )
            )

            continue

        # ====================================================
        # 5. MANQUANTE
        # ====================================================

        matches.append(
            SkillMatch(
                skill=required_skill,
                status="missing",
                score=0.0,
                evidence=[],
                explanation=(
                    "Aucune compétence déclarée, "
                    "preuve ou combinaison d'indices "
                    "suffisante dans le Master CV."
                ),
            )
        )

    # ========================================================
    # INFERENCE COMPOSITE — PRODUCT MANAGEMENT
    # ========================================================
    #
    # Product Management est une compétence transverse.
    # Elle ne doit pas être déduite par simple similarité
    # sémantique avec une phrase.
    #
    # On l'infère uniquement lorsque plusieurs compétences
    # constitutives du métier sont déjà présentes.
    #
    # Règle :
    #
    # - au moins 3 compétences produit distinctes
    # - au moins 1 compétence prouvée
    #
    # Les compétences techniques ne participent jamais
    # à cette inférence.
    # ========================================================

    PRODUCT_MANAGEMENT_COMPONENTS = {
        "product discovery",
        "product strategy",
        "roadmap produit",
        "priorisation",
        "backlog management",
        "product delivery",
        "experimentation",
        "stakeholder management",
        "agile scrum",
    }

    product_management_match = None

    for match in matches:

        if (
            _canonical_skill_name(match.skill)
            == "product management"
        ):
            product_management_match = match
            break

    if (
        product_management_match is not None
        and product_management_match.status == "missing"
    ):

        component_matches = []

        for match in matches:

            canonical_component = (
                _canonical_skill_name(
                    match.skill
                )
            )

            if (
                canonical_component
                in PRODUCT_MANAGEMENT_COMPONENTS
                and match.status
                in {"proven", "inferred"}
            ):

                component_matches.append(
                    match
                )

        # ----------------------------------------------------
        # Déduplication
        # ----------------------------------------------------

        unique_components = {}

        for match in component_matches:

            canonical_component = (
                _canonical_skill_name(
                    match.skill
                )
            )

            unique_components[
                canonical_component
            ] = match

        component_matches = list(
            unique_components.values()
        )

        # ----------------------------------------------------
        # Nombre de compétences réellement démontrées
        # ----------------------------------------------------

        proven_components = [
            match
            for match in component_matches
            if match.status == "proven"
        ]

        component_count = len(
            component_matches
        )

        # ----------------------------------------------------
        # Inférence
        # ----------------------------------------------------

        if (
            component_count >= 3
            and proven_components
        ):

            if component_count >= 5:

                inference_score = (
                    INFERRED_STRONG_SCORE
                )

                inference_level = "forte"

            elif component_count >= 4:

                inference_score = (
                    INFERRED_GOOD_SCORE
                )

                inference_level = "bonne"

            else:

                inference_score = (
                    INFERRED_MODERATE_SCORE
                )

                inference_level = "prudente"

            component_names = [
                match.skill
                for match in sorted(
                    component_matches,
                    key=lambda item: item.score,
                    reverse=True,
                )
            ]

            product_management_match.status = (
                "inferred"
            )

            product_management_match.score = (
                inference_score
            )

            product_management_match.evidence = [
                (
                    "Inférence composite Product "
                    "Management : "
                    f"{component_count} compétences "
                    "constitutives du Product Management "
                    "sont déjà démontrées ou déduites."
                ),
                (
                    "Composantes : "
                    + ", ".join(
                        component_names
                    )
                ),
            ]

            product_management_match.explanation = (
                "Product Management n'est pas "
                "explicitement déclaré, mais une "
                f"inférence {inference_level} est "
                "possible à partir d'un ensemble "
                "cohérent de compétences produit."
            )

    # ========================================================
    # SCORES
    # ========================================================

    if not matches:

        score_skills = 0.0
        score_experience = 0.0

    else:

        # ----------------------------------------------------
        # SCORE DES COMPETENCES
        # ----------------------------------------------------
        #
        # On prend en compte la qualité réelle de chaque match.
        #
        # Exemple :
        #
        # proven              = 1.00
        # inferred very strong= 0.85
        # inferred strong     = 0.80
        # inferred good       = 0.75
        # inferred moderate   = 0.70
        # inferred prudent    = 0.60
        # missing             = 0.00
        #
        # ----------------------------------------------------

        total_skill_score = sum(
            match.score
            for match in matches
        )

        score_skills = round(
            total_skill_score
            / len(matches)
            * 100,
            1,
        )

        # ----------------------------------------------------
        # SCORE D'EXPERIENCE
        # ----------------------------------------------------
        #
        # Ce score mesure la capacité du candidat à démontrer
        # les compétences demandées.
        #
        # Une compétence prouvée compte davantage qu'une
        # compétence simplement inférée.
        # ----------------------------------------------------

        proven_count = sum(
            match.status == "proven"
            for match in matches
        )

        inferred_count = sum(
            match.status == "inferred"
            for match in matches
        )

        score_experience = round(
            (
                proven_count * EXPERIENCE_PROVEN_WEIGHT
                + inferred_count * EXPERIENCE_INFERRED_WEIGHT
            )
            / len(matches),
            1,
        )

        # ========================================================
        # DOMAINES
        # ========================================================

        normalized_job_text = _normalize(
            job_text
        )

        profile_domains = set()

        if "e commerce" in profile_text:

            profile_domains.add(
                "e commerce"
            )

        if "adtech" in profile_text:

            profile_domains.add(
                "adtech"
            )

        if "digital" in profile_text:

            profile_domains.add(
                "digital"
            )

        job_domains = set()

        if "e commerce" in normalized_job_text:

            job_domains.add(
                "e commerce"
            )

        if "adtech" in normalized_job_text:

            job_domains.add(
                "adtech"
            )

        if "digital" in normalized_job_text:

            job_domains.add(
                "digital"
            )

        if not job_domains:

            score_domain = score_skills

        else:

            score_domain = round(
                len(
                    profile_domains
                    & job_domains
                )
                / len(job_domains)
                * 100,
                1,
            )

    # ========================================================
    # SCORE GLOBAL
    # ========================================================

    if job_text.strip():

        score_global = round(
            score_skills * 0.70
            + score_experience * 0.20
            + score_domain * 0.10,
            1,
        )

    else:

        score_global = score_skills

    # ========================================================
    # FORCES
    # ========================================================

    strengths = []

    for match in matches:

        if match.status == "proven":

            strengths.append(
                f"{match.skill} : "
                "compétence prouvée"
            )

        elif (
            match.status == "inferred"
            and match.score >= INFERRED_STRONG_SCORE
        ):

            strengths.append(
                f"{match.skill} : "
                "compétence fortement déductible"
            )


    # ========================================================
    # FAIBLESSES
    # ========================================================

    weaknesses = []

    for match in matches:

        if match.status == "missing":

            weaknesses.append(
                f"{match.skill} : "
                "compétence manquante"
            )

        elif (
            match.status == "inferred"
            and match.score < INFERRED_STRONG_SCORE
        ):

            weaknesses.append(
                f"{match.skill} : "
                "compétence seulement déductible"
            )
    # ========================================================
    # RESULTAT
    # ========================================================

    return MatchingResult(
        score_global=score_global,
        score_skills=score_skills,
        score_experience=score_experience,
        score_domain=score_domain,
        matches=matches,
        strengths=strengths,
        weaknesses=weaknesses,
    )



# ============================================================
# ANALYSE + SAUVEGARDE
# ============================================================

def analyze_and_save_job_match(
    candidate_id: str,
    job_offer_id: str,
    required_skills: list[str],
) -> MatchingResult:

    db = SessionLocal()

    try:

        job_offer = db.get(
            JobOfferDB,
            job_offer_id,
        )

        if not job_offer:

            raise ValueError(
                f"Annonce introuvable : "
                f"{job_offer_id}"
            )

        job_text = "\n".join(
            [
                job_offer.title or "",
                job_offer.description or "",
            ]
        )

    finally:

        db.close()

    # ========================================================
    # ANALYSE
    # ========================================================

    result = analyze_candidate_against_skills(
        candidate_id=candidate_id,
        required_skills=required_skills,
        job_text=job_text,
    )

    # ========================================================
    # SAUVEGARDE
    # ========================================================

    db = SessionLocal()

    try:

        match = (
            db.query(JobMatchDB)
            .filter(
                JobMatchDB.candidate_id
                == candidate_id,
                JobMatchDB.job_offer_id
                == job_offer_id,
            )
            .one_or_none()
        )

        # ----------------------------------------------------
        # CREATION
        # ----------------------------------------------------

        if match is None:

            match = JobMatchDB(
                id=f"match-{uuid4()}",
                candidate_id=candidate_id,
                job_offer_id=job_offer_id,
            )

            db.add(match)

        # ----------------------------------------------------
        # SCORES
        # ----------------------------------------------------

        match.score_global = (
            result.score_global
        )

        match.score_skills = (
            result.score_skills
        )

        match.score_experience = (
            result.score_experience
        )

        match.score_domain = (
            result.score_domain
        )

        # ----------------------------------------------------
        # COMPETENCES
        # ----------------------------------------------------

        match.matched_skills = (
            result.matched_skills
        )

        match.inferred_skills = (
            result.inferred_skills
        )

        match.missing_skills = (
            result.missing_skills
        )

        # ----------------------------------------------------
        # FORCES / FAIBLESSES
        # ----------------------------------------------------

        match.strengths = (
            result.strengths
        )

        match.weaknesses = (
            result.weaknesses
        )

        # ----------------------------------------------------
        # COMMIT
        # ----------------------------------------------------

        db.commit()

    except Exception:

        db.rollback()

        raise

    finally:

        db.close()

    return result