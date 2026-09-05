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


# ============================================================
# CACHES
# ============================================================
#
# Le moteur sémantique était appelé une poignée de fois par analyse,
# tant que douze compétences seulement pouvaient être déduites.
# Depuis que le référentiel décide lui-même, il l'est une fois par
# exigence déductible et par bloc du parcours — une centaine de fois.
#
# Sans mémoire, chaque appel refiltrait 13 476 entrées et réencodait
# les mêmes textes : 165 secondes pour une annonce de dix-sept
# exigences. Les deux caches ci-dessous sont vidés par
# skill_catalog_service.invalidate_caches(), seul point d'entrée
# après une écriture dans le référentiel.

# Forme canonique -> entrées du corpus, pour servir `restrict_to`
# sans balayer le référentiel.
_index_corpus_par_forme: dict[str, list[dict]] | None = None

# Texte -> vecteur. Les blocs du parcours reviennent à chaque
# exigence, et le texte d'une compétence à chaque bloc.
_embeddings: dict[str, object] = {}

# Au-delà, on repart de zéro plutôt que de laisser le cache enfler
# indéfiniment dans une session longue.
_MAX_EMBEDDINGS = 5000


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
# VOCABULAIRE PROPRE A UNE COMPETENCE
# ============================================================
#
# Deux dictionnaires vivaient ici : SPECIFIC_PATTERNS, vingt-sept
# compétences avec leurs formulations caractéristiques écrites à la
# main, et CONTEXT_PATTERNS, onze compétences avec leur vocabulaire
# de contexte. Deux cent quatre-vingts lignes, toutes d'un métier
# produit, plus six branches `if skill_name == ...`.
#
# Ils décidaient plus que la liste blanche de l'inférence : sans
# entrée pour une compétence, spécificité et contexte valaient zéro,
# et aucune des règles d'inférence sémantique ne pouvait plus être
# satisfaite. Mesuré sur un profil d'infirmière, la ressemblance
# sémantique atteignait 0,65 — au-dessus du seuil — et l'inférence
# échouait quand même, faute de renfort.
#
# Ce que ces dictionnaires écrivaient à la main, le référentiel le
# porte déjà : le vocabulaire propre à une compétence, ce sont son
# nom et ses alias ; son contexte, ce sont sa description et les
# compétences qu'il lui associe.

# Mots trop courants pour distinguer quoi que ce soit. La longueur
# minimale en écarte déjà la plupart ; ceux-ci lui survivent.
_MOTS_VIDES = frozenset(
    {
        "avec", "sans", "pour", "dans", "cette", "cettes", "leur",
        "leurs", "elle", "elles", "nous", "vous", "sont", "etre",
        "avoir", "faire", "fait", "plus", "moins", "tres", "tout",
        "tous", "toute", "toutes", "autre", "autres", "meme",
        "memes", "selon", "entre", "chaque", "afin", "ainsi",
        "dont", "lors", "apres", "avant", "pendant", "depuis",
        "aussi", "encore", "quand", "comme", "parce", "donc",
        "mais", "puis", "alors", "cela", "celui", "celle",
        "notamment", "permettant", "permet", "peut", "doit",
        "type", "types", "niveau", "cadre", "partir", "grace",
        "ensemble", "different", "differents", "differente",
        "differentes", "general", "generale", "divers", "diverses",
    }
)

# En deçà, un mot ne distingue rien.
_LONGUEUR_MOT_SIGNIFIANT = 4


def _mots_signifiants(texte: str) -> tuple[str, ...]:
    """Mots d'un texte assez longs et assez rares pour distinguer."""

    return tuple(
        mot
        for mot in _normalize(texte).split()
        if len(mot) >= _LONGUEUR_MOT_SIGNIFIANT
        and mot not in _MOTS_VIDES
    )


# Les deux vocabulaires ne dépendent que du référentiel : on les
# calcule une fois par compétence. Vidés par
# skill_catalog_service.invalidate_caches().
_vocabulaires: dict[str, tuple[tuple, tuple, tuple]] = {}


def _vocabulaire(
    skill: CatalogSkill,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """
    Trois listes tirées de l'entrée de référentiel :

    - les formulations propres à la compétence (nom et alias en
      plusieurs mots) — les retrouver telles quelles dans un texte
      est le signal le plus fort ;
    - les mots signifiants de ce nom et de ces alias ;
    - les mots de contexte : description et compétences associées.
    """

    if skill.id in _vocabulaires:
        return _vocabulaires[skill.id]

    formulations: list[str] = []
    mots_propres: list[str] = []

    for terme in (skill.canonical_name, *skill.aliases):

        normalise = _normalize(terme)

        if not normalise:
            continue

        if " " in normalise and normalise not in formulations:
            formulations.append(normalise)

        for mot in _mots_signifiants(terme):
            if mot not in mots_propres:
                mots_propres.append(mot)

    mots_contexte: list[str] = []

    for terme in (skill.description, *skill.related_skills):

        for mot in _mots_signifiants(terme or ""):

            # Un mot déjà propre à la compétence ne dit rien de son
            # contexte : il dirait deux fois la même chose.
            if mot in mots_propres or mot in mots_contexte:
                continue

            mots_contexte.append(mot)

    _vocabulaires[skill.id] = (
        tuple(formulations),
        tuple(mots_propres),
        tuple(mots_contexte),
    )

    return _vocabulaires[skill.id]


def _compte(texte_normalise: str, termes: tuple[str, ...]) -> int:

    return sum(
        1
        for terme in termes
        if _contains_term(texte_normalise, terme)
    )


# ============================================================
# SPECIFICITE
# ============================================================

def _specificity_score(
    text: str,
    skill: CatalogSkill,
) -> float:
    """
    Le texte emploie-t-il le vocabulaire propre à cette compétence ?

    Retrouver une formulation entière — le nom de la compétence ou
    l'un de ses alias, en plusieurs mots — vaut le maximum : c'est
    la compétence nommée, pas simplement évoquée. À défaut, on compte
    les mots qui lui appartiennent en propre.
    """

    normalized_text = _normalize(text)

    formulations, mots_propres, _ = _vocabulaire(skill)

    if _compte(normalized_text, formulations):
        return 1.0

    trouves = _compte(normalized_text, mots_propres)

    if trouves >= 3:
        return 0.9

    if trouves == 2:
        return 0.7

    if trouves == 1:
        return 0.5

    return 0.0


# ============================================================
# CONTEXTE
# ============================================================

def _context_score(
    text: str,
    skill: CatalogSkill,
) -> float:
    """
    Le texte parle-t-il du même monde que cette compétence ?

    Le vocabulaire de contexte vient de la description de la
    compétence et de celles que le référentiel lui associe. Il pèse
    moins que la spécificité : partager un champ lexical n'est pas
    exercer une compétence.
    """

    normalized_text = _normalize(text)

    _, _, mots_contexte = _vocabulaire(skill)

    trouves = _compte(normalized_text, mots_contexte)

    if trouves >= 4:
        return 0.45

    if trouves >= 2:
        return 0.30

    if trouves == 1:
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

def _corpus_par_forme() -> dict[str, list[dict]]:
    """Index du corpus sémantique par forme canonique."""

    global _index_corpus_par_forme

    if _index_corpus_par_forme is None:

        from services.matching.normalization import (
            _canonical_skill_name,
        )

        index: dict[str, list[dict]] = {}

        for item in get_skill_semantic_corpus():

            forme = _canonical_skill_name(
                item["skill"].canonical_name
            )

            index.setdefault(forme, []).append(item)

        _index_corpus_par_forme = index

    return _index_corpus_par_forme


def _encode(model, textes: list[str]):
    """
    Vecteurs des textes donnés, en ne faisant encoder que les
    inconnus.

    Retourne un tableau dans l'ordre demandé.
    """

    import numpy

    manquants = [
        texte
        for texte in dict.fromkeys(textes)
        if texte not in _embeddings
    ]

    if manquants:

        if len(_embeddings) + len(manquants) > _MAX_EMBEDDINGS:
            _embeddings.clear()

        vecteurs = model.encode(
            manquants,
            normalize_embeddings=True,
        )

        for texte, vecteur in zip(manquants, vecteurs):
            _embeddings[texte] = vecteur

    return numpy.array([_embeddings[texte] for texte in textes])


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

    if restrict_to:

        index = _corpus_par_forme()

        corpus = [
            item
            for forme in restrict_to
            for item in index.get(forme, ())
        ]

    else:

        corpus = get_skill_semantic_corpus()

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

        text_embedding = _encode(model, [text])[0]

        skill_embeddings = _encode(model, corpus_texts)

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