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
from models.skill_match import JobSkillMatchDB

from services.requirement_importance import (
    IMPORTANCE_PAR_DEFAUT,
    LIBELLES as LIBELLES_IMPORTANCE,
    classify_requirements,
    normalise_terme,
)

from services.skill_catalog_service import find_skill_by_name

from services.matching.config import (
    DECLARED_SCORE,
    EXPERIENCE_INFERRED_WEIGHT,
    EXPERIENCE_PROVEN_WEIGHT,
    INFERRED_GOOD_SCORE,
    INFERRED_MODERATE_SCORE,
    INFERRED_PRUDENT_SCORE,
    INFERRED_STRONG_SCORE,
    INFERRED_VERY_STRONG_SCORE,
    MIN_COMPOSITE_COMPONENTS,
    POIDS_IMPORTANCE,
    PROVEN_SCORE,
    SKILL_WEIGHT_DECAY,
)
from services.matching.inference import (
    _est_deductible,
    _find_inference_evidence,
    _find_semantic_inference_evidence,
)
from services.matching.normalization import (
    _canonical_skill_name,
)
from services.matching.profile_text import (
    _format_evidence,
    _profile_text_blocks,
    _text_from_profile,
)
from services.matching.results import (
    PRESENT_STATUSES,
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
    importance_hints: dict[str, str] | None = None,
) -> MatchingResult:
    """
    Confronte le profil du candidat aux exigences d'une annonce.

    ``importance_hints`` porte ce que l'IA a compris du statut de
    chaque exigence en lisant l'annonce (condition, souhait, simple
    mention). C'est facultatif : sans lui, le niveau est déduit du
    texte de l'annonce par marqueurs, et sans texte d'annonce toutes
    les exigences comptent pareil — le comportement d'origine.
    """

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
                        status="declared",
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
        # 2. COMPETENCES QUE LE REFERENTIEL DIT
        #    NON DEDUCTIBLES
        # ====================================================
        #
        # Un outil, une technologie, un corpus de connaissances : on
        # les a appris ou non, aucun récit d'expérience ne permet de
        # les supposer. Le référentiel porte cette distinction
        # (skill_catalog.is_inferable), le moteur s'y range.

        if not _est_deductible(canonical_skill):

            matches.append(
                SkillMatch(
                    skill=required_skill,
                    status="missing",
                    score=0.0,
                    evidence=[],
                    explanation=(
                        "Compétence non déclarée "
                        "explicitement. Le référentiel la "
                        "range parmi celles qui ne se "
                        "déduisent pas d'un parcours : un "
                        "outil ou un savoir s'apprend, il "
                        "ne se suppose pas."
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
    # NIVEAU D'EXIGENCE
    # ========================================================
    #
    # Le statut dit ce que le candidat sait faire ; le niveau dit ce
    # que l'annonce en demande. Les deux sont indépendants, et il
    # faut les deux pour qu'un écart veuille dire quelque chose :
    # « Jira absent » ne pèse pas comme « gestion de projet absente ».

    niveaux = classify_requirements(
        [match.skill for match in matches],
        job_text,
        hints=importance_hints,
    )

    for match in matches:

        match.importance = niveaux.get(
            normalise_terme(match.skill),
            IMPORTANCE_PAR_DEFAUT,
        )

    # ========================================================
    # INFERENCE COMPOSITE
    # ========================================================
    #
    # Certaines compétences sont des ensembles : elles ne se
    # constatent pas dans une phrase, elles se constatent dans un
    # faisceau. Product Management en est une — la déduire d'une
    # ressemblance de vocabulaire serait exactement le genre de
    # flatterie que ce moteur refuse.
    #
    # Ce que le référentiel associe à une compétence tient lieu de
    # composition : `related_skills` dit de quoi elle est faite. Le
    # moteur codait à la place les neuf composantes du Product
    # Management, ce qui n'a jamais rien pu déduire d'autre.
    #
    # Règle inchangée :
    #
    # - au moins 3 composantes distinctes présentes ou déduites
    # - au moins 1 composante réellement prouvée ou déclarée
    #
    # Une entrée sans compétences associées — c'est le cas de toutes
    # celles importées en masse — ne produit aucune inférence
    # composite : on ne devine pas une composition qu'on ignore.
    # ========================================================

    par_forme_canonique = {
        _canonical_skill_name(match.skill): match
        for match in matches
    }

    for match in matches:

        if match.status != "missing":
            continue

        entree = find_skill_by_name(match.skill)

        if entree is None or not entree.is_composite:
            continue

        if not entree.related_skills:
            continue

        composantes = []

        for nom in entree.related_skills:

            composante = par_forme_canonique.get(
                _canonical_skill_name(nom)
            )

            if composante is None:
                continue

            if composante.status in PRESENT_STATUSES | {"inferred"}:
                composantes.append(composante)

        # NOTE : une compétence déclarée sans preuve compte encore
        # ici, comme avant l'introduction du statut "declared".
        # Restreindre cette inférence aux seules compétences prouvées
        # changerait les résultats de matching : à trancher à part.
        prouvees = [
            composante
            for composante in composantes
            if composante.status in PRESENT_STATUSES
        ]

        if len(composantes) < MIN_COMPOSITE_COMPONENTS or not prouvees:
            continue

        if len(composantes) >= 5:
            inference_score = INFERRED_STRONG_SCORE
            inference_level = "forte"

        elif len(composantes) >= 4:
            inference_score = INFERRED_GOOD_SCORE
            inference_level = "bonne"

        else:
            inference_score = INFERRED_MODERATE_SCORE
            inference_level = "prudente"

        noms = [
            composante.skill
            for composante in sorted(
                composantes,
                key=lambda item: item.score,
                reverse=True,
            )
        ]

        match.status = "inferred"
        match.score = inference_score

        match.evidence = [
            (
                f"Inférence composite : {len(composantes)} "
                "compétences que le référentiel associe à "
                f"« {entree.canonical_name} » sont déjà "
                "démontrées ou déduites."
            ),
            "Composantes : " + ", ".join(noms),
        ]

        match.explanation = (
            f"{entree.canonical_name} n'est pas explicitement "
            f"déclaré, mais une inférence {inference_level} est "
            "possible à partir d'un ensemble cohérent de "
            "compétences associées."
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

        # ----------------------------------------------------
        # PONDERATION PAR L'ORDRE D'APPARITION
        # ----------------------------------------------------
        #
        # La moyenne simple traitait un outil cité en fin de liste à
        # égalité avec la compétence cœur du poste. Tant que le
        # référentiel ne reconnaissait que quelques termes par
        # annonce, cela passait inaperçu ; avec un référentiel large,
        # une annonce qui énumère « Jira, Miro, GitLab, Planner, MS
        # Project » voyait son score s'effondrer sur des détails.
        #
        # Les exigences arrivent dans leur ordre d'apparition dans
        # l'annonce. Ce que l'annonce cite en premier pèse davantage :
        # c'est une heuristique, mais elle correspond à la façon dont
        # une offre est rédigée — l'essentiel d'abord, l'outillage
        # ensuite.
        #
        # Le rang ne suffisait pas : à l'intérieur d'une énumération
        # d'outils, l'ordre ne veut plus rien dire. Le niveau
        # d'exigence lu dans l'annonce (essentielle / souhaitée /
        # mention) s'y multiplie — un signal sur ce que l'annonce
        # exige, l'autre sur la place qu'elle lui donne.

        poids = [
            POIDS_IMPORTANCE.get(
                match.importance,
                POIDS_IMPORTANCE[IMPORTANCE_PAR_DEFAUT],
            )
            * (1.0 / (1.0 + rang / SKILL_WEIGHT_DECAY))
            for rang, match in enumerate(matches)
        ]

        total_skill_score = sum(
            match.score * poids_match
            for match, poids_match in zip(matches, poids)
        )

        score_skills = round(
            total_skill_score / sum(poids) * 100,
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
        #
        # NOTE : une compétence déclarée sans preuve pèse ici autant
        # qu'une compétence prouvée, comme avant l'introduction du
        # statut "declared". Lui donner un poids intermédiaire ferait
        # baisser les scores existants : arbitrage à part entière,
        # volontairement non fait dans ce commit.
        # ----------------------------------------------------

        present_count = sum(
            match.status in PRESENT_STATUSES
            for match in matches
        )

        inferred_count = sum(
            match.status == "inferred"
            for match in matches
        )

        score_experience = round(
            (
                present_count * EXPERIENCE_PROVEN_WEIGHT
                + inferred_count * EXPERIENCE_INFERRED_WEIGHT
            )
            / len(matches),
            1,
        )

        # ========================================================
        # DOMAINES
        # ========================================================
        #
        # Une annonce couvre plusieurs domaines ; la question est de
        # savoir dans combien d'entre eux le candidat a quelque chose
        # à montrer. Couvrir quatre exigences réparties sur quatre
        # domaines n'est pas la même candidature que couvrir quatre
        # exigences du même domaine.
        #
        # Le moteur cherchait ici trois mots dans le texte :
        # « e-commerce », « adtech », « digital ». Mesuré sur les
        # treize annonces du corpus, ce score valait 100 sur les
        # treize — toutes contiennent « digital », et le profil
        # aussi. Il ne mesurait plus rien, et ajoutait dix points à
        # tout le monde. Pour un autre métier il n'aurait rien
        # mesuré non plus, mais dans l'autre sens.
        #
        # Les domaines viennent maintenant du référentiel : la
        # catégorie de chaque exigence qu'il reconnaît. Aucun
        # vocabulaire codé en dur, et la mesure vaut pour
        # l'infirmière comme pour le développeur.

        domaines_annonce: set[str] = set()
        domaines_couverts: set[str] = set()

        for match in matches:

            entree = find_skill_by_name(match.skill)

            if entree is None or not entree.category:
                continue

            domaines_annonce.add(entree.category)

            if match.status in PRESENT_STATUSES:
                domaines_couverts.add(entree.category)

        if not domaines_annonce:

            # Aucune exigence rattachée au référentiel : il n'y a
            # pas de domaine à comparer. Mieux vaut reprendre le
            # score des compétences que d'inventer une valeur.
            score_domain = score_skills

        else:

            score_domain = round(
                len(domaines_couverts)
                / len(domaines_annonce)
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

        elif match.status == "declared":

            strengths.append(
                f"{match.skill} : "
                "compétence déclarée, à documenter"
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

            # Le niveau change tout pour qui lit la liste : un outil
            # cité en exemple et une condition d'entrée non couverte
            # n'appellent pas la même décision.
            weaknesses.append(
                f"{match.skill} : "
                "compétence manquante "
                f"({LIBELLES_IMPORTANCE[match.importance]}"
                " par l'annonce)"
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
    importance_hints: dict[str, str] | None = None,
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
        importance_hints=importance_hints,
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
        # DETAIL PAR COMPETENCE
        # ----------------------------------------------------
        #
        # Le détail est remplacé intégralement à chaque analyse :
        # il décrit l'analyse courante, pas son historique.

        db.flush()

        (
            db.query(JobSkillMatchDB)
            .filter(
                JobSkillMatchDB.job_match_id == match.id
            )
            .delete(synchronize_session=False)
        )

        for skill_match in result.matches:

            db.add(
                JobSkillMatchDB(
                    id=f"skill-match-{uuid4()}",
                    job_match_id=match.id,
                    skill=skill_match.skill,
                    canonical_skill=_canonical_skill_name(
                        skill_match.skill
                    ),
                    status=skill_match.status,
                    importance=skill_match.importance,
                    score=skill_match.score,
                    explanation=skill_match.explanation,
                    evidence=list(skill_match.evidence),
                )
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