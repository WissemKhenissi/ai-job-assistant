from __future__ import annotations

import json
import re
import unicodedata

from database.db import SessionLocal
from database.models import SkillCatalogDB


# ============================================================
# NORMALISATION
# ============================================================

def _normalize(value: str) -> str:
    """
    Normalise un texte pour faciliter la détection :

    - suppression des accents
    - minuscules
    - normalisation des tirets
    - conservation de + et #
      pour des technologies comme C++ / C#
    - suppression des caractères parasites
    - espaces multiples supprimés
    """

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


# ============================================================
# RECHERCHE DE TERMES
# ============================================================

def _contains_term(
    text: str,
    term: str,
) -> bool:
    """
    Vérifie qu'un terme apparaît réellement dans le texte.

    Important pour les termes courts :

        UI  -> détecte "UI"
        AI  -> détecte "AI"
        R   -> détecte "R"

    mais :

        UI  -> ne détecte pas "fruit"
        R   -> ne détecte pas "marketing"
    """

    normalized_text = _normalize(text)
    normalized_term = _normalize(term)

    if not normalized_term:
        return False

    # Termes courts : frontière stricte.
    if len(normalized_term) <= 2:

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

    # Termes normaux : frontière de mot.
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
# CATALOGUE
# ============================================================

def _load_skill_catalog() -> list[SkillCatalogDB]:
    """
    Charge toutes les compétences actives du référentiel.
    """

    db = SessionLocal()

    try:

        skills = (
            db.query(SkillCatalogDB)
            .filter(
                SkillCatalogDB.is_active.is_(True)
            )
            .order_by(
                SkillCatalogDB.canonical_name
            )
            .all()
        )

        return skills

    finally:

        db.close()


def _parse_aliases(
    skill: SkillCatalogDB,
) -> list[str]:
    """
    Transforme le JSON des alias stocké en base
    en liste Python.

    Le système reste robuste si une ancienne ligne
    contient une simple chaîne.
    """

    if not skill.aliases:
        return []

    try:

        aliases = json.loads(
            skill.aliases
        )

        if isinstance(aliases, list):

            return [
                str(alias)
                for alias in aliases
                if alias
            ]

    except (
        json.JSONDecodeError,
        TypeError,
    ):
        pass

    return [
        skill.aliases
    ]


# ============================================================
# DETECTION DES COMPETENCES DANS UNE ANNONCE
# ============================================================
#
# L'ancienne approche lançait une recherche par expression régulière
# dans le texte **pour chaque alias du référentiel** : le coût
# dépendait de la taille du catalogue, pas de celle de l'annonce.
# Mesuré à 46 entrées : 23 ms. Extrapolé à un référentiel de 14 000
# compétences (l'ordre de grandeur d'une taxonomie publique) : près de
# sept secondes par annonce.
#
# On fait désormais l'inverse : découper l'annonce une fois, puis
# chercher chaque groupe de mots dans un index construit une seule
# fois par processus. Le coût suit la longueur de l'annonce et cesse
# de suivre celle du référentiel.
#
# La sémantique est identique : les deux méthodes reconnaissent un
# alias exactement aux frontières de mots, sur le même texte
# normalisé.

# Un mot, au sens de la détection. La normalisation conserve « . »,
# « + » et « # » pour des noms comme node.js, C++ ou C# ; mais un
# point de fin de phrase doit rester une frontière, sans quoi
# « SQL. » cesserait d'être reconnu. Le point sépare donc, et
# « node.js » se retrouve indexé comme les deux mots « node js » —
# des deux côtés de la comparaison, donc sans perte.
_MOT = re.compile(r"[a-z0-9+#]+")


def _mots(texte_normalise: str) -> list[str]:
    return _MOT.findall(texte_normalise)


_index_extraction_cache: tuple[dict, int] | None = None


def _index_extraction() -> tuple[dict, int]:
    """
    Index « forme normalisée -> (compétence, alias) », et longueur du
    plus long alias en nombre de mots.
    """

    global _index_extraction_cache

    if _index_extraction_cache is None:

        index: dict[str, tuple] = {}

        taille_max = 1

        for skill in _load_skill_catalog():

            for alias in (
                skill.canonical_name,
                *_parse_aliases(skill),
            ):

                mots = _mots(_normalize(alias))

                if not mots:
                    continue

                taille_max = max(taille_max, len(mots))

                index.setdefault(" ".join(mots), (skill, alias))

        _index_extraction_cache = (index, taille_max)

    return _index_extraction_cache


def _detecter(job_description: str) -> list[tuple]:
    """
    Compétences reconnues dans l'annonce.

    Retourne (position, compétence, alias reconnu) par compétence, à
    sa première occurrence, dans l'ordre d'apparition.
    """

    index, taille_max = _index_extraction()

    texte = _normalize(job_description)

    if not texte:
        return []

    # Les mots et leur position dans le texte normalisé, en une seule
    # passe : la position restitue l'ordre d'apparition, qui porte une
    # information — ce que l'annonce cite en premier compte davantage.
    reperes = list(_MOT.finditer(texte))

    mots = [repere.group() for repere in reperes]
    positions = [repere.start() for repere in reperes]

    trouvees: dict[str, tuple] = {}

    for depart in range(len(mots)):

        limite = min(taille_max, len(mots) - depart)

        for longueur in range(1, limite + 1):

            entree = index.get(
                " ".join(mots[depart : depart + longueur])
            )

            if entree is None:
                continue

            skill, alias = entree

            # Première occurrence seulement : le balayage va de la
            # gauche vers la droite.
            trouvees.setdefault(
                skill.id, (positions[depart], skill, alias)
            )

    return sorted(
        trouvees.values(),
        key=lambda item: (
            item[0],
            item[1].canonical_name.casefold(),
        ),
    )


def extract_required_skills(
    job_description: str,
) -> list[str]:
    """
    Extrait les compétences détectées dans une annonce.

    Le référentiel est entièrement piloté par la table
    `skill_catalog`. Aucune compétence n'est codée en dur ici.

    Retourne les noms canoniques des compétences, dans l'ordre
    d'apparition dans l'annonce.
    """

    if not job_description:
        return []

    return [
        skill.canonical_name
        for _position, skill, _alias in _detecter(job_description)
    ]


# ============================================================
# VERSION DETAILLEE
# ============================================================

def extract_required_skills_detailed(
    job_description: str,
) -> list[dict]:
    """
    Version détaillée de l'extraction.

    Utile pour le moteur de matching et pour l'interface.

    Exemple :

    {
        "canonical_name": "Python",
        "category": "Technology",
        "matched_alias": "Programmation Python",
        "position": 120
    }

    Cette fonction permet de conserver l'information expliquant
    pourquoi une compétence a été détectée.
    """

    if not job_description:
        return []

    return [
        {
            "canonical_name": skill.canonical_name,
            "category": skill.category,
            "subcategory": skill.subcategory,
            "matched_alias": alias,
            "position": position,
            "skill_id": skill.id,
        }
        for position, skill, alias in _detecter(job_description)
    ]


# ============================================================
# ANNEES D'EXPERIENCE DEMANDEES
# ============================================================

# "3 ans", "5 années", "3+ ans", "au moins 4 ans", "3 à 5 ans"...
_MOTIF_ANNEES = re.compile(
    r"(\d{1,2})\s*(?:\+|ans?\b|ann[ée]es?\b)",
    flags=re.IGNORECASE,
)

# Fourchettes : "3 a 5 ans", "entre 3 et 5 ans". Le texte est
# normalise avant, donc "a" y remplace deja "à".
_MOTIF_FOURCHETTE = re.compile(
    r"(\d{1,2})\s*(?:a|et)\s+(\d{1,2})\s*(?:ans?\b|ann[ée]es?\b)",
    flags=re.IGNORECASE,
)

# L'annonce doit parler d'expérience à proximité du chiffre : sans ça,
# "3 ans" dans "contrat de 3 ans" serait pris pour une exigence.
_MOTS_EXPERIENCE = ("experience", "experiences", "anciennete", "seniorite")

# Fenêtre de recherche autour du chiffre, en caractères.
_FENETRE = 60


def extract_required_years(job_description: str) -> int | None:
    """
    Nombre d'années d'expérience demandées par l'annonce, ou None.

    Purement déterministe (aucune IA) : cette information sert à
    comparer avec l'ancienneté réelle du candidat, il vaut donc mieux
    ne rien annoncer que d'annoncer un chiffre inventé.

    En cas de fourchette ("3 à 5 ans"), le minimum est retenu : c'est
    le seuil d'entrée, donc le seul qui permette de dire si le profil
    passe le filtre.
    """

    if not job_description:
        return None

    normalise = _normalize(job_description)

    candidats: list[int] = []

    # Les deux motifs alimentent la meme liste : sur "de 5 a 8 ans",
    # la fourchette apporte 5 et le motif simple 8 — le min() final
    # retient bien le seuil d'entree.
    for correspondance in list(_MOTIF_FOURCHETTE.finditer(normalise)) + list(
        _MOTIF_ANNEES.finditer(normalise)
    ):

        debut = max(0, correspondance.start() - _FENETRE)
        fin = min(len(normalise), correspondance.end() + _FENETRE)

        contexte = normalise[debut:fin]

        if not any(mot in contexte for mot in _MOTS_EXPERIENCE):
            continue

        try:
            annees = int(correspondance.group(1))
        except (TypeError, ValueError):
            continue

        # Au-delà, il ne s'agit plus d'une exigence d'ancienneté
        # (année civile, effectif, montant...).
        if 1 <= annees <= 30:
            candidats.append(annees)

    if not candidats:
        return None

    return min(candidats)
