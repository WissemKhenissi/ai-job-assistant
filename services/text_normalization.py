"""
Formes de comparaison d'un texte, partagées par toute la chaîne.

Ces deux fonctions existaient en quatre exemplaires : deux copies
mot pour mot de la forme « minuscules sans accents »
(`services.ai.job_analysis`, `ui.job_matching.analysis`) et deux
copies quasi identiques de la forme sans ponctuation
(`services.requirement_cleaning`, `services.requirement_importance`).

Ce n'était pas qu'une redite. Le tri des exigences déduplique sur une
forme, et le classement de leur niveau d'exigence indexe sur l'autre :
si les deux dérivent d'un caractère, une exigence retenue par le tri
cesse silencieusement de retrouver son niveau. Une seule définition
supprime cette possibilité.

À ne pas confondre avec les `_normalize` de
`services.job_requirements_service`, `services.matching.normalization`
et `services.skill_semantic_service` : ceux-là appliquent des règles
propres à leur usage (traitement des tirets, des points de
« node.js », des séparateurs de chemin) et ne sont pas
interchangeables avec celles-ci.
"""

from __future__ import annotations

import re
import unicodedata


def sans_accents(texte: str) -> str:
    """
    Retire les accents sans toucher à la structure du texte.

    Sauts de ligne, points et virgules survivent : le classement du
    niveau d'exigence découpe le texte de l'annonce en phrases après
    être passé par ici.

    La décomposition est NFD, et pas NFKD, pour une raison mesurée :
    NFKD réécrit les caractères de compatibilité, et transforme donc
    « … » en trois points. Sur une annonce réelle, « maîtrise des
    outils produits (Jira, Confluence, Figma, …) » se coupait au
    premier point : la liste perdait son dernier élément, cessait
    d'être reconnue comme énumération, et Jira redevenait une
    condition d'entrée. Une normalisation qui déplace les frontières
    de phrase n'a pas sa place ici.
    """

    decompose = unicodedata.normalize("NFD", texte or "")

    return "".join(
        caractere
        for caractere in decompose
        if not unicodedata.combining(caractere)
    )


def minuscules_sans_accents(texte: str) -> str:
    """
    Forme la plus permissive : la ponctuation et les espaces restent.

    Suffisant pour un contrôle de présence (« ce terme figure-t-il
    dans l'annonce ? ») ou une déduplication d'affichage.
    """

    return sans_accents(texte).casefold()


def forme_comparable(texte: str) -> str:
    """
    Forme de comparaison stricte : minuscules, sans accents, sans
    ponctuation, espaces réduits.

    « + » et « # » sont conservés — sans eux, C++ et C# deviendraient
    le même terme, et tous deux se confondraient avec « c ».

    C'est la clé sous laquelle une exigence est retrouvée d'un module
    à l'autre.

    Ici la décomposition NFKD est sans danger — et utile : la
    ponctuation étant de toute façon jetée, elle ne peut plus
    déplacer aucune frontière, et elle ramène en prime les ligatures
    et exposants d'un texte collé depuis une page web.
    """

    decompose = unicodedata.normalize("NFKD", texte or "")

    normalise = "".join(
        caractere
        for caractere in decompose
        if not unicodedata.combining(caractere)
    ).casefold()

    normalise = re.sub(r"[^a-z0-9+#]+", " ", normalise)

    return re.sub(r"\s+", " ", normalise).strip()
