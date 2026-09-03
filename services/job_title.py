"""
Nettoyage de l'intitulé d'une annonce pour l'afficher sur un CV.

Les annonces enregistrées depuis un lien portent souvent le titre de
la page plutôt que celui du poste :

    "Anonyme hiring Chef de Projet Marketing Digital in Paris,
     Île-de-France, France | LinkedIn"
    "Chef(fe) de Projet CRM Senior (H/F) at IODA Group – Greater Paris"

Écrit tel quel sous le nom du candidat, cela ruine le document. Ce
module ne retient que l'intitulé, sans jamais rien inventer : il
coupe, il ne réécrit pas. Si le titre ne correspond à aucun motif
connu, il ressort inchangé — mieux vaut un titre imparfait qu'un
titre fabriqué.
"""

from __future__ import annotations

import re


# Au-delà, ce n'est plus un intitulé de poste : on préfère ne rien
# afficher que d'étaler une phrase entière sous le nom.
MAX_TITLE_LENGTH = 80


# Suffixes de site, coupés avec tout ce qui suit.
_SUFFIXES = (
    " | ",
    " – Greater ",
    " - Greater ",
)

# Séparateurs « poste <sep> entreprise / lieu ».
_SEPARATEURS = (
    " at ",
    " chez ",
    " in ",
    " à ",
)

# Mentions de mixité, retirées où qu'elles soient.
_MENTIONS = re.compile(
    r"\s*[\(\[]?\s*(?:h\s*/\s*f|f\s*/\s*h|m\s*/\s*f|w\s*/\s*m)"
    r"\s*[\)\]]?\s*",
    flags=re.IGNORECASE,
)


def clean_job_title(title: str) -> str:
    """
    Intitulé de poste présentable, extrait du titre de l'annonce.

    Retourne une chaîne vide si rien d'exploitable ne subsiste : le
    CV affiche alors le positionnement du candidat plutôt qu'un
    fragment de page web.
    """

    if not title:
        return ""

    propre = title.strip()

    # "Entreprise hiring Poste in Ville" : ce qui précède est le
    # recruteur, pas le poste.
    minuscules = propre.lower()

    if " hiring " in minuscules:
        propre = propre[minuscules.index(" hiring ") + len(" hiring "):]

    for suffixe in _SUFFIXES:
        index = propre.lower().find(suffixe.lower())
        if index > 0:
            propre = propre[:index]

    for separateur in _SEPARATEURS:
        index = propre.lower().find(separateur.lower())
        if index > 0:
            propre = propre[:index]

    propre = _MENTIONS.sub(" ", propre)

    propre = re.sub(r"\s+", " ", propre).strip(" -–—|,;:")

    if len(propre) > MAX_TITLE_LENGTH:
        return ""

    return propre
