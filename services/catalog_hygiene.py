"""
Repérage des reconnaissances douteuses du référentiel.

Le référentiel apprend déjà des termes qu'il ne connaît pas : chaque
mot inconnu d'une annonce est enregistré et soumis à l'utilisateur
(``services.skill_candidate_service``). Il manquait le symétrique —
les termes qu'il croit connaître, et qu'il reconnaît de travers.

Après l'import d'ESCO, un alias attribué à une compétence d'un tout
autre domaine capture le mot partout ailleurs. Relevé sur les treize
annonces du corpus :

    « CMS »         -> technologie de montage en surface
    « FNAC »        -> aspiration à l'aiguille fine
    « transformer » -> panneaux de sécurité
    « pole »        -> éléments d'échafaudages

Ces reconnaissances entrent dans l'analyse comme des exigences à part
entière, comptées manquantes.

Aucune règle ne peut trancher à leur place. Sur les vingt-neuf
reconnaissances de ce type dans le corpus, la majorité est correcte
— « IA » pour Artificial Intelligence, « SEO » pour l'optimisation
des moteurs de recherche, « Figma » pour un logiciel d'édition
graphique. Un filtre automatique détruirait autant qu'il corrigerait.

Ce module ne décide donc rien : il montre. Il retient les
reconnaissances dont l'alias ne partage aucun mot avec le nom de la
compétence — le signe qu'un raccourci a été pris quelque part — et
laisse l'utilisateur confirmer ou retirer, comme pour le reste du
référentiel.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from database.db import SessionLocal
from database.models import SkillCatalogDB
from models.job import JobOfferDB

from services.job_requirements_service import (
    extract_required_skills_detailed,
)
from services.skill_catalog_service import (
    invalidate_caches,
    normalize_skill_text,
)


@dataclass
class ReconnaissanceDouteuse:
    """Un alias qui a reconnu une compétence, sans lui ressembler."""

    skill_id: str
    canonical_name: str
    alias: str

    # Titres des annonces où la reconnaissance s'est produite : c'est
    # ce qui permet à l'utilisateur de juger sur pièces.
    offres: list[str] = field(default_factory=list)

    @property
    def vient_d_un_import(self) -> bool:
        return str(self.skill_id).startswith("esco-")


def _mots(texte: str) -> set[str]:
    return set(normalize_skill_text(texte).split())


def detections_douteuses() -> list[ReconnaissanceDouteuse]:
    """
    Les reconnaissances suspectes dans les annonces déjà analysées.

    On ne balaie pas le référentiel — 108 000 alias, dont l'immense
    majorité ne servira jamais. On regarde ce qui s'est réellement
    produit sur les annonces de l'utilisateur : une reconnaissance
    qui n'a jamais eu lieu ne fausse aucun score.

    Le critère est volontairement grossier — aucun mot commun entre
    l'alias et le nom de la compétence — parce qu'il ne conclut rien.
    Il ne fait que réduire une liste de plusieurs centaines à une
    trentaine de cas qu'un humain lit en deux minutes.
    """

    db = SessionLocal()

    try:
        offres = [
            (offre.title or "", offre.description or "")
            for offre in db.query(JobOfferDB).all()
        ]

    finally:
        db.close()

    douteuses: dict[tuple[str, str], ReconnaissanceDouteuse] = {}

    for titre, description in offres:

        for detail in extract_required_skills_detailed(
            f"{titre}\n{description}"
        ):

            alias = detail["matched_alias"]
            nom = detail["canonical_name"]

            if _mots(alias) & _mots(nom):
                continue

            cle = (detail["skill_id"], normalize_skill_text(alias))

            douteuse = douteuses.get(cle)

            if douteuse is None:

                douteuse = ReconnaissanceDouteuse(
                    skill_id=detail["skill_id"],
                    canonical_name=nom,
                    alias=alias,
                )

                douteuses[cle] = douteuse

            if titre and titre not in douteuse.offres:
                douteuse.offres.append(titre)

    return sorted(
        douteuses.values(),
        key=lambda item: (-len(item.offres), item.alias.casefold()),
    )


def remove_alias(skill_id: str, alias: str) -> bool:
    """
    Retire un alias d'une compétence du référentiel.

    Le nom canonique n'est jamais retirable : une compétence que plus
    rien ne nomme deviendrait indétectable, et l'utilisateur ne
    verrait qu'une exigence disparue sans explication. Pour écarter
    une compétence entière, c'est ``is_active`` qui existe.

    Retourne True si un alias a effectivement été retiré.
    """

    forme = normalize_skill_text(alias)

    if not forme:
        return False

    db = SessionLocal()

    try:

        competence = db.get(SkillCatalogDB, skill_id)

        if competence is None:
            return False

        if forme == normalize_skill_text(competence.canonical_name):
            raise ValueError(
                "Le nom canonique d'une compétence ne peut pas être "
                "retiré : elle deviendrait introuvable. Désactivez "
                "la compétence si elle n'a pas sa place."
            )

        try:
            alias_actuels = json.loads(competence.aliases or "[]")

        except (TypeError, ValueError):
            return False

        if not isinstance(alias_actuels, list):
            return False

        restants = [
            item
            for item in alias_actuels
            if normalize_skill_text(str(item)) != forme
        ]

        if len(restants) == len(alias_actuels):
            return False

        competence.aliases = json.dumps(restants, ensure_ascii=False)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    invalidate_caches()

    return True
