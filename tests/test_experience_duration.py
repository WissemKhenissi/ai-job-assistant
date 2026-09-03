"""
Calcul de l'ancienneté professionnelle
(services.experience_duration).

Le point sensible : deux expériences qui se chevauchent ne doivent pas
compter double. Une ancienneté gonflée serait exactement le type
d'affirmation flatteuse que ce projet s'interdit.
"""

from __future__ import annotations

from datetime import date

from services.experience_duration import (
    format_experience_years,
    merge_periods,
    total_experience_years,
)


class _Experience:
    """Suffisant pour ces fonctions : elles ne lisent que les dates."""

    def __init__(self, start_date, end_date=None):
        self.start_date = start_date
        self.end_date = end_date


AUJOURD_HUI = date(2026, 1, 1)


# ============================================================
# FUSION DES PERIODES
# ============================================================

def test_deux_periodes_disjointes_restent_separees():
    resultat = merge_periods(
        [
            (date(2015, 1, 1), date(2016, 1, 1)),
            (date(2018, 1, 1), date(2019, 1, 1)),
        ]
    )

    assert len(resultat) == 2


def test_deux_periodes_qui_se_chevauchent_sont_fusionnees():
    resultat = merge_periods(
        [
            (date(2015, 1, 1), date(2017, 1, 1)),
            (date(2016, 1, 1), date(2018, 1, 1)),
        ]
    )

    assert resultat == [(date(2015, 1, 1), date(2018, 1, 1))]


def test_une_periode_incluse_dans_une_autre_disparait():
    resultat = merge_periods(
        [
            (date(2015, 1, 1), date(2020, 1, 1)),
            (date(2016, 1, 1), date(2017, 1, 1)),
        ]
    )

    assert resultat == [(date(2015, 1, 1), date(2020, 1, 1))]


# ============================================================
# TOTAL EN ANNEES
# ============================================================

def test_une_experience_de_deux_ans():
    annees = total_experience_years(
        [_Experience(date(2018, 1, 1), date(2020, 1, 1))],
        aujourd_hui=AUJOURD_HUI,
    )

    assert 1.9 <= annees <= 2.1


def test_les_chevauchements_ne_comptent_pas_double():
    """
    Deux postes menés en parallèle sur la même période valent deux
    ans d'ancienneté, pas quatre.
    """

    annees = total_experience_years(
        [
            _Experience(date(2018, 1, 1), date(2020, 1, 1)),
            _Experience(date(2018, 6, 1), date(2019, 6, 1)),
        ],
        aujourd_hui=AUJOURD_HUI,
    )

    assert 1.9 <= annees <= 2.1


def test_une_experience_en_cours_court_jusqu_a_aujourd_hui():
    annees = total_experience_years(
        [_Experience(date(2024, 1, 1), None)],
        aujourd_hui=AUJOURD_HUI,
    )

    assert 1.9 <= annees <= 2.1


def test_une_experience_sans_date_de_debut_est_ignoree():
    annees = total_experience_years(
        [_Experience(None, date(2020, 1, 1))],
        aujourd_hui=AUJOURD_HUI,
    )

    assert annees == 0.0


def test_une_date_de_fin_anterieure_au_debut_est_ignoree():
    annees = total_experience_years(
        [_Experience(date(2020, 1, 1), date(2018, 1, 1))],
        aujourd_hui=AUJOURD_HUI,
    )

    assert annees == 0.0


def test_aucune_experience_donne_zero():
    assert total_experience_years([], aujourd_hui=AUJOURD_HUI) == 0.0


def test_plusieurs_experiences_successives_s_additionnent():
    annees = total_experience_years(
        [
            _Experience(date(2015, 1, 1), date(2016, 1, 1)),
            _Experience(date(2018, 1, 1), date(2020, 1, 1)),
        ],
        aujourd_hui=AUJOURD_HUI,
    )

    assert 2.9 <= annees <= 3.1


# ============================================================
# AFFICHAGE
# ============================================================

def test_affichage_sans_experience():
    assert format_experience_years(0) == "—"


def test_affichage_en_mois_sous_un_an():
    assert "mois" in format_experience_years(0.5)


def test_affichage_au_pluriel():
    assert format_experience_years(7.5) == "7,5 ans"


def test_affichage_au_singulier():
    assert format_experience_years(1.0) == "1 an"
