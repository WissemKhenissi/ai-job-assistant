"""
Calcul de l'ancienneté professionnelle à partir des expériences.

Les périodes sont fusionnées avant d'être additionnées : deux
expériences qui se chevauchent (un poste et une mission menée en
parallèle) ne doivent pas compter double, sinon l'ancienneté affichée
dépasserait la réalité — exactement le genre de gonflement que ce
projet existe pour éviter.

Fonctions pures, sans accès base : elles reçoivent les expériences et
rendent un nombre, ce qui les rend testables sans base de données.
"""

from __future__ import annotations

from datetime import date


# Une année moyenne, en jours (365.25 tient compte des bissextiles).
JOURS_PAR_AN = 365.25


def _periodes(experiences, aujourd_hui: date) -> list[tuple[date, date]]:
    """
    Extrait les couples (début, fin) exploitables.

    Une expérience en cours (end_date à None) court jusqu'à
    aujourd'hui ; une expérience sans date de début est ignorée, faute
    de pouvoir en mesurer la durée.
    """

    periodes = []

    for experience in experiences:

        debut = getattr(experience, "start_date", None)

        if debut is None:
            continue

        fin = getattr(experience, "end_date", None) or aujourd_hui

        if fin < debut:
            continue

        periodes.append((debut, fin))

    return sorted(periodes)


def merge_periods(
    periodes: list[tuple[date, date]],
) -> list[tuple[date, date]]:
    """Fusionne les périodes qui se chevauchent ou se touchent."""

    fusionnees: list[tuple[date, date]] = []

    for debut, fin in sorted(periodes):

        if fusionnees and debut <= fusionnees[-1][1]:

            debut_precedent, fin_precedente = fusionnees[-1]
            fusionnees[-1] = (debut_precedent, max(fin_precedente, fin))

        else:
            fusionnees.append((debut, fin))

    return fusionnees


def total_experience_years(
    experiences,
    aujourd_hui: date | None = None,
) -> float:
    """
    Ancienneté totale, en années, chevauchements déduits.

    Retourne 0.0 si aucune expérience n'est exploitable.
    """

    aujourd_hui = aujourd_hui or date.today()

    fusionnees = merge_periods(_periodes(experiences, aujourd_hui))

    jours = sum(
        (fin - debut).days for debut, fin in fusionnees
    )

    return round(jours / JOURS_PAR_AN, 1)


def format_experience_years(annees: float) -> str:
    """Formule courte pour l'affichage : "7,5 ans", "1 an", "—"."""

    if annees <= 0:
        return "—"

    if annees < 1:
        mois = max(1, round(annees * 12))
        return f"{mois} mois"

    texte = f"{annees:.1f}".replace(".", ",").replace(",0", "")

    return f"{texte} an" + ("s" if annees >= 2 else "")
