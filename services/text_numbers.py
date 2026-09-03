"""
Comparaison des nombres entre un texte source et un texte généré.

Le garde-fou central du projet est simple : aucun nombre absent de la
source ne doit apparaître dans le texte produit. Comparer bêtement les
suites de chiffres a montré sa limite en usage réel — le Master CV dit
« environ 100 k€ », la lettre écrit « environ 100 000 euros », et le
contrôle rejette une lettre parfaitement exacte parce que « 000 »
n'existait nulle part.

Ce module ramène donc les nombres à une forme canonique avant de les
comparer : les séparateurs de milliers disparaissent, et les suffixes
d'échelle (k€, M€, millions) sont développés. « 100 k€ », « 100 000 »
et « 100.000 » deviennent tous « 100000 ».

Le contrôle reste strictement plus sûr qu'un contrôle absent, et
strictement moins bruyant qu'une comparaison littérale : il ne laisse
passer qu'une écriture différente du même nombre, jamais un nombre
différent.
"""

from __future__ import annotations

import re


# Espaces utilisés comme séparateurs de milliers, y compris les
# espaces insécables que produisent les traitements de texte.
_SEPARATEURS = "    "

_MILLIERS = re.compile(
    rf"(?<=\d)[{_SEPARATEURS}.](?=\d{{3}}(?!\d))"
)

# Suffixes d'échelle. L'unité est exigée (€, euros, « millions »…) :
# un « k » ou un « M » isolé serait trop souvent une lettre ordinaire.
_ECHELLES = (
    (
        re.compile(
            r"(\d+(?:[.,]\d+)?)\s*k\s*(?:€|euros?\b|eur\b)",
            re.IGNORECASE,
        ),
        1_000,
    ),
    (
        re.compile(
            r"(\d+(?:[.,]\d+)?)\s*(?:milliers?)\b",
            re.IGNORECASE,
        ),
        1_000,
    ),
    (
        re.compile(
            r"(\d+(?:[.,]\d+)?)\s*m\s*(?:€|euros?\b|eur\b)",
            re.IGNORECASE,
        ),
        1_000_000,
    ),
    (
        re.compile(
            r"(\d+(?:[.,]\d+)?)\s*millions?\b",
            re.IGNORECASE,
        ),
        1_000_000,
    ),
)


def _developper(text: str) -> str:
    """Remplace « 1,4 M€ » par « 1400000 », « 100 k€ » par « 100000 »."""

    resultat = text

    for motif, facteur in _ECHELLES:

        def _remplacer(correspondance: re.Match) -> str:

            valeur = correspondance.group(1).replace(",", ".")

            try:
                return str(int(round(float(valeur) * facteur)))

            except ValueError:
                return correspondance.group(0)

        resultat = motif.sub(_remplacer, resultat)

    return resultat


def numbers_in(text: str) -> set[str]:
    """
    Nombres d'un texte, ramenés à une forme comparable.

    Deux écritures du même nombre donnent le même jeton ; deux nombres
    différents en donnent deux.
    """

    if not text:
        return set()

    sans_separateurs = _MILLIERS.sub("", text)

    return set(re.findall(r"\d+", _developper(sans_separateurs)))
