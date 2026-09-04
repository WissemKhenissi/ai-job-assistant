from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from services.skill_catalog_service import (
    CatalogSkill,
    get_skill_semantic_corpus,
)


# ============================================================
# CONFIGURATION
# ============================================================

SEMANTIC_MATCH_THRESHOLD = 0.48

SEMANTIC_STRONG_THRESHOLD = 0.70
SEMANTIC_VERY_STRONG_THRESHOLD = 0.82

SEMANTIC_WEIGHT = 0.65
SPECIFICITY_WEIGHT = 0.25
CONTEXT_WEIGHT = 0.10


# ============================================================
# RESULTAT
# ============================================================

@dataclass(frozen=True)
class SemanticSkillMatch:
    skill: CatalogSkill
    score: float
    confidence: str
    matched_text: str

    method: str = "semantic"

    semantic_score: float = 0.0
    specificity_score: float = 0.0
    context_score: float = 0.0


# ============================================================
# MODELE SEMANTIQUE
# ============================================================

_model = None
_model_load_attempted = False


def _get_model():
    """
    Charge sentence-transformers uniquement lorsque nécessaire.

    Le modèle est conservé en mémoire après le premier chargement.
    """

    global _model
    global _model_load_attempted

    if _model_load_attempted:
        return _model

    _model_load_attempted = True

    try:

        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(
            "paraphrase-multilingual-MiniLM-L12-v2"
        )

    except Exception:

        _model = None

    return _model


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
        r"[^a-z0-9+#. ]",
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


# ============================================================
# SPECIFICITE
# ============================================================

SPECIFIC_PATTERNS: dict[str, tuple[str, ...]] = {

    "Product Management": (
        "product management",
        "product manager",
        "gestion de produit",
        "management produit",
        "vision produit",
    ),

    "Product Discovery": (
        "product discovery",
        "discovery produit",
        "decouverte produit",
        "identifier les besoins",
        "identifier les problemes utilisateurs",
        "identifier les opportunites",
        "comprendre les besoins utilisateurs",
    ),

    "Product Delivery": (
        "product delivery",
        "delivery produit",
        "livraison du produit",
        "piloter le delivery",
        "piloter les developpements",
        "livraison incrementale",
        "mise en production",
        "suivi des livraisons",
    ),

    "Product Strategy": (
        "product strategy",
        "strategie produit",
        "vision produit",
        "objectifs produit",
        "proposition de valeur",
        "valeur business",
    ),

    "Roadmap produit": (
        "product roadmap",
        "roadmap produit",
        "definir la roadmap",
        "gerer la roadmap",
        "planifier la roadmap",
        "trajectoire produit",
    ),

    "Priorisation": (
        "priorisation",
        "prioritisation",
        "prioritize",
        "prioritization",
        "definir les priorites",
        "prioriser les fonctionnalites",
        "prioriser les features",
        "prioriser les taches",
        "arbitrer les fonctionnalites",
        "arbitrage",
        "valeur et faisabilite",
        "impact et faisabilite",
        "valeur utilisateur",
    ),

    "Backlog Management": (
        "backlog management",
        "gestion du backlog",
        "product backlog",
        "backlog produit",
        "gerer le backlog",
        "maintenir le backlog",
        "prioriser le backlog",
        "alimenter le backlog",
        "refinement du backlog",
        "backlog refinement",
    ),

    "Gestion de projet": (
        "gestion de projet",
        "pilotage de projet",
        "conduite de projet",
        "project management",
        "piloter un projet",
        "coordonner un projet",
        "suivre un projet",
        "planifier un projet",
    ),

    "Stakeholder Management": (
        "stakeholder management",
        "stakeholders management",
        "gestion des parties prenantes",
        "gestion des stakeholders",
        "parties prenantes",
        "parties prenantes internes",
        "parties prenantes externes",
        "equipes metiers",
        "equipes techniques",
        "clients et partenaires",
        "coordination des parties prenantes",
        "coordonner les parties prenantes",
        "alignement des parties prenantes",
        "coordination transverse",
    ),

    "Agile / Scrum": (
        "agile",
        "scrum",
        "agile scrum",
        "methodologie agile",
        "methodes agiles",
        "sprint",
        "sprints",
        "cycles iteratifs",
        "cycle iteratif",
        "developpement iteratif",
        "developpements iteratifs",
        "livraison incrementale",
        "amelioration continue",
        "ceremonies scrum",
        "daily scrum",
        "sprint planning",
        "sprint review",
        "retrospective",
    ),

    "Kanban": (
        "kanban",
        "flux de travail",
        "work in progress",
        "wip",
        "limitation du travail en cours",
    ),

    "Data Analysis": (
        "data analysis",
        "data analytics",
        "analyse de donnees",
        "analyse des donnees",
        "analyser les donnees",
        "analyse des performances",
        "analyse de performance",
        "indicateurs de performance",
        "indicateur de performance",
        "kpi",
        "kpis",
        "mesurer la performance",
        "mesurer les performances",
        "data driven",
    ),

    "Data Science": (
        "data science",
        "data scientist",
        "science des donnees",
        "modeles predictifs",
        "modelisation predictive",
        "modeles statistiques",
    ),

    "Machine Learning": (
        "machine learning",
        "apprentissage automatique",
        "modeles de machine learning",
        "modeles ml",
        "machine learning engineering",
        "modeles predictifs",
        "prediction",
        "classification automatique",
    ),

    "Artificial Intelligence": (
        "artificial intelligence",
        "intelligence artificielle",
        "produits ia",
        "produit ia",
        "solutions ia",
        "technologies ia",
    ),

    "SQL": (
        "sql",
        "requete sql",
        "requetes sql",
        "sql queries",
        "langage sql",
    ),

    "Python": (
        "python",
        "programmation python",
        "developpement python",
        "python programming",
    ),

    "R": (
        "langage r",
        "r programming",
        "r programming language",
        "programmation r",
    ),

    "AWS": (
        "aws",
        "amazon web services",
    ),

    "Azure": (
        "azure",
        "microsoft azure",
    ),

    "Google Cloud": (
        "google cloud",
        "google cloud platform",
        "gcp",
    ),

    "User Research": (
        "user research",
        "recherche utilisateur",
        "recherche utilisateurs",
        "customer research",
        "etude utilisateur",
        "etude utilisateurs",
        "entretiens utilisateurs",
        "interviews utilisateurs",
        "besoins utilisateurs",
        "besoin utilisateur",
        "besoins et comportements des utilisateurs",
        "comportements des utilisateurs",
        "analyser les besoins utilisateurs",
        "analyser les comportements utilisateurs",
        "analyser les besoins et comportements",
        "comprendre les besoins utilisateurs",
        "comprendre les comportements utilisateurs",
        "problemes utilisateurs",
        "opportunites utilisateurs",
        "feedback utilisateurs",
    ),

    "UX": (
        "ux",
        "user experience",
        "experience utilisateur",
        "ux design",
        "parcours utilisateur",
        "experience digitale",
    ),

    "UI": (
        "ui",
        "user interface",
        "interface utilisateur",
        "ui design",
        "interface graphique",
    ),

    "Jira": (
        "jira",
        "atlassian jira",
    ),

    "Microsoft Excel": (
        "excel",
        "microsoft excel",
        "excel macros",
        "macros excel",
        "vba excel",
    ),

    "E-commerce": (
        "e commerce",
        "ecommerce",
        "commerce electronique",
        "digital commerce",
        "parcours d achat",
        "conversion ecommerce",
    ),
}


# ============================================================
# CONTEXTE
# ============================================================

CONTEXT_PATTERNS: dict[str, tuple[str, ...]] = {

    "Stakeholder Management": (
        "parties prenantes",
        "stakeholders",
        "equipes metiers",
        "equipes techniques",
        "clients",
        "partenaires",
        "coordination",
        "alignement",
        "communication",
    ),

    "Priorisation": (
        "priorites",
        "valeur",
        "impact",
        "faisabilite",
        "effort",
        "cout",
        "urgence",
        "fonctionnalites",
    ),

    "User Research": (
        "utilisateurs",
        "besoins",
        "comportements",
        "usages",
        "attentes",
        "frustrations",
        "interviews",
        "sondages",
        "insights",
    ),

    "Product Discovery": (
        "utilisateurs",
        "besoins",
        "problemes",
        "opportunites",
        "hypotheses",
        "discovery",
        "insights",
    ),

    "Agile / Scrum": (
        "iteration",
        "iteratif",
        "iterative",
        "sprint",
        "sprints",
        "cycle de developpement",
        "cycles de developpement",
        "cycles iteratifs",
        "developpement iteratif",
        "developpements iteratifs",
        "equipe",
        "livraison",
        "increment",
        "livraison incrementale",
        "retrospective",
        "amelioration continue",
    ),

    "Product Delivery": (
        "product delivery",
        "delivery produit",
        "livraison du produit",
        "piloter le delivery",
        "piloter les developpements",
        "developpements par cycles iteratifs",
        "livraison incrementale",
        "mise en production",
        "suivi des livraisons",
    ),

    "Data Analysis": (
        "donnees",
        "data",
        "kpi",
        "indicateurs",
        "performance",
        "analytics",
        "mesurer",
        "analyse",
    ),

    "Machine Learning": (
        "modele",
        "modeles",
        "donnees",
        "prediction",
        "classification",
        "algorithme",
    ),

    "Data Science": (
        "donnees",
        "statistiques",
        "modeles",
        "prediction",
        "analyse",
    ),

    "Product Strategy": (
        "vision",
        "strategie",
        "objectifs",
        "valeur",
        "business",
        "marche",
    ),

    "Backlog Management": (
        "backlog",
        "stories",
        "fonctionnalites",
        "priorisation",
        "sprint",
        "product owner",
    ),
}


# ============================================================
# SPECIFICITE
# ============================================================

def _specificity_score(
    text: str,
    skill: CatalogSkill,
) -> float:

    normalized_text = _normalize(text)
    skill_name = skill.canonical_name

    # --------------------------------------------------------
    # USER RESEARCH
    # --------------------------------------------------------

    if skill_name == "User Research":

        signals = (
            "besoins et comportements des utilisateurs",
            "comportements des utilisateurs",
            "analyser les besoins utilisateurs",
            "analyser les comportements utilisateurs",
            "analyser les besoins et comportements",
            "recherche utilisateur",
            "recherche utilisateurs",
            "user research",
            "customer research",
            "entretiens utilisateurs",
        )

        if any(
            _contains_term(
                normalized_text,
                signal,
            )
            for signal in signals
        ):
            return 1.0

    # --------------------------------------------------------
    # STAKEHOLDER
    # --------------------------------------------------------

    if skill_name == "Stakeholder Management":

        signals = (
            "gestion des parties prenantes",
            "gestion des stakeholders",
            "stakeholder management",
            "coordination des parties prenantes",
            "coordonner les parties prenantes",
            "parties prenantes",
            "equipes metiers",
            "equipes techniques",
        )

        if any(
            _contains_term(
                normalized_text,
                signal,
            )
            for signal in signals
        ):
            return 0.9

    # --------------------------------------------------------
    # PRIORISATION
    # --------------------------------------------------------

    if skill_name == "Priorisation":

        signals = (
            "priorisation",
            "prioritization",
            "prioritize",
            "definir les priorites",
            "prioriser les fonctionnalites",
            "prioriser les features",
            "prioriser les taches",
            "valeur et faisabilite",
            "impact et faisabilite",
        )

        if any(
            _contains_term(
                normalized_text,
                signal,
            )
            for signal in signals
        ):
            return 0.8

    # --------------------------------------------------------
    # DATA ANALYSIS
    # --------------------------------------------------------

    if skill_name == "Data Analysis":

        signals = (
            "analyse de donnees",
            "analyse des donnees",
            "analyser les donnees",
            "indicateurs de performance",
            "indicateur de performance",
            "kpi",
            "kpis",
            "data analysis",
            "data analytics",
        )

        if any(
            _contains_term(
                normalized_text,
                signal,
            )
            for signal in signals
        ):
            return 0.9

    # --------------------------------------------------------
    # AGILE
    # --------------------------------------------------------

    if skill_name == "Agile / Scrum":

        signals = (
            "agile",
            "scrum",
            "methodologie agile",
            "methodes agiles",
            "sprint",
            "sprints",
            "cycles iteratifs",
            "cycle iteratif",
            "developpement iteratif",
            "developpements iteratifs",
            "retrospective",
            "sprint planning",
            "sprint review",
            "piloter les developpements par cycles iteratifs",
            "piloter le developpement par cycles iteratifs",
            "developpements par cycles iteratifs",
            "cycles de developpement iteratifs",
        )

        if any(
            _contains_term(
                normalized_text,
                signal,
            )
            for signal in signals
        ):
            return 1.0

    # --------------------------------------------------------
    # PRODUCT DELIVERY
    # --------------------------------------------------------

    if skill_name == "Product Delivery":

        signals = (
            "product delivery",
            "delivery produit",
            "livraison du produit",
            "piloter le delivery",
            "piloter les developpements",
            "piloter les developpements par cycles iteratifs",
            "mise en production",
            "suivi des livraisons",
        )

        if any(
            _contains_term(
                normalized_text,
                signal,
            )
            for signal in signals
        ):
            return 0.9

    # --------------------------------------------------------
    # REGLES GENERALES
    # --------------------------------------------------------

    patterns = SPECIFIC_PATTERNS.get(
        skill_name,
        (),
    )

    if not patterns:
        return 0.0

    matched = sum(
        1
        for pattern in patterns
        if _contains_term(
            normalized_text,
            pattern,
        )
    )

    if matched >= 3:
        return 0.9

    if matched == 2:
        return 0.7

    if matched == 1:
        return 0.5

    return 0.0


# ============================================================
# CONTEXTE
# ============================================================

def _context_score(
    text: str,
    skill: CatalogSkill,
) -> float:

    normalized_text = _normalize(text)

    patterns = CONTEXT_PATTERNS.get(
        skill.canonical_name,
        (),
    )

    if not patterns:
        return 0.0

    matched = sum(
        1
        for pattern in patterns
        if _contains_term(
            normalized_text,
            pattern,
        )
    )

    if matched >= 4:
        return 0.45

    if matched >= 2:
        return 0.30

    if matched == 1:
        return 0.20

    return 0.0


# ============================================================
# FALLBACK LEXICAL
# ============================================================

def _lexical_similarity(
    text: str,
    skill: CatalogSkill,
) -> float:

    normalized_text = _normalize(text)

    candidates = (
        skill.canonical_name,
        *skill.aliases,
    )

    for candidate in candidates:

        if _contains_term(
            normalized_text,
            candidate,
        ):
            return 1.0

    return 0.0


# ============================================================
# CONFIDENCE
# ============================================================

def _confidence_from_score(
    score: float,
) -> str:

    if score >= SEMANTIC_VERY_STRONG_THRESHOLD:
        return "very_strong"

    if score >= SEMANTIC_STRONG_THRESHOLD:
        return "strong"

    if score >= SEMANTIC_MATCH_THRESHOLD:
        return "possible"

    return "none"


# ============================================================
# SCORE FINAL
# ============================================================

def _calculate_final_score(
    semantic_score: float,
    specificity_score: float,
    context_score: float,
) -> float:

    if specificity_score >= 0.9:

        score = (
            semantic_score * 0.45
            + specificity_score * 0.45
            + context_score * 0.10
        )

    elif specificity_score >= 0.8:

        score = (
            semantic_score * 0.50
            + specificity_score * 0.40
            + context_score * 0.10
        )

    else:

        score = (
            semantic_score * SEMANTIC_WEIGHT
            + specificity_score * SPECIFICITY_WEIGHT
            + context_score * CONTEXT_WEIGHT
        )

    return min(
        1.0,
        max(
            0.0,
            score,
        ),
    )


# ============================================================
# MATCHING SEMANTIQUE
# ============================================================

def find_semantic_skill_matches(
    text: str,
    threshold: float = SEMANTIC_MATCH_THRESHOLD,
    limit: int = 10,
    restrict_to: set[str] | None = None,
) -> list[SemanticSkillMatch]:
    """
    Compétences du référentiel sémantiquement proches d'un texte.

    `restrict_to` limite la recherche à des formes canoniques
    précises. Ce n'est pas une optimisation accessoire : l'appelant
    principal ne s'intéresse qu'à **une** compétence à la fois, et
    faire encoder tout le référentiel pour la retrouver coûtait 209
    secondes par appel une fois le référentiel ESCO importé — l'analyse
    d'une seule annonce devenait impraticable.

    Restreindre corrige aussi un défaut de fond : avec `limit`, la
    compétence recherchée pouvait être évincée du classement par dix
    autres mieux notées, et déclarée absente à tort.
    """

    if not text or not text.strip():
        return []

    corpus = get_skill_semantic_corpus()

    if restrict_to:

        from services.matching.normalization import (
            _canonical_skill_name,
        )

        corpus = [
            item
            for item in corpus
            if _canonical_skill_name(item["skill"].canonical_name)
            in restrict_to
        ]

    if not corpus:
        return []

    model = _get_model()

    # ========================================================
    # FALLBACK LEXICAL
    # ========================================================

    if model is None:

        results = []

        for item in corpus:

            skill = item["skill"]

            lexical_score = _lexical_similarity(
                text,
                skill,
            )

            if lexical_score <= 0:
                continue

            specificity_score = _specificity_score(
                text,
                skill,
            )

            context_score = _context_score(
                text,
                skill,
            )

            final_score = _calculate_final_score(
                lexical_score,
                specificity_score,
                context_score,
            )

            if final_score < threshold:
                continue

            results.append(
                SemanticSkillMatch(
                    skill=skill,
                    score=round(
                        final_score,
                        4,
                    ),
                    confidence="very_strong",
                    matched_text=text,
                    method="lexical",
                    semantic_score=round(
                        lexical_score,
                        4,
                    ),
                    specificity_score=round(
                        specificity_score,
                        4,
                    ),
                    context_score=round(
                        context_score,
                        4,
                    ),
                )
            )

        results.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        return results[:limit]

    # ========================================================
    # CORPUS
    # ========================================================

    corpus_texts = [
        item.get("texts", {}).get(
            "full",
            "",
        )
        for item in corpus
    ]

    # ========================================================
    # EMBEDDINGS
    # ========================================================

    try:

        text_embedding = model.encode(
            text,
            normalize_embeddings=True,
        )

        skill_embeddings = model.encode(
            corpus_texts,
            normalize_embeddings=True,
        )

    except Exception:

        return find_semantic_skill_matches(
            text=text,
            threshold=threshold,
            limit=limit,
        )

    # ========================================================
    # SIMILARITES
    # ========================================================

    scores = skill_embeddings @ text_embedding

    results: list[SemanticSkillMatch] = []

    for item, semantic_score in zip(
        corpus,
        scores,
    ):

        skill = item["skill"]

        semantic_score_float = float(
            semantic_score
        )

        specificity_score = _specificity_score(
            text,
            skill,
        )

        context_score = _context_score(
            text,
            skill,
        )

        final_score = _calculate_final_score(
            semantic_score_float,
            specificity_score,
            context_score,
        )

        if final_score < threshold:
            continue

        results.append(
            SemanticSkillMatch(
                skill=skill,
                score=round(
                    final_score,
                    4,
                ),
                confidence=_confidence_from_score(
                    final_score
                ),
                matched_text=text,
                method="semantic",
                semantic_score=round(
                    semantic_score_float,
                    4,
                ),
                specificity_score=round(
                    specificity_score,
                    4,
                ),
                context_score=round(
                    context_score,
                    4,
                ),
            )
        )

    results.sort(
        key=lambda item: (
            item.score,
            item.semantic_score,
            item.specificity_score,
        ),
        reverse=True,
    )

    return results[:limit]