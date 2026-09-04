"""
Apprentissage du référentiel à partir des annonces analysées.

Le référentiel pilote tout : le matching, le vocabulaire autorisé à la
rédaction, le tri des exigences. Livré figé, il ne vaut que pour les
métiers que son auteur a prévus — aujourd'hui produit, data et
e-commerce. Un développeur, une infirmière ou un juriste n'y
trouveraient rien, et l'outil ne fonctionnerait pas pour eux.

Ce module ferme la boucle. Chaque terme d'annonce que le référentiel
ne reconnaît pas est enregistré, compté, et présenté à l'utilisateur
qui décide : en faire une compétence, la rattacher comme alias d'une
compétence existante, ou l'ignorer. Le référentiel se remplit alors
par l'usage, quel que soit le métier visé.

Rien n'est décidé automatiquement. Créer une compétence, c'est
affirmer qu'un terme en désigne une — c'est exactement le genre
d'affirmation que ce projet ne laisse pas à la machine.
"""

from __future__ import annotations

import json
from uuid import uuid4

from database.db import SessionLocal
from database.models import SkillCandidateDB, SkillCatalogDB
from services.skill_catalog_service import (
    find_skill_by_name,
    normalize_skill_text,
)


# Statuts possibles d'un terme rencontré.
NOUVEAU = "nouveau"
INTEGRE = "integre"      # promu en compétence du référentiel
RATTACHE = "rattache"    # ajouté comme alias d'une compétence
IGNORE = "ignore"        # jugé sans valeur par l'utilisateur

# Un terme traité ne doit plus revenir dans la liste à trier.
STATUTS_TRAITES = frozenset({INTEGRE, RATTACHE, IGNORE})

# Au-delà, la liste des annonces d'exemple n'apprend plus rien.
MAX_EXEMPLES = 10


def _invalider_cache_alias() -> None:
    """
    L'index « alias -> nom canonique » est construit une fois par
    processus (services.matching.normalization).

    Sans cette remise à zéro, une compétence tout juste créée resterait
    invisible du moteur jusqu'au prochain démarrage — et l'utilisateur
    croirait que son ajout n'a rien changé.
    """

    import services.matching.normalization as normalization

    normalization._canonical_alias_index_cache = None


def record_unknown_terms(
    terms: list[str] | tuple[str, ...],
    job_offer_id: str = "",
    was_counted: bool = True,
) -> list[str]:
    """
    Enregistre les termes qu'aucune compétence du référentiel ne
    reconnaît, et retourne ceux qui viennent d'être vus.

    Un terme déjà traité par l'utilisateur (intégré, rattaché ou
    ignoré) voit son compteur augmenter sans revenir dans la liste à
    trier : sa décision tient.
    """

    db = SessionLocal()

    vus: list[str] = []

    try:

        for brut in terms:

            terme = (brut or "").strip()

            if not terme:
                continue

            if find_skill_by_name(terme) is not None:
                continue

            cle = normalize_skill_text(terme)

            if not cle:
                continue

            existant = (
                db.query(SkillCandidateDB)
                .filter(SkillCandidateDB.canonical_key == cle)
                .one_or_none()
            )

            if existant is None:

                exemples = [job_offer_id] if job_offer_id else []

                db.add(
                    SkillCandidateDB(
                        id=f"skill-candidate-{uuid4()}",
                        term=terme,
                        canonical_key=cle,
                        occurrences=1,
                        was_counted=was_counted,
                        status=NOUVEAU,
                        job_offer_ids=exemples,
                    )
                )

                vus.append(terme)

            else:

                existant.occurrences += 1

                if (
                    job_offer_id
                    and job_offer_id not in (existant.job_offer_ids or [])
                    and len(existant.job_offer_ids or []) < MAX_EXEMPLES
                ):
                    existant.job_offer_ids = [
                        *(existant.job_offer_ids or []),
                        job_offer_id,
                    ]

                # Un terme d'abord écarté puis compté mérite d'être
                # présenté comme compté : c'est le cas le plus utile.
                if was_counted:
                    existant.was_counted = True

        db.commit()

        return vus

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def get_candidates(
    only_pending: bool = True,
) -> list[dict]:
    """
    Termes rencontrés, du plus fréquent au plus rare, en primitives.
    """

    db = SessionLocal()

    try:

        requete = db.query(SkillCandidateDB)

        if only_pending:
            requete = requete.filter(
                SkillCandidateDB.status == NOUVEAU
            )

        lignes = requete.order_by(
            SkillCandidateDB.occurrences.desc(),
            SkillCandidateDB.term,
        ).all()

        # Nom de la compétence visée, pour que l'utilisateur voie ce
        # qu'il a décidé sans avoir à s'en souvenir.
        noms = {
            competence.id: competence.canonical_name
            for competence in db.query(SkillCatalogDB).all()
        }

        return [
            {
                "id": ligne.id,
                "term": ligne.term,
                "occurrences": ligne.occurrences,
                "was_counted": ligne.was_counted,
                "status": ligne.status,
                "resolved_skill_id": ligne.resolved_skill_id or "",
                "resolved_skill_name": noms.get(
                    ligne.resolved_skill_id or "", ""
                ),
                "job_offer_ids": list(ligne.job_offer_ids or []),
            }
            for ligne in lignes
        ]

    finally:
        db.close()


def undo_decision(candidate_id: str) -> str:
    """
    Défait une décision et remet le terme dans la liste à trier.

    Une décision de vocabulaire se prend sur un terme sorti de son
    contexte : se tromper est facile, et sans marche arrière l'erreur
    devient définitive — un alias posé sur la mauvaise compétence
    rattacherait durablement une compétence du Master CV à la mauvaise
    entrée du référentiel.

    Retourne une phrase décrivant ce qui a été défait.
    """

    db = SessionLocal()

    message = ""

    try:

        ligne = db.get(SkillCandidateDB, candidate_id)

        if ligne is None:
            raise ValueError(f"Terme introuvable : {candidate_id}")

        if ligne.status == NOUVEAU:
            raise ValueError(
                f"« {ligne.term} » n'a encore fait l'objet d'aucune "
                "décision."
            )

        terme = ligne.term

        # ----------------------------------------------------
        # RATTACHEMENT : retirer l'alias posé
        # ----------------------------------------------------

        if ligne.status == RATTACHE and ligne.resolved_skill_id:

            competence = db.get(
                SkillCatalogDB, ligne.resolved_skill_id
            )

            if competence is not None:

                cle_terme = normalize_skill_text(ligne.term)

                # Le nom canonique n'est jamais retiré : il ne vient
                # pas de ce rattachement et l'entrée en dépend.
                cle_canonique = normalize_skill_text(
                    competence.canonical_name
                )

                conserves = [
                    alias
                    for alias in _charger_alias(competence)
                    if normalize_skill_text(alias) != cle_terme
                    or normalize_skill_text(alias) == cle_canonique
                ]

                competence.aliases = json.dumps(
                    conserves, ensure_ascii=False
                )

                message = (
                    f"« {ligne.term} » n'est plus un alias de "
                    f"« {competence.canonical_name} »."
                )

        # ----------------------------------------------------
        # CREATION : supprimer la compétence créée
        # ----------------------------------------------------
        #
        # Rien ne pointe vers skill_catalog par clé étrangère : les
        # analyses conservent des libellés, pas des identifiants. La
        # suppression ne casse donc aucune donnée existante, elle
        # change seulement la résolution à venir.

        elif ligne.status == INTEGRE and ligne.resolved_skill_id:

            competence = db.get(
                SkillCatalogDB, ligne.resolved_skill_id
            )

            if competence is not None:

                message = (
                    f"La compétence « {competence.canonical_name} » "
                    "a été retirée du référentiel."
                )

                db.delete(competence)

        elif ligne.status == IGNORE:
            message = f"« {ligne.term} » revient dans la liste à trier."

        ligne.status = NOUVEAU
        ligne.resolved_skill_id = None

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    _invalider_cache_alias()

    return message or f"« {terme} » remis à trier."


def ignore_candidate(candidate_id: str) -> None:
    """L'utilisateur juge que ce terme ne désigne pas une compétence."""

    db = SessionLocal()

    try:
        ligne = db.get(SkillCandidateDB, candidate_id)

        if ligne is None:
            raise ValueError(f"Terme introuvable : {candidate_id}")

        ligne.status = IGNORE
        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def attach_as_alias(candidate_id: str, catalog_skill_id: str) -> None:
    """
    Rattache le terme à une compétence existante du référentiel.

    C'est le cas le plus fréquent : l'annonce nomme autrement une
    compétence déjà connue.
    """

    db = SessionLocal()

    try:

        ligne = db.get(SkillCandidateDB, candidate_id)

        if ligne is None:
            raise ValueError(f"Terme introuvable : {candidate_id}")

        competence = db.get(SkillCatalogDB, catalog_skill_id)

        if competence is None:
            raise ValueError(
                f"Compétence introuvable : {catalog_skill_id}"
            )

        alias = _charger_alias(competence)

        deja = {normalize_skill_text(item) for item in alias}

        if normalize_skill_text(ligne.term) not in deja:
            alias.append(ligne.term)

        competence.aliases = json.dumps(alias, ensure_ascii=False)

        ligne.status = RATTACHE
        ligne.resolved_skill_id = catalog_skill_id

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    _invalider_cache_alias()


def promote_to_catalog(
    candidate_id: str,
    canonical_name: str = "",
    category: str = "",
    description: str = "",
) -> str:
    """
    Crée une compétence du référentiel à partir du terme rencontré.

    Retourne l'identifiant de la compétence créée.
    """

    db = SessionLocal()

    try:

        ligne = db.get(SkillCandidateDB, candidate_id)

        if ligne is None:
            raise ValueError(f"Terme introuvable : {candidate_id}")

        nom = (canonical_name or ligne.term).strip()

        if not nom:
            raise ValueError("Le nom de la compétence est obligatoire.")

        cle = normalize_skill_text(nom)

        collision = _competence_revendiquant(db, cle)

        if collision is not None:
            raise ValueError(
                f"« {nom} » est déjà connu du référentiel sous "
                f"« {collision} »."
            )

        alias = [nom]

        if normalize_skill_text(ligne.term) != cle:
            alias.append(ligne.term)

        identifiant = f"catalog-{uuid4()}"

        db.add(
            SkillCatalogDB(
                id=identifiant,
                canonical_name=nom,
                category=category,
                subcategory="",
                description=description,
                aliases=json.dumps(alias, ensure_ascii=False),
                parent_skill_id=None,
                related_skills=json.dumps([], ensure_ascii=False),
                is_active=True,
            )
        )

        ligne.status = INTEGRE
        ligne.resolved_skill_id = identifiant

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    _invalider_cache_alias()

    return identifiant


# ============================================================
# OUTILS INTERNES
# ============================================================

def _charger_alias(competence: SkillCatalogDB) -> list[str]:

    try:
        valeur = json.loads(competence.aliases or "[]")

    except (TypeError, ValueError):
        return [competence.canonical_name]

    return [item for item in valeur if isinstance(item, str)]


def _competence_revendiquant(db, cle: str) -> str | None:
    """
    Compétence du référentiel qui revendique déjà cette forme.

    Un alias appartient à une seule compétence : sans ce contrôle,
    créer un doublon rattacherait silencieusement une compétence du
    Master CV à la mauvaise entrée.
    """

    for competence in db.query(SkillCatalogDB).all():

        for nom in (
            competence.canonical_name,
            *_charger_alias(competence),
        ):
            if normalize_skill_text(nom) == cle:
                return competence.canonical_name

    return None
