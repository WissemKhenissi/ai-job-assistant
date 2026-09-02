"""
Récupération du contenu d'une annonce depuis son URL.

Aucune IA ici : un simple téléchargement de la page suivi d'une
extraction du texte principal (bibliothèque trafilatura, qui ignore
raisonnablement bien menus/footer/publicités). Purement mécanique,
donc aucun risque d'invention — soit le texte a été trouvé sur la
page, soit non.

Ce n'est pas garanti de fonctionner sur tous les sites. Certains
(LinkedIn en particulier) bloquent activement ce type de requête ou
chargent leur contenu en JavaScript, qu'un simple téléchargement HTTP
ne peut jamais voir. Dans ce cas, l'échec est explicite et invite au
copier-coller manuel — qui reste, comme pour les fonctionnalités IA
du projet, le filet de sécurité toujours disponible : cette
fonctionnalité est un raccourci, jamais une dépendance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class FetchedJobOffer:
    title: str = ""
    text: str = ""
    success: bool = False
    error: str = ""


def fetch_job_offer_from_url(url: str) -> FetchedJobOffer:
    """
    Télécharge une page et en extrait le titre et le texte principal.

    Ne lève jamais d'exception : tout échec (URL invalide, page
    inaccessible, site qui bloque la requête, contenu chargé en
    JavaScript) retourne un résultat explicite avec un message
    compréhensible, plutôt que de faire planter le formulaire.
    """

    url = url.strip()

    if not url:
        return FetchedJobOffer(error="Aucun lien fourni.")

    if urlparse(url).scheme not in ("http", "https"):
        return FetchedJobOffer(
            error="Le lien doit commencer par http:// ou https://."
        )

    import trafilatura

    try:
        telechargement = trafilatura.fetch_url(url)

    except Exception as error:
        return FetchedJobOffer(
            error=f"Téléchargement impossible : {error}"
        )

    if not telechargement:
        return FetchedJobOffer(
            error=(
                "Impossible d'accéder à cette page — le site bloque "
                "peut-être les requêtes automatiques (fréquent sur "
                "LinkedIn notamment), ou le lien est incorrect."
            )
        )

    try:
        extraction = trafilatura.extract(
            telechargement,
            output_format="json",
            with_metadata=True,
            favor_recall=True,
        )

    except Exception as error:
        return FetchedJobOffer(
            error=f"Extraction du contenu impossible : {error}"
        )

    if not extraction:
        return FetchedJobOffer(
            error=(
                "Aucun contenu exploitable trouvé sur cette page — "
                "elle charge peut-être son contenu dynamiquement "
                "(JavaScript), ce qu'un téléchargement simple ne "
                "peut pas voir."
            )
        )

    try:
        donnees = json.loads(extraction)

    except json.JSONDecodeError:
        return FetchedJobOffer(error="Contenu récupéré illisible.")

    texte = (donnees.get("text") or "").strip()

    if not texte:
        return FetchedJobOffer(
            error="La page ne contient aucun texte exploitable."
        )

    titre = (donnees.get("title") or "").strip()

    return FetchedJobOffer(title=titre, text=texte, success=True)
