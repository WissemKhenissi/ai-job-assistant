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
# DETECTION D'UNE COMPETENCE
# ============================================================

def _find_skill_position(
    text: str,
    skill: SkillCatalogDB,
) -> int | None:
    """
    Retourne la position de la première occurrence
    d'une compétence ou d'un de ses alias.

    None = compétence absente.
    """

    normalized_text = _normalize(text)

    candidates = [
        skill.canonical_name,
        *_parse_aliases(skill),
    ]

    positions: list[int] = []

    for candidate in candidates:

        normalized_candidate = _normalize(
            candidate
        )

        if not normalized_candidate:
            continue

        pattern = (
            rf"(?<![a-z0-9])"
            rf"{re.escape(normalized_candidate)}"
            rf"(?![a-z0-9])"
        )

        match = re.search(
            pattern,
            normalized_text,
            flags=re.IGNORECASE,
        )

        if match:
            positions.append(
                match.start()
            )

    if not positions:
        return None

    return min(positions)


# ============================================================
# EXTRACTION
# ============================================================

def extract_required_skills(
    job_description: str,
) -> list[str]:
    """
    Extrait les compétences détectées dans une annonce.

    Le référentiel est entièrement piloté par la table
    `skill_catalog`.

    Aucune compétence n'est codée en dur ici.

    Retourne les noms canoniques des compétences.
    """

    if not job_description:
        return []

    catalog = _load_skill_catalog()

    detected_skills: list[
        tuple[int, str]
    ] = []

    for skill in catalog:

        position = _find_skill_position(
            job_description,
            skill,
        )

        if position is None:
            continue

        detected_skills.append(
            (
                position,
                skill.canonical_name,
            )
        )

    # --------------------------------------------------------
    # TRI PAR ORDRE D'APPARITION
    # --------------------------------------------------------

    detected_skills.sort(
        key=lambda item: (
            item[0],
            item[1].casefold(),
        )
    )

    # --------------------------------------------------------
    # DEDUPLICATION
    # --------------------------------------------------------

    result: list[str] = []
    seen: set[str] = set()

    for _, skill_name in detected_skills:

        normalized_skill = _normalize(
            skill_name
        )

        if normalized_skill in seen:
            continue

        seen.add(
            normalized_skill
        )

        result.append(
            skill_name
        )

    return result


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

    Cette fonction permet de conserver l'information
    expliquant pourquoi une compétence a été détectée.
    """

    if not job_description:
        return []

    catalog = _load_skill_catalog()

    normalized_text = _normalize(
        job_description
    )

    detected: list[dict] = []

    for skill in catalog:

        candidates = [
            skill.canonical_name,
            *_parse_aliases(skill),
        ]

        matches: list[
            tuple[int, str]
        ] = []

        for candidate in candidates:

            normalized_candidate = _normalize(
                candidate
            )

            if not normalized_candidate:
                continue

            pattern = (
                rf"(?<![a-z0-9])"
                rf"{re.escape(normalized_candidate)}"
                rf"(?![a-z0-9])"
            )

            match = re.search(
                pattern,
                normalized_text,
                flags=re.IGNORECASE,
            )

            if match:

                matches.append(
                    (
                        match.start(),
                        candidate,
                    )
                )

        if not matches:
            continue

        position, matched_alias = min(
            matches,
            key=lambda item: item[0],
        )

        detected.append(
            {
                "canonical_name": skill.canonical_name,
                "category": skill.category,
                "subcategory": skill.subcategory,
                "matched_alias": matched_alias,
                "position": position,
                "skill_id": skill.id,
            }
        )

    # --------------------------------------------------------
    # TRI
    # --------------------------------------------------------

    detected.sort(
        key=lambda item: (
            item["position"],
            item["canonical_name"].casefold(),
        )
    )

    # --------------------------------------------------------
    # DEDUPLICATION
    # --------------------------------------------------------

    result: list[dict] = []
    seen: set[str] = set()

    for item in detected:

        key = _normalize(
            item["canonical_name"]
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result

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
