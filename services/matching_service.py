from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable
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

from services.skill_catalog_service import (
    get_active_skills,
    normalize_skill_text,
)
from services.skill_semantic_service import (
    find_semantic_skill_matches,
)


# ============================================================
# NORMALISATION / ALIAS
# ============================================================

# Les alias de compétences ne sont plus dupliqués ici : ils viennent
# du référentiel skill_catalog (table skill_catalog, exposée par
# services.skill_catalog_service), seule source de vérité. Voir
# _canonical_skill_name() / _canonical_alias_index() plus bas.


# ============================================================
# INFERENCE LEXICALE
# ============================================================

INFERENCE_KEYWORDS = {
    "agile scrum": (
        "iteration",
        "iterative",
        "mvp",
        "test",
        "amelioration continue",
        "sprint",
        "cycle iteratif",
        "cycles iteratifs",
        "developpement iteratif",
        "developpements iteratifs",
    ),
    "priorisation": (
        "priorite",
        "priorites",
        "arbitrage",
        "mvp",
        "quick win",
        "optimisation",
        "valeur",
        "cout",
        "faisabilite",
    ),
    "backlog management": (
        "priorite",
        "arbitrage",
        "mvp",
        "iteration",
        "fonctionnalite",
        "backlog",
        "user story",
        "stories",
    ),
    "stakeholder management": (
        "coordination",
        "partenaire",
        "equipe",
        "juridique",
        "comptabilite",
        "ux",
        "ui",
        "it",
        "client",
        "parties prenantes",
        "stakeholders",
    ),
    "data kpi": (
        "kpi",
        "performance",
        "marge",
        "chiffre d affaires",
        "ca",
        "reporting",
        "metrique",
        "conversion",
        "roi",
    ),
    "gestion de projet": (
        "pilotage",
        "coordination",
        "mise en production",
        "projet",
        "planning",
        "blocage",
        "deadline",
    ),
    "e commerce": (
        "e commerce",
        "fnac",
        "france billet",
        "post achat",
        "confirmation de commande",
        "achat",
    ),
    "product strategy": (
        "business model",
        "proposition de valeur",
        "opportunite",
        "valeur business",
        "monetisation",
        "offre",
        "strategie",
    ),
    "roadmap produit": (
        "planning",
        "priorite",
        "evolution",
        "iteration",
        "projet",
        "mise en production",
        "roadmap",
    ),
    "experimentation": (
        "test",
        "iteration",
        "optimisation",
        "mvp",
        "mesure",
        "kpi",
    ),
    "ux": (
        "ux",
        "parcours",
        "experience utilisateur",
        "interface",
        "landing page",
    ),
    "ui": (
        "ui",
        "interface",
        "design",
        "landing page",
    ),
}

# ============================================================
# INFERENCE SEMANTIQUE
# ============================================================

SEMANTIC_INFERENCE_THRESHOLD = 0.62

SEMANTIC_INFERENCE_STRONG_THRESHOLD = 0.75

SEMANTIC_SPECIFICITY_THRESHOLD = 0.80


# ============================================================
# PONDERATION DES STATUTS
# ============================================================

# Une compétence explicitement prouvée est la référence.
PROVEN_SCORE = 1.00

# Compétence déclarée dans le CV mais sans preuve détaillée.
DECLARED_SCORE = 0.90

# Inférence sémantique :
# la valeur dépend de la qualité de la correspondance.
INFERRED_VERY_STRONG_SCORE = 0.85
INFERRED_STRONG_SCORE = 0.80
INFERRED_GOOD_SCORE = 0.75
INFERRED_MODERATE_SCORE = 0.70
INFERRED_PRUDENT_SCORE = 0.60

MISSING_SCORE = 0.00


# ============================================================
# PONDERATION DU SCORE D'EXPERIENCE
# ============================================================
#
# Le score d'expérience est exprimé sur 100 : il mesure la part
# des compétences demandées que le candidat sait démontrer.
#
# Une compétence prouvée (preuve EvidenceDB liée) vaut le maximum,
# une compétence seulement déduite vaut nettement moins — une
# inférence reste une hypothèse, pas un fait affirmé.

EXPERIENCE_PROVEN_WEIGHT = 100

EXPERIENCE_INFERRED_WEIGHT = 60


# ============================================================
# COMPETENCES AUTORISEES A L'INFERENCE
# ============================================================

SEMANTIC_INFERENCE_SKILLS = {
    "agile scrum",
    "priorisation",
    "backlog management",
    "stakeholder management",
    "product discovery",
    "product strategy",
    "roadmap produit",
    "product delivery",
    "experimentation",
    # "analyse utilisateur" fusionne désormais dans "user research"
    # (alias du référentiel skill_catalog) via _canonical_skill_name().
    "user research",
    "data analysis",
    "gestion de projet",
}


# ============================================================
# COMPETENCES QUI NE DOIVENT JAMAIS ETRE INDUITES
# ============================================================

SEMANTIC_INFERENCE_EXCLUDED = {
    "product management",
    "python",
    "sql",
    "r",
    "aws",
    "azure",
    "google cloud",
    "machine learning",
    "data science",
    "artificial intelligence",
    "jira",
}


# ============================================================
# OBJETS DE RESULTAT
# ============================================================

@dataclass
class SkillMatch:
    skill: str
    status: str
    score: float
    evidence: list[str]
    explanation: str


@dataclass
class MatchingResult:
    score_global: float
    score_skills: float
    score_experience: float
    score_domain: float
    matches: list[SkillMatch]
    strengths: list[str]
    weaknesses: list[str]

    @property
    def matched_skills(self) -> list[str]:
        return [
            match.skill
            for match in self.matches
            if match.status == "proven"
        ]

    @property
    def inferred_skills(self) -> list[str]:
        return [
            match.skill
            for match in self.matches
            if match.status == "inferred"
        ]

    @property
    def missing_skills(self) -> list[str]:
        return [
            match.skill
            for match in self.matches
            if match.status == "missing"
        ]


# ============================================================
# NORMALISATION
# ============================================================

def _normalize(value: str) -> str:

    if not value:
        return ""

    normalized = unicodedata.normalize(
        "NFKD",
        value,
    )

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    normalized = normalized.casefold()

    normalized = re.sub(
        r"[-_/]",
        " ",
        normalized,
    )

    normalized = re.sub(
        r"[^a-z0-9 ]",
        " ",
        normalized,
    )

    return re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()


def _contains_term(
    text: str,
    term: str,
) -> bool:

    normalized_text = _normalize(text)
    normalized_term = _normalize(term)

    if not normalized_term:
        return False

    pattern = (
        rf"(?<![a-z0-9])"
        rf"{re.escape(normalized_term)}"
        rf"(?![a-z0-9])"
    )

    return (
        re.search(
            pattern,
            normalized_text,
            flags=re.IGNORECASE,
        )
        is not None
    )


_canonical_alias_index_cache: dict[str, str] | None = None


def _canonical_alias_index() -> dict[str, str]:
    """
    Construit (une seule fois par process) l'index
    "alias normalisé -> nom canonique normalisé" à partir du
    référentiel skill_catalog.

    Remplace l'ancien dictionnaire SKILL_ALIASES codé en dur :
    skill_catalog est désormais l'unique source de vérité pour les
    alias de compétences.
    """

    global _canonical_alias_index_cache

    if _canonical_alias_index_cache is None:

        index: dict[str, str] = {}

        for skill in get_active_skills():

            canonical_key = normalize_skill_text(
                skill.canonical_name
            )

            for name in (
                skill.canonical_name,
                *skill.aliases,
            ):

                index[normalize_skill_text(name)] = canonical_key

        _canonical_alias_index_cache = index

    return _canonical_alias_index_cache


def _canonical_skill_name(
    value: str,
) -> str:

    normalized_value = _normalize(value)

    return _canonical_alias_index().get(
        normalized_value,
        normalized_value,
    )


# ============================================================
# PROFIL — TEXTE GLOBAL
# ============================================================

def _text_from_profile(
    skills: Iterable[SkillDB],
    experiences: Iterable[ExperienceDB],
    achievements: Iterable[AchievementDB],
    evidence: Iterable[EvidenceDB],
) -> str:

    parts: list[str] = []

    # --------------------------------------------------------
    # COMPETENCES
    # --------------------------------------------------------

    for skill in skills:

        parts.extend(
            [
                skill.name or "",
                skill.description or "",
                skill.category or "",
            ]
        )

    # --------------------------------------------------------
    # EXPERIENCES
    # --------------------------------------------------------

    for experience in experiences:

        parts.extend(
            [
                experience.company or "",
                experience.job_title or "",
                experience.description or "",
                experience.business_context or "",
                experience.team_context or "",
            ]
        )

    # --------------------------------------------------------
    # REALISATIONS
    # --------------------------------------------------------

    for achievement in achievements:

        parts.extend(
            [
                achievement.title or "",
                achievement.situation or "",
                achievement.action or "",
                achievement.result or "",
                achievement.metrics or "",
                achievement.description or "",
            ]
        )

    # --------------------------------------------------------
    # PREUVES
    # --------------------------------------------------------

    for item in evidence:

        parts.extend(
            [
                item.description or "",
                item.metric or "",
                item.context or "",
            ]
        )

    return _normalize(
        " ".join(parts)
    )


# ============================================================
# PROFIL — BLOCS POUR L'INFERENCE SEMANTIQUE
# ============================================================

def _profile_text_blocks(
    skills: Iterable[SkillDB],
    experiences: Iterable[ExperienceDB],
    achievements: Iterable[AchievementDB],
    evidence: Iterable[EvidenceDB],
) -> list[str]:

    blocks: list[str] = []

    # --------------------------------------------------------
    # COMPETENCES DECLAREES
    # --------------------------------------------------------

    for skill in skills:

        text = " ".join(
            [
                skill.name or "",
                skill.description or "",
                skill.category or "",
            ]
        ).strip()

        if text:

            blocks.append(
                _normalize(text)
            )

    # --------------------------------------------------------
    # EXPERIENCES
    # --------------------------------------------------------

    for experience in experiences:

        text = " ".join(
            [
                experience.company or "",
                experience.job_title or "",
                experience.description or "",
                experience.business_context or "",
                experience.team_context or "",
            ]
        ).strip()

        if text:

            blocks.append(
                _normalize(text)
            )

    # --------------------------------------------------------
    # REALISATIONS
    # --------------------------------------------------------

    for achievement in achievements:

        text = " ".join(
            [
                achievement.title or "",
                achievement.situation or "",
                achievement.action or "",
                achievement.result or "",
                achievement.metrics or "",
                achievement.description or "",
            ]
        ).strip()

        if text:

            blocks.append(
                _normalize(text)
            )

    # --------------------------------------------------------
    # PREUVES
    # --------------------------------------------------------

    for item in evidence:

        text = " ".join(
            [
                item.description or "",
                item.metric or "",
                item.context or "",
            ]
        ).strip()

        if text:

            blocks.append(
                _normalize(text)
            )

    return blocks


# ============================================================
# FORMATAGE DES PREUVES
# ============================================================

def _format_evidence(
    item: EvidenceDB,
) -> str:

    parts = []

    if item.description:
        parts.append(
            item.description
        )

    if item.metric:
        parts.append(
            item.metric
        )

    if item.context:
        parts.append(
            item.context
        )

    return " — ".join(parts)


# ============================================================
# INFERENCE LEXICALE
# ============================================================

def _find_inference_evidence(
    canonical_skill: str,
    profile_text: str,
) -> list[str]:

    keywords = INFERENCE_KEYWORDS.get(
        canonical_skill,
        (),
    )

    found_keywords = []

    for keyword in keywords:

        if _contains_term(
            profile_text,
            keyword,
        ):

            found_keywords.append(
                keyword
            )

    if len(found_keywords) < 2:
        return []

    return [
        "Indices indirects trouvés : "
        + ", ".join(
            found_keywords[:5]
        )
    ]


# ============================================================
# INFERENCE SEMANTIQUE
# ============================================================

def _find_semantic_inference_evidence(
    canonical_skill: str,
    profile_texts: list[str],
) -> tuple[list[str], float] | None:
    """
    Recherche une compétence pouvant être déduite
    sémantiquement du parcours.

    L'analyse est effectuée bloc par bloc.

    IMPORTANT :

    - Les compétences explicitement exclues ne sont jamais
      inférées.
    - Un score sémantique faible ne suffit jamais.
    - Une formulation très spécifique peut renforcer
      une correspondance.
    - On conserve le meilleur bloc du parcours.
    """

    if not profile_texts:
        return None

    # ========================================================
    # SECURITE
    # ========================================================

    if canonical_skill in SEMANTIC_INFERENCE_EXCLUDED:
        return None

    if canonical_skill not in SEMANTIC_INFERENCE_SKILLS:
        return None

    best_match = None

    # ========================================================
    # ANALYSE BLOC PAR BLOC
    # ========================================================

    for profile_block in profile_texts:

        if not profile_block.strip():
            continue

        try:

            semantic_matches = (
                find_semantic_skill_matches(
                    profile_block,
                    threshold=0.45,
                    limit=10,
                )
            )

        except Exception:

            continue

        # ====================================================
        # RECHERCHE DE LA COMPETENCE
        # ====================================================

        for semantic_match in semantic_matches:

            matched_skill = _canonical_skill_name(
                semantic_match.skill.canonical_name
            )

            if matched_skill != canonical_skill:
                continue

            semantic_score = float(
                getattr(
                    semantic_match,
                    "semantic_score",
                    semantic_match.score,
                )
            )

            specificity_score = float(
                getattr(
                    semantic_match,
                    "specificity_score",
                    0.0,
                )
            )

            context_score = float(
                getattr(
                    semantic_match,
                    "context_score",
                    0.0,
                )
            )

            final_score = float(
                semantic_match.score
            )

            candidate = (
                final_score,
                semantic_score,
                specificity_score,
                context_score,
                profile_block,
            )

            if (
                best_match is None
                or candidate[:4] > best_match[:4]
            ):

                best_match = candidate

    # ========================================================
    # AUCUNE CORRESPONDANCE
    # ========================================================

    if best_match is None:
        return None

    (
        final_score,
        semantic_score,
        specificity_score,
        context_score,
        matched_text,
    ) = best_match

    # ========================================================
    # REGLE SPECIALE :
    # FORMULATION TRES SPECIFIQUE
    # ========================================================

    # Une formulation très spécifique peut compenser une
    # similarité sémantique moyenne, mais uniquement lorsque
    # le contexte est également cohérent.

    if (
        semantic_score >= 0.48
        and specificity_score >= 0.90
        and context_score >= 0.20
    ):

        return (
            [
                (
                    "Correspondance sémantique renforcée "
                    "par une formulation très spécifique "
                    f"(sem={semantic_score:.2f}, "
                    f"spec={specificity_score:.2f}, "
                    f"ctx={context_score:.2f})."
                )
            ],
            semantic_score,
        )

    # ========================================================
    # REGLE 1 :
    # SEMANTIQUE TRES FORTE
    # ========================================================

    if (
        semantic_score
        >= SEMANTIC_INFERENCE_STRONG_THRESHOLD
        and (
            specificity_score >= 0.50
            or context_score >= 0.30
        )
    ):

        return (
            [
                (
                    "Correspondance sémantique forte "
                    f"(score={semantic_score:.2f}) "
                    "avec un élément précis du parcours."
                )
            ],
            semantic_score,
        )

    # ========================================================
    # REGLE 2 :
    # SEMANTIQUE FORTE + SPECIFICITE
    # ========================================================

    if (
        semantic_score >= 0.68
        and specificity_score
        >= SEMANTIC_SPECIFICITY_THRESHOLD
    ):

        return (
            [
                (
                    "Correspondance sémantique "
                    f"(score={semantic_score:.2f}) "
                    "renforcée par une formulation "
                    "spécifique "
                    f"(score={specificity_score:.2f})."
                )
            ],
            semantic_score,
        )

    # ========================================================
    # REGLE 3 :
    # SEMANTIQUE + CONTEXTE
    # ========================================================

    if (
        semantic_score
        >= SEMANTIC_INFERENCE_THRESHOLD
        and context_score >= 0.30
    ):

        return (
            [
                (
                    "Correspondance sémantique "
                    f"(score={semantic_score:.2f}) "
                    "renforcée par le contexte "
                    f"(score={context_score:.2f})."
                )
            ],
            semantic_score,
        )

    # ========================================================
    # RIEN DE SUFFISAMMENT FIABLE
    # ========================================================

    return None


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