"""
Mise en ligne de CV d'une réalisation du Master CV.

Constat qui a motivé ce module : le Master CV contenait « marge
publicitaire passée d'environ 1,4 M€ à environ 2,5 M€, ≈ +79 % sur
7 ans », et le CV affichait « Suivi de KPI et performance business ».
Les réalisations étaient bien construites par la sélection, puis
purement et simplement ignorées par l'export. Aucune des preuves du
Master CV ne porte de chiffre : ils vivent tous ici.

Le cahier des charges est sans ambiguïté là-dessus (§8, §17) : une
réalisation prime sur une description de tâche.

La composition est déterministe — titre, puis résultat, puis au plus
une métrique qui apporte un chiffre que le résultat ne donne pas déjà.
Rien n'est reformulé : ce texte est déjà de la forme action + contexte
+ impact, et c'est le contenu le plus précieux du document.
"""

from __future__ import annotations

import re
import unicodedata

from services.text_numbers import numbers_in


def _phrases_metriques(metrics: str) -> list[str]:
    """Les métriques sont saisies une par ligne dans le Master CV."""

    return [
        ligne.strip(" •-–\t")
        for ligne in (metrics or "").splitlines()
        if ligne.strip(" •-–\t")
    ]


def _metrique_complementaire(result: str, metrics: str) -> str:
    """
    Métrique qui apporte un chiffre absent du résultat.

    Une métrique qui ne fait que répéter les chiffres du résultat
    alourdit la ligne sans rien ajouter. Entre plusieurs candidates,
    on préfère un pourcentage — c'est la forme qui frappe le plus —
    puis la plus détaillée.
    """

    chiffres_resultat = numbers_in(result)

    candidates = [
        phrase
        for phrase in _phrases_metriques(metrics)
        if numbers_in(phrase) and not numbers_in(phrase) <= chiffres_resultat
    ]

    if not candidates:
        return ""

    pourcentages = [
        phrase for phrase in candidates if "%" in phrase
    ]

    if pourcentages:
        return max(pourcentages, key=len)

    return max(candidates, key=len)


def _minuscule_initiale(texte: str) -> str:
    """
    « Marge publicitaire passée… » devient « marge publicitaire
    passée… » quand la phrase suit un tiret. Un sigle reste intact.
    """

    if not texte:
        return texte

    premier_mot = texte.split(" ", 1)[0]

    if premier_mot.isupper() and len(premier_mot) > 1:
        return texte

    return texte[0].lower() + texte[1:]


def build_achievement_line(
    title: str,
    result: str = "",
    metrics: str = "",
) -> tuple[str, str]:
    """
    Compose la puce d'une réalisation.

    Retourne (titre, détail) : l'export met le titre en gras et le
    détail à sa suite. Le détail peut être vide — une réalisation sans
    résultat renseigné garde le droit de figurer, elle dit ce qui a
    été mené.
    """

    titre = (title or "").strip().rstrip(".")

    morceaux: list[str] = []

    resultat = (result or "").strip()

    metrique = _metrique_complementaire(resultat, metrics)

    if resultat:
        # Le point final disparaît quand une parenthèse suit : « …sur
        # la période. (≈ +79 %) » se lit mal.
        morceaux.append(
            _minuscule_initiale(
                resultat.rstrip(".") if metrique else resultat
            )
        )

    if metrique:
        morceaux.append(f"({metrique.rstrip('.')})")

    return titre, " ".join(morceaux)


def _forme_comparable(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation, espaces normalisés."""

    normalise = unicodedata.normalize("NFKD", texte or "")

    normalise = "".join(
        caractere
        for caractere in normalise
        if not unicodedata.combining(caractere)
    )

    normalise = re.sub(r"[^a-z0-9]+", " ", normalise.casefold())

    return re.sub(r"\s+", " ", normalise).strip()


def is_redundant(title: str, detail: str, textes_de_puces) -> bool:
    """
    Cette réalisation répète-t-elle une puce déjà retenue ?

    Cas réel : la réalisation « Monétisation des supports ticketis.fr —
    suivi opérationnel du bon déroulement des campagnes » côtoyait la
    puce « Participation à la monétisation des supports ticketis.fr :
    display on-site, extension d'audience… », plus riche et plus
    précise. Deux fois la même chose sur un CV se remarque.

    Une réalisation chiffrée n'est jamais redondante : le chiffre est
    précisément ce que la puce n'a pas.
    """

    if numbers_in(f"{title} {detail}"):
        return False

    titre_comparable = _forme_comparable(title)

    if not titre_comparable:
        return True

    return any(
        titre_comparable in _forme_comparable(texte)
        for texte in textes_de_puces
    )


def achievement_source_text(
    title: str,
    situation: str = "",
    action: str = "",
    result: str = "",
    metrics: str = "",
) -> str:
    """
    Tout ce que le Master CV dit de cette réalisation.

    Sert au contrôle : aucun chiffre de la puce ne doit être absent
    d'ici.
    """

    return " ".join(
        partie.strip()
        for partie in (title, situation, action, result, metrics)
        if partie and partie.strip()
    )
