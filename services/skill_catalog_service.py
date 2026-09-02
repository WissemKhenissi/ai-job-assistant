from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass


from database.db import SessionLocal
from database.models import SkillCatalogDB


# ============================================================
# MODELE DE DONNEES
# ============================================================

@dataclass(frozen=True)
class CatalogSkill:
    """
    Représentation applicative d'une compétence du référentiel.

    Le catalogue reste volontairement indépendant du moteur
    sémantique afin de pouvoir être utilisé :

    - par l'extraction lexicale ;
    - par le matching sémantique ;
    - par le matching CV / annonce ;
    - par la mémoire marché ;
    - par la future détection de compétences inconnues.
    """

    id: str
    canonical_name: str
    category: str
    subcategory: str
    description: str
    aliases: tuple[str, ...]
    parent_skill_id: str | None
    related_skills: tuple[str, ...]


# ============================================================
# NORMALISATION
# ============================================================

def normalize_skill_text(value: str) -> str:
    """
    Normalisation commune au moteur de compétences.

    Objectifs :

    - supprimer les accents ;
    - passer en minuscules ;
    - homogénéiser les séparateurs ;
    - conserver + et # pour C++ / C# ;
    - supprimer les caractères parasites ;
    - supprimer les espaces multiples.

    Exemple :

        "Gestion des Parties-Prenantes"
        ->
        "gestion des parties prenantes"
    """

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


# ============================================================
# PARSING JSON
# ============================================================

def _parse_json_list(
    value: str | None,
) -> tuple[str, ...]:
    """
    Convertit une colonne JSON en tuple Python.

    Le système reste compatible avec les anciennes données
    si la colonne contient exceptionnellement une valeur
    non JSON.
    """

    if not value:
        return ()

    try:

        parsed = json.loads(value)

        if isinstance(parsed, list):

            return tuple(
                str(item).strip()
                for item in parsed
                if str(item).strip()
            )

    except (
        json.JSONDecodeError,
        TypeError,
    ):
        pass

    # Compatibilité avec une ancienne valeur texte simple.
    value = str(value).strip()

    if value:
        return (value,)

    return ()


# ============================================================
# CONVERSION DB -> OBJET APPLICATIF
# ============================================================

def _to_catalog_skill(
    skill: SkillCatalogDB,
) -> CatalogSkill:

    return CatalogSkill(
        id=skill.id,
        canonical_name=skill.canonical_name,
        category=skill.category or "",
        subcategory=skill.subcategory or "",
        description=skill.description or "",
        aliases=_parse_json_list(
            skill.aliases
        ),
        parent_skill_id=skill.parent_skill_id,
        related_skills=_parse_json_list(
            skill.related_skills
        ),
    )


# ============================================================
# CHARGEMENT DU CATALOGUE
# ============================================================

def get_active_skills() -> list[CatalogSkill]:
    """
    Retourne toutes les compétences actives du référentiel.

    Le catalogue est la source de vérité du moteur.
    """

    db = SessionLocal()

    try:

        rows = (
            db.query(SkillCatalogDB)
            .filter(
                SkillCatalogDB.is_active.is_(True)
            )
            .order_by(
                SkillCatalogDB.canonical_name
            )
            .all()
        )

        return [
            _to_catalog_skill(row)
            for row in rows
        ]

    finally:

        db.close()


# ============================================================
# RECHERCHE PAR ID
# ============================================================

def get_skill_by_id(
    skill_id: str,
) -> CatalogSkill | None:

    if not skill_id:
        return None

    db = SessionLocal()

    try:

        row = (
            db.query(SkillCatalogDB)
            .filter(
                SkillCatalogDB.id == skill_id,
                SkillCatalogDB.is_active.is_(True),
            )
            .first()
        )

        if row is None:
            return None

        return _to_catalog_skill(row)

    finally:

        db.close()


# ============================================================
# RECHERCHE PAR NOM / ALIAS
# ============================================================

def find_skill_by_name(
    name: str,
) -> CatalogSkill | None:
    """
    Recherche une compétence à partir :

    - du nom canonique ;
    - d'un alias.

    La comparaison est normalisée.

    Exemple :

        "SQL"
        "sql"
        "Langage SQL"

    peuvent retourner la même compétence.
    """

    normalized_name = normalize_skill_text(
        name
    )

    if not normalized_name:
        return None

    skills = get_active_skills()

    for skill in skills:

        candidates = (
            skill.canonical_name,
            *skill.aliases,
        )

        for candidate in candidates:

            if (
                normalize_skill_text(candidate)
                == normalized_name
            ):
                return skill

    return None


# ============================================================
# REPRESENTATION SEMANTIQUE
# ============================================================

def build_skill_search_text(
    skill: CatalogSkill,
) -> str:
    """
    Construit la représentation complète d'une compétence.

    Cette représentation est destinée notamment :

    - au moteur de recherche ;
    - au matching sémantique ;
    - à l'indexation vectorielle.

    Elle rassemble :

    - nom canonique ;
    - alias ;
    - catégorie ;
    - sous-catégorie ;
    - description ;
    - compétences liées.
    """

    parts: list[str] = []

    # --------------------------------------------------------
    # NOM CANONIQUE
    # --------------------------------------------------------

    if skill.canonical_name:
        parts.append(
            skill.canonical_name
        )

    # --------------------------------------------------------
    # ALIAS
    # --------------------------------------------------------

    parts.extend(
        alias
        for alias in skill.aliases
        if alias
    )

    # --------------------------------------------------------
    # CATEGORISATION
    # --------------------------------------------------------

    if skill.category:
        parts.append(
            skill.category
        )

    if skill.subcategory:
        parts.append(
            skill.subcategory
        )

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    if skill.description:
        parts.append(
            skill.description
        )

    # --------------------------------------------------------
    # COMPETENCES LIEES
    # --------------------------------------------------------

    parts.extend(
        related
        for related in skill.related_skills
        if related
    )

    return " ".join(
        part.strip()
        for part in parts
        if part and part.strip()
    )


# ============================================================
# REPRESENTATIONS SEMANTIQUES SPECIALISEES
# ============================================================

def build_skill_semantic_texts(
    skill: CatalogSkill,
) -> dict[str, str]:
    """
    Construit plusieurs représentations d'une compétence.

    Pourquoi plusieurs représentations ?

    Une compétence peut être exprimée de différentes façons
    dans une annonce.

    Exemple :

        Stakeholder Management

    peut apparaître comme :

        "gestion des parties prenantes"

        "coordination des équipes métiers"

        "communication avec les parties prenantes"

        "alignement des acteurs internes et externes"

    Une seule représentation textuelle peut donc être trop
    restrictive.

    Cette fonction prépare le moteur à comparer plusieurs
    dimensions de la compétence.
    """

    canonical_text = (
        skill.canonical_name
        or ""
    )

    alias_text = " ".join(
        skill.aliases
    )

    taxonomy_text = " ".join(
        part
        for part in (
            skill.category,
            skill.subcategory,
        )
        if part
    )

    description_text = (
        skill.description
        or ""
    )

    related_text = " ".join(
        skill.related_skills
    )

    return {
        "canonical": canonical_text.strip(),
        "aliases": alias_text.strip(),
        "taxonomy": taxonomy_text.strip(),
        "description": description_text.strip(),
        "related": related_text.strip(),
        "full": build_skill_search_text(
            skill
        ),
    }


def build_skill_semantic_text(
    skill: CatalogSkill,
) -> str:
    """
    Construit une représentation sémantique optimisée.

    Cette fonction est volontairement distincte de
    build_skill_search_text().

    build_skill_search_text()
        -> représentation générale du catalogue.

    build_skill_semantic_text()
        -> représentation destinée au modèle d'embeddings.

    L'objectif est de donner davantage de contexte au modèle
    tout en conservant une structure stable.
    """

    texts = build_skill_semantic_texts(
        skill
    )

    sections: list[str] = []

    if texts["canonical"]:
        sections.append(
            f"Compétence : {texts['canonical']}"
        )

    if texts["aliases"]:
        sections.append(
            f"Synonymes et formulations : "
            f"{texts['aliases']}"
        )

    if texts["taxonomy"]:
        sections.append(
            f"Catégorie : "
            f"{texts['taxonomy']}"
        )

    if texts["description"]:
        sections.append(
            f"Description : "
            f"{texts['description']}"
        )

    if texts["related"]:
        sections.append(
            f"Compétences associées : "
            f"{texts['related']}"
        )

    return "\n".join(
        sections
    )


# ============================================================
# CATALOGUE POUR RECHERCHE
# ============================================================

def get_skill_catalog_for_search() -> list[dict]:
    """
    Retourne le catalogue dans une structure directement
    exploitable par les moteurs de recherche et de matching.
    """

    skills = get_active_skills()

    results: list[dict] = []

    for skill in skills:

        semantic_texts = (
            build_skill_semantic_texts(
                skill
            )
        )

        results.append(
            {
                "id": skill.id,
                "canonical_name": (
                    skill.canonical_name
                ),
                "category": skill.category,
                "subcategory": skill.subcategory,
                "aliases": list(
                    skill.aliases
                ),
                "description": (
                    skill.description
                ),
                "parent_skill_id": (
                    skill.parent_skill_id
                ),
                "related_skills": list(
                    skill.related_skills
                ),
                "search_text": (
                    semantic_texts["full"]
                ),
                "semantic_text": (
                    build_skill_semantic_text(
                        skill
                    )
                ),
                "semantic_texts": (
                    semantic_texts
                ),
            }
        )

    return results


# ============================================================
# RECHERCHE MULTI-REPRESENTATIONS
# ============================================================

def get_skill_semantic_corpus() -> list[dict]:
    """
    Retourne le corpus destiné au moteur sémantique.

    Chaque compétence possède plusieurs textes.

    Exemple :

        {
            "skill": CatalogSkill(...),
            "texts": {
                "canonical": "...",
                "aliases": "...",
                "taxonomy": "...",
                "description": "...",
                "related": "...",
                "full": "..."
            }
        }

    Cette structure permettra au moteur sémantique de calculer
    plusieurs similarités et de les fusionner.
    """

    skills = get_active_skills()

    return [
        {
            "skill": skill,
            "texts": build_skill_semantic_texts(
                skill
            ),
        }
        for skill in skills
    ]