"""
Vocabulaire autorisé et interdit pour une offre donnée.

Le cahier des charges demande d'employer le vocabulaire de l'annonce
« lorsqu'il correspond réellement au parcours du candidat ». Confier ce
jugement au modèle reviendrait à lui laisser décider qu'une compétence
est acquise — précisément la décision que le projet ne lui confie
jamais.

Ce module calcule donc la frontière à sa place, à partir de deux
sources déjà fiables : l'analyse de l'offre (qui dit, compétence par
compétence, si elle est prouvée) et le référentiel skill_catalog (qui
dit quels termes désignent la même compétence).

    prouvée          -> tous ses termes sont autorisés
    déclarée         -> interdits (aucune preuve au Master CV)
    déduite          -> interdits (une déduction n'est pas un fait)
    manquante        -> interdits (absente du parcours)

Le résultat sert deux fois : à cadrer le prompt de reformulation, et à
rejeter après coup une reformulation qui aurait fait apparaître un
terme interdit. Le prompt seul ne suffit pas — c'est la leçon déjà
tirée du garde-fou sur les chiffres.
"""

from __future__ import annotations

from dataclasses import dataclass

from database.db import SessionLocal
from database.models import SkillDB
from models.matching import JobMatchDB
from models.skill_match import JobSkillMatchDB

from services.matching.normalization import (
    _canonical_skill_name,
    _contains_term,
)
from services.skill_catalog_service import (
    get_active_skills,
    normalize_skill_text,
)


# Un terme trop court reconnaîtrait n'importe quoi : on les écarte,
# quitte à laisser passer un sigle de deux lettres.
MIN_TERM_LENGTH = 3


# Mots qui rehaussent un niveau sans rien prouver. Les garde-fous
# existants ne les voyaient pas : ce ne sont ni des chiffres, ni des
# noms de compétence. Un essai réel a pourtant produit « Expert en
# pilotage de projets digitaux » là où le Master CV écrit « une
# expérience de pilotage de projets digitaux ».
SENIORITY_TERMS = (
    "expert",
    "experte",
    "expertise",
    "maîtrise",
    "maîtrisant",
    "senior",
    "sénior",
    "lead",
    "leader",
    "head",
    "principal",
    "référent",
    "référente",
    "spécialiste",
    "manager",
    "directeur",
    "directrice",
    "responsable",
)


@dataclass(frozen=True)
class OfferVocabulary:
    """
    Termes que la rédaction peut employer, et ceux qu'elle ne peut pas.

    Les deux listes sont closes : tout terme absent des deux n'est pas
    un nom de compétence connu du référentiel, et le prompt demande de
    ne pas en introduire.
    """

    authorized: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.authorized and not self.forbidden


def mentions_term(text: str, term: str) -> bool:
    """
    Le texte emploie-t-il ce terme ?

    Délègue à la normalisation du moteur de matching : accents,
    casse et séparateurs ignorés, mais frontières de mots respectées
    — « SQL » ne doit pas se reconnaître dans « SQLite ».
    """

    return _contains_term(text, term)


def forbidden_terms_used(
    text: str,
    forbidden: tuple[str, ...] | list[str],
    source_text: str = "",
) -> list[str]:
    """
    Termes interdits présents dans `text` et absents de `source_text`.

    Un terme déjà présent dans le texte source n'est pas une invention
    du modèle : il vient du Master CV, et le supprimer serait censurer
    le candidat plutôt que le protéger.
    """

    return [
        terme
        for terme in forbidden
        if mentions_term(text, terme)
        and not (source_text and mentions_term(source_text, terme))
    ]


def seniority_terms_added(text: str, source_text: str) -> list[str]:
    """
    Mots de séniorité apparus à la reformulation (§26).

    Le cahier des charges l'écrit noir sur blanc : ne présente jamais
    le candidat comme senior, lead, manager ou expert parce que
    l'offre emploie ces mots. C'est une règle qu'un contrôle
    automatique applique mieux qu'une consigne — le modèle peut
    l'oublier, la comparaison de deux textes non.
    """

    return [
        terme
        for terme in SENIORITY_TERMS
        if mentions_term(text, terme)
        and not mentions_term(source_text, terme)
    ]


def _catalog_terms_by_canonical() -> dict[str, set[str]]:
    """Forme canonique -> tous les libellés que le référentiel lui connaît."""

    index: dict[str, set[str]] = {}

    for skill in get_active_skills():

        canonical = normalize_skill_text(skill.canonical_name)

        index.setdefault(canonical, set()).update(
            (skill.canonical_name, *skill.aliases)
        )

    return index


def _retenir(terme: str) -> bool:

    return len(normalize_skill_text(terme)) >= MIN_TERM_LENGTH


def build_offer_vocabulary(
    candidate_id: str,
    job_offer_id: str,
) -> OfferVocabulary:
    """
    Construit le vocabulaire autorisé et interdit pour cette offre.

    Retourne un vocabulaire vide si l'offre n'a pas été analysée : la
    reformulation reste alors cadrée par ses autres garde-fous, sans
    jamais échouer pour autant.
    """

    db = SessionLocal()

    try:

        job_match = (
            db.query(JobMatchDB)
            .filter(
                JobMatchDB.candidate_id == candidate_id,
                JobMatchDB.job_offer_id == job_offer_id,
            )
            .one_or_none()
        )

        if job_match is None:
            return OfferVocabulary()

        skill_matches = (
            db.query(JobSkillMatchDB)
            .filter(JobSkillMatchDB.job_match_id == job_match.id)
            .all()
        )

        if not skill_matches:
            return OfferVocabulary()

        par_canonique = _catalog_terms_by_canonical()

        autorises: set[str] = set()
        interdits: set[str] = set()
        canoniques_prouvees: set[str] = set()

        for row in skill_matches:

            termes = {row.skill}

            termes.update(
                par_canonique.get(row.canonical_skill, set())
            )

            termes = {
                terme.strip()
                for terme in termes
                if terme and terme.strip() and _retenir(terme)
            }

            if row.status == "proven":
                canoniques_prouvees.add(row.canonical_skill)
                autorises.update(termes)

            else:
                interdits.update(termes)

        # ----------------------------------------------------
        # LES MOTS DU CANDIDAT LUI-MEME
        # ----------------------------------------------------
        #
        # Le candidat désigne parfois une compétence prouvée avec un
        # libellé que ni l'annonce ni le référentiel n'emploient :
        # c'est son propre vocabulaire, il reste autorisé.

        for skill in (
            db.query(SkillDB)
            .filter(SkillDB.candidate_id == candidate_id)
            .all()
        ):

            if (
                _canonical_skill_name(skill.name) in canoniques_prouvees
                and _retenir(skill.name)
            ):
                autorises.add(skill.name.strip())

        # ----------------------------------------------------
        # ARBITRAGE
        # ----------------------------------------------------
        #
        # Une annonce peut demander deux fois la même compétence sous
        # deux libellés au statut différent. Le terme reste autorisé
        # dès qu'une preuve existe : c'est la preuve qui tranche, pas
        # l'ordre des lignes de l'annonce.

        formes_autorisees = {
            normalize_skill_text(terme) for terme in autorises
        }

        interdits = {
            terme
            for terme in interdits
            if normalize_skill_text(terme) not in formes_autorisees
        }

        return OfferVocabulary(
            authorized=tuple(sorted(autorises)),
            forbidden=tuple(sorted(interdits)),
        )

    finally:

        db.close()
