"""
Import du référentiel ESCO dans skill_catalog.

Le référentiel livré à la main couvrait 46 compétences, toutes issues
du secteur produit / data / e-commerce. Mesuré sur dix métiers
inventés, quatre annonces sur dix n'y trouvaient **aucune** exigence
reconnaissable : ni « HACCP » pour un chef de cuisine, ni « contentieux
prud'homal » pour une juriste. Sans socle, l'outil ne sert qu'un
métier.

ESCO est la classification européenne des compétences : 13 939
concepts, 28 langues, publiée par la Commission européenne sous
licence CC BY 4.0. Sa structure — un terme préféré, des termes non
préférés — est exactement celle de skill_catalog.

Deux fichiers sont lus, français et anglais, joints par `conceptUri` :
le français fournit le nom canonique, l'anglais apporte les synonymes
qui lui manquent (13 942 entrées avec alias contre 1 933). Une même
compétence devient ainsi reconnaissable dans les deux langues, ce qui
prépare la rédaction d'un CV dans la langue de l'annonce.

Trois règles de prudence :

- **le référentiel maison gagne** : une compétence ESCO dont le nom
  est déjà revendiqué par une entrée existante est écartée. Les 46
  entrées écrites à la main sont plus précises pour ce candidat que
  leur équivalent générique ;
- **un alias n'appartient qu'à une entrée** : en cas de collision, il
  est abandonné plutôt que déplacé, et le nombre est rapporté ;
- **les compétences transversales sont exclues par défaut** :
  « travailler en équipe » ou « faire preuve de curiosité »
  figureraient dans presque toutes les annonces et gonfleraient les
  exigences sans rien distinguer.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from database.db import SessionLocal
from database.models import SkillCatalogDB
from services.skill_catalog_service import (
    invalidate_caches,
    normalize_skill_text,
)


# Une ligne de description ESCO peut être très longue.
csv.field_size_limit(10_000_000)


# Types de concepts retenus. ESCO distingue les savoir-faire des
# connaissances ; les deux ont leur place sur un CV.
SKILL_TYPES = frozenset({"skill/competence", "knowledge"})

# Un alias d'une seule lettre reconnaîtrait n'importe quoi.
MIN_ALIAS_LENGTH = 3


# Mots qu'un alias ne peut pas être à lui seul.
#
# ESCO contient des sigles sectoriels qui, en français, s'écrivent
# comme des mots courants : « AVEC » est un alias de « gestion des
# appareils mobiles », et reconnaissait donc une exigence dans
# n'importe quelle phrase contenant la préposition. Observé sur deux
# annonces sans le moindre rapport.
#
# Un alias d'un seul mot n'est retenu que s'il ne figure ni parmi les
# mots-outils, ni parmi les termes trop généraux pour désigner une
# compétence à eux seuls.
MOTS_OUTILS = frozenset(
    {
        "avec", "sans", "pour", "dans", "sur", "sous", "par", "chez",
        "vers", "entre", "apres", "avant", "depuis", "pendant",
        "selon", "malgre", "aussi", "donc", "mais", "car", "quand",
        "comme", "tout", "tous", "toute", "toutes", "plus", "moins",
        "tres", "bien", "encore", "deja", "meme", "autre", "autres",
        "faire", "etre", "avoir", "aller", "venir", "voir", "savoir",
        "with", "without", "from", "into", "over", "under", "about",
        "after", "before", "during", "through", "between", "also",
        "then", "than", "when", "where", "which", "while", "such",
        "make", "made", "have", "does", "done", "used", "using",
    }
)

# Profondeur maximale de remontée dans la hiérarchie ESCO.
MAX_PROFONDEUR = 12


@dataclass(frozen=True)
class EscoImportSummary:
    """Ce que l'import a réellement écrit, et ce qu'il a écarté."""

    created: int = 0
    already_imported: int = 0
    skipped_existing_name: int = 0
    skipped_transversal: int = 0
    skipped_other_type: int = 0
    aliases_kept: int = 0
    aliases_dropped: int = 0
    categories: dict[str, int] = field(default_factory=dict)
    dry_run: bool = False


# ============================================================
# LECTURE DES FICHIERS
# ============================================================

def _lire_csv(source: Path, nom_partiel: str) -> list[dict]:
    """
    Lit un CSV depuis une archive .zip ou un dossier décompressé.

    Accepter les deux évite d'imposer une manipulation : le fichier
    téléchargé sur le site d'ESCO est une archive, mais un dossier
    déjà extrait fonctionne aussi.
    """

    if source.is_dir():

        chemins = sorted(source.glob(f"*{nom_partiel}*.csv"))

        if not chemins:
            raise FileNotFoundError(
                f"Aucun fichier « {nom_partiel} » dans {source}."
            )

        with open(chemins[0], encoding="utf-8") as fichier:
            return list(csv.DictReader(fichier))

    with zipfile.ZipFile(source) as archive:

        noms = [
            nom
            for nom in archive.namelist()
            if nom_partiel in nom and nom.endswith(".csv")
        ]

        if not noms:
            raise FileNotFoundError(
                f"Aucun fichier « {nom_partiel} » dans {source.name}."
            )

        with archive.open(sorted(noms)[0]) as brut:

            texte = io.TextIOWrapper(brut, encoding="utf-8")

            return list(csv.DictReader(texte))


def alias_exploitable(alias: str) -> bool:
    """
    Cet alias peut-il désigner une compétence à lui seul ?

    Un terme composé passe toujours : c'est le mot isolé qui pose
    problème, parce qu'il se rencontre partout. La règle prolonge
    celle du tri des exigences, qui écarte déjà les mots trop
    généraux d'une annonce.
    """

    from services.requirement_cleaning import GENERIC_TERMS

    forme = normalize_skill_text(alias)

    if len(forme) < MIN_ALIAS_LENGTH:
        return False

    if " " in forme:
        return True

    return forme not in MOTS_OUTILS and forme not in GENERIC_TERMS


def _etiquettes(ligne: dict) -> list[str]:
    """Termes préféré et non préférés d'une ligne ESCO."""

    resultat = []

    for champ in ("preferredLabel", "altLabels", "hiddenLabels"):

        valeur = (ligne.get(champ) or "").strip()

        if valeur:
            resultat.extend(
                item.strip()
                for item in valeur.splitlines()
                if item.strip()
            )

    return resultat


def _table_des_categories(source: Path) -> tuple[dict, dict]:
    """
    (parent par URI, libellé du groupe de niveau 1 par URI).

    ESCO ne range pas ses compétences dans une catégorie directement :
    il faut remonter la hiérarchie jusqu'au groupe de premier niveau —
    « santé et protection sociales », « travailler avec des
    ordinateurs ». La remontée couvre l'intégralité du référentiel.
    """

    parents = {
        ligne["conceptUri"]: ligne["broaderUri"]
        for ligne in _lire_csv(source, "broaderRelationsSkillPillar")
    }

    groupes = {
        ligne["Level 1 URI"]: ligne["Level 1 preferred term"]
        for ligne in _lire_csv(source, "skillsHierarchy")
        if ligne.get("Level 1 URI")
    }

    return parents, groupes


def _categorie(uri: str, parents: dict, groupes: dict) -> str:

    vus: set[str] = set()

    for _ in range(MAX_PROFONDEUR):

        if uri in groupes:
            return groupes[uri]

        if uri in vus or uri not in parents:
            return ""

        vus.add(uri)
        uri = parents[uri]

    return ""


# ============================================================
# IMPORT
# ============================================================

def _formes_deja_revendiquees(db) -> dict[str, str]:
    """Forme normalisée -> nom canonique qui la revendique."""

    index: dict[str, str] = {}

    for competence in db.query(SkillCatalogDB).all():

        etiquettes = [competence.canonical_name]

        try:
            alias = json.loads(competence.aliases or "[]")

            if isinstance(alias, list):
                etiquettes.extend(
                    item for item in alias if isinstance(item, str)
                )

        except (TypeError, ValueError):
            pass

        for etiquette in etiquettes:

            forme = normalize_skill_text(etiquette)

            if forme:
                index.setdefault(forme, competence.canonical_name)

    return index


def import_esco(
    source_fr: str | Path,
    source_en: str | Path | None = None,
    include_transversal: bool = False,
    limit: int | None = None,
    dry_run: bool = False,
) -> EscoImportSummary:
    """
    Importe les compétences ESCO dans skill_catalog.

    `source_fr` et `source_en` sont les archives .zip téléchargées sur
    le site d'ESCO, ou des dossiers déjà décompressés. L'anglais est
    facultatif : sans lui, l'import fonctionne mais perd la plus
    grande partie des synonymes.

    `dry_run` calcule tout sans rien écrire — utile pour voir ce que
    l'import ferait avant de le faire.
    """

    chemin_fr = Path(source_fr)

    lignes_fr = _lire_csv(chemin_fr, "skills_")

    par_uri_en: dict[str, dict] = {}

    if source_en is not None:
        par_uri_en = {
            ligne["conceptUri"]: ligne
            for ligne in _lire_csv(Path(source_en), "skills_")
        }

    parents, groupes = _table_des_categories(chemin_fr)

    db = SessionLocal()

    try:

        revendiquees = _formes_deja_revendiquees(db)

        deja_importees = {
            identifiant
            for (identifiant,) in db.query(SkillCatalogDB.id).all()
        }

        crees = 0
        connues = 0
        nom_pris = 0
        transversales = 0
        autre_type = 0
        alias_gardes = 0
        alias_perdus = 0
        categories: dict[str, int] = {}

        nouvelles: list[SkillCatalogDB] = []

        for ligne in lignes_fr:

            if limit is not None and crees >= limit:
                break

            if ligne.get("skillType") not in SKILL_TYPES:
                autre_type += 1
                continue

            if (
                not include_transversal
                and ligne.get("reuseLevel") == "transversal"
            ):
                transversales += 1
                continue

            uri = ligne["conceptUri"]

            identifiant = "esco-" + uri.rsplit("/", 1)[-1]

            if identifiant in deja_importees:
                connues += 1
                continue

            nom = (ligne.get("preferredLabel") or "").strip()

            forme_nom = normalize_skill_text(nom)

            if not nom or not forme_nom:
                autre_type += 1
                continue

            # Le référentiel maison gagne : plus précis pour ce
            # candidat que son équivalent générique.
            if forme_nom in revendiquees:
                nom_pris += 1
                continue

            # ----------------------------------------------
            # ALIAS
            # ----------------------------------------------

            alias: list[str] = []

            candidats = _etiquettes(ligne)

            if uri in par_uri_en:
                candidats.extend(_etiquettes(par_uri_en[uri]))

            for candidat in candidats:

                forme = normalize_skill_text(candidat)

                if not forme or not alias_exploitable(candidat):
                    continue

                if forme in revendiquees:

                    if forme != forme_nom:
                        alias_perdus += 1

                    continue

                revendiquees[forme] = nom
                alias.append(candidat)
                alias_gardes += 1

            if not alias:
                # Le nom lui-même a été refusé : rien à indexer.
                nom_pris += 1
                continue

            categorie = _categorie(uri, parents, groupes)

            categories[categorie or "(sans catégorie)"] = (
                categories.get(categorie or "(sans catégorie)", 0) + 1
            )

            nouvelles.append(
                SkillCatalogDB(
                    id=identifiant,
                    canonical_name=nom,
                    category=categorie,
                    subcategory=ligne.get("skillType") or "",
                    description=(ligne.get("description") or "").strip(),
                    aliases=json.dumps(alias, ensure_ascii=False),
                    parent_skill_id=None,
                    related_skills="[]",
                    is_active=True,
                )
            )

            crees += 1

        if not dry_run and nouvelles:

            db.bulk_save_objects(nouvelles)
            db.commit()

        return EscoImportSummary(
            created=crees,
            already_imported=connues,
            skipped_existing_name=nom_pris,
            skipped_transversal=transversales,
            skipped_other_type=autre_type,
            aliases_kept=alias_gardes,
            aliases_dropped=alias_perdus,
            categories=dict(
                sorted(
                    categories.items(),
                    key=lambda item: -item[1],
                )
            ),
            dry_run=dry_run,
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

        if not dry_run:
            invalidate_caches()
