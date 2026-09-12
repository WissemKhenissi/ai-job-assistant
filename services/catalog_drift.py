"""
Écart entre le référentiel en base et celui que décrit le dépôt.

Le référentiel vit à deux endroits, et ce n'est pas un accident :

- ``database/seed_skill_catalog.py`` le décrit dans le dépôt. C'est
  lui qu'un collègue clone, et lui que la mesure d'évaluation est
  censée pouvoir reproduire.
- ``data/job_assistant.db`` le contient à l'exécution. C'est là
  qu'écrit l'écran Référentiel, où l'utilisateur rattache un alias,
  crée une compétence ou en retire une reconnaissance douteuse.

Rien ne fait le pont entre les deux, et le seed n'est pas neutre : il
REMPLACE les colonnes qu'il gère au lieu de les fusionner. Un alias
ajouté depuis l'écran et jamais remonté dans le fichier tient donc
jusqu'au premier ``seed_skill_catalog()``, puis disparaît sans un mot.

Ce n'est pas une hypothèse. Le tri des soixante-huit termes a produit
quatorze alias — « gestion de projets » au pluriel, « KPIs »,
« Product Owner », « principes et technologies de l'IA »… — qui
n'existaient qu'en base. La mesure publiée sur onze annonces portait
sur ce moteur-là ; le dépôt, lui, en décrivait un autre, moins bon.
Une mesure qu'on ne peut pas reproduire depuis le dépôt ne prouve
rien à personne d'autre qu'à celui qui l'a lancée.

Ce module ne répare rien et ne décide rien : il constate. Deux
destinataires, deux usages :

- l'écran Référentiel s'en sert pour prévenir, AVANT la perte, que
  ce qui vient d'être saisi ne survivra pas à un seed ;
- le harnais d'évaluation s'en sert pour refuser de mesurer une base
  qui ne correspond plus au dépôt.

Seules les entrées écrites à la main sont concernées. Les entrées
importées d'ESCO (``esco-*``) ne figurent pas dans le seed et n'ont
pas à y figurer : elles viennent d'un fichier de référence, pas d'une
décision.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from database.db import SessionLocal
from database.models import SkillCatalogDB
from database.seed_skill_catalog import (
    SKILLS,
    champs_ecrases_par_le_seed,
)


# Les colonnes dont on sait afficher l'écart terme à terme. Les
# autres sont signalées par leur nom, ce qui suffit à alerter.
_LISTES = ("aliases", "related_skills")


@dataclass
class EntreeModifiee:
    """Une entrée que le prochain seed ramènerait à sa version dépôt."""

    skill_id: str
    canonical_name: str

    # En base et pas dans le seed : c'est ce qui serait DÉTRUIT.
    alias_perdus: list[str] = field(default_factory=list)

    # Dans le seed et pas en base : la base est en retard d'un seed.
    alias_a_recuperer: list[str] = field(default_factory=list)

    # Les autres colonnes qui diffèrent, par leur nom.
    autres_champs: list[str] = field(default_factory=list)

    @property
    def perd_quelque_chose(self) -> bool:
        return bool(self.alias_perdus or self.autres_champs)


@dataclass
class EntreeHorsDepot:
    """Une compétence créée depuis l'écran, absente du dépôt."""

    skill_id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)


@dataclass
class Derive:
    """Tout ce qui sépare la base du dépôt."""

    modifiees: list[EntreeModifiee] = field(default_factory=list)
    hors_depot: list[EntreeHorsDepot] = field(default_factory=list)
    absentes_de_la_base: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(
            self.modifiees
            or self.hors_depot
            or self.absentes_de_la_base
        )

    @property
    def alias_en_peril(self) -> int:
        """Combien d'alias un seed détruirait maintenant."""

        return sum(
            len(entree.alias_perdus) for entree in self.modifiees
        )


def _liste(brut) -> list[str]:
    """Une colonne JSON de la base, en liste de chaînes."""

    if not brut:
        return []

    try:
        valeurs = json.loads(brut)

    except (TypeError, ValueError):
        return []

    return [str(valeur) for valeur in valeurs] if valeurs else []


def divergences_avec_le_seed() -> Derive:
    """
    Ce qui sépare le référentiel en base de celui du dépôt.

    L'appariement reprend exactement celui du seed — par identifiant,
    puis à défaut par nom canonique — sans quoi on annoncerait des
    écarts que le seed ne verrait pas, et l'inverse.
    """

    db = SessionLocal()

    try:

        lignes = (
            db.query(SkillCatalogDB)
            .filter(SkillCatalogDB.id.like("catalog-%"))
            .all()
        )

        par_id = {ligne.id: ligne for ligne in lignes}

        par_nom: dict[str, SkillCatalogDB] = {}

        for ligne in lignes:
            par_nom.setdefault(ligne.canonical_name, ligne)

        derive = Derive()

        apparies: set[str] = set()

        for skill_data in SKILLS:

            ligne = par_id.get(skill_data["id"]) or par_nom.get(
                skill_data["canonical_name"]
            )

            if ligne is None:
                derive.absentes_de_la_base.append(
                    skill_data["canonical_name"]
                )
                continue

            apparies.add(ligne.id)

            ecart = EntreeModifiee(
                skill_id=ligne.id,
                canonical_name=ligne.canonical_name,
            )

            for champ, attendu in champs_ecrases_par_le_seed(
                skill_data
            ).items():

                if not hasattr(ligne, champ):
                    continue

                actuel = getattr(ligne, champ)

                if actuel == attendu:
                    continue

                if champ == "aliases":

                    en_base = _liste(actuel)
                    au_depot = _liste(attendu)

                    ecart.alias_perdus = [
                        alias
                        for alias in en_base
                        if alias not in au_depot
                    ]

                    ecart.alias_a_recuperer = [
                        alias
                        for alias in au_depot
                        if alias not in en_base
                    ]

                    # Un simple réordonnancement ne coûte rien :
                    # crier dessus apprendrait à ignorer l'alerte.
                    if (
                        not ecart.alias_perdus
                        and not ecart.alias_a_recuperer
                    ):
                        continue

                else:
                    ecart.autres_champs.append(champ)

            if (
                ecart.alias_perdus
                or ecart.alias_a_recuperer
                or ecart.autres_champs
            ):
                derive.modifiees.append(ecart)

        for ligne in lignes:

            if ligne.id in apparies:
                continue

            derive.hors_depot.append(
                EntreeHorsDepot(
                    skill_id=ligne.id,
                    canonical_name=ligne.canonical_name,
                    aliases=_liste(ligne.aliases),
                )
            )

        return derive

    finally:
        db.close()


def extrait_de_seed(derive: Derive) -> str:
    """
    De quoi remonter la dérive dans le dépôt, prêt à coller.

    Une alerte qui dit « vous allez perdre ceci » sans dire comment
    l'éviter finit par être cliquée sans être lue. Le texte produit
    n'est pas exécuté : il est affiché, et c'est un humain qui le
    porte dans database/seed_skill_catalog.py.
    """

    lignes: list[str] = []

    for entree in derive.modifiees:

        if not entree.alias_perdus:
            continue

        lignes.append(
            f"# {entree.canonical_name} "
            f"({entree.skill_id}) — à ajouter aux aliases :"
        )

        for alias in entree.alias_perdus:
            lignes.append(f'    "{alias}",')

        lignes.append("")

    for entree in derive.hors_depot:

        lignes.append(
            f"# Entrée absente du dépôt — à ajouter à SKILLS :"
        )
        lignes.append("{")
        lignes.append(f'    "id": "{entree.skill_id}",')
        lignes.append(
            f'    "canonical_name": "{entree.canonical_name}",'
        )
        lignes.append('    "aliases": [')

        for alias in entree.aliases:
            lignes.append(f'        "{alias}",')

        lignes.append("    ],")
        lignes.append("},")
        lignes.append("")

    return "\n".join(lignes).strip()
