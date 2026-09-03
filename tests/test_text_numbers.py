"""
Comparaison des nombres (services.text_numbers).

Ces tests fixent la frontière entre deux choses que la comparaison
littérale confondait : **écrire le même nombre autrement**, qui est
permis, et **écrire un nombre nouveau**, qui ne l'est pas.

Le cas d'origine est réel : le Master CV dit « environ 100 k€ », la
lettre écrit « environ 100 000 euros », et le garde-fou rejetait une
lettre parfaitement exacte parce que « 000 » n'existait nulle part.
"""

from __future__ import annotations

import pytest

from services.text_numbers import numbers_in


# ============================================================
# MEME NOMBRE, ECRITURES DIFFERENTES
# ============================================================

@pytest.mark.parametrize(
    ("premier", "second"),
    [
        ("Environ 100 k€ de CA.", "Environ 100 000 euros de CA."),
        ("Marge de 1,4 M€.", "Marge de 1,4 million d'euros."),
        ("Budget de 2,5 M€.", "Budget de 2 500 000 €."),
        ("Coût de 15 k€.", "Coût de 15 000 euros."),
    ],
)
def test_deux_ecritures_du_meme_nombre_se_valent(premier, second):
    assert numbers_in(premier) == numbers_in(second)


def test_un_suffixe_d_echelle_est_developpe():
    assert numbers_in("100 k€") == {"100000"}
    assert numbers_in("1,4 M€") == {"1400000"}


def test_un_separateur_de_milliers_disparait():
    assert numbers_in("100 000") == {"100000"}
    assert numbers_in("2 500 000") == {"2500000"}


# ============================================================
# NOMBRE REELLEMENT NOUVEAU
# ============================================================

def test_un_nombre_invente_reste_detecte():
    source = "Environ 100 k€ de CA sur 18 mois."
    genere = "Environ 250 000 euros de CA sur 18 mois."

    assert numbers_in(genere) - numbers_in(source) == {"250000"}


def test_un_pourcentage_invente_reste_detecte():
    source = "Marge publicitaire en progression."
    genere = "Marge publicitaire en hausse de 79 %."

    assert numbers_in(genere) - numbers_in(source) == {"79"}


def test_le_cas_reel_ne_declenche_plus_de_rejet():
    """
    La phrase exacte qui avait fait rejeter une lettre juste.
    """

    fiche = "Résultat : Environ 100 k€ de chiffre d'affaires généré sur les 18 premiers mois."
    lettre = "pour générer environ 100 000 euros de chiffre d'affaires sur les 18 premiers mois."

    assert numbers_in(lettre) - numbers_in(fiche) == set()


# ============================================================
# CE QUI NE DOIT PAS ETRE TOUCHE
# ============================================================

def test_un_numero_de_telephone_reste_intact():
    assert numbers_in("06 12 34 56 78") == {
        "06", "12", "34", "56", "78",
    }


def test_des_annees_restent_des_annees():
    assert numbers_in("2015 – 2017") == {"2015", "2017"}


def test_un_texte_vide_ne_contient_aucun_nombre():
    assert numbers_in("") == set()
    assert numbers_in("Aucun chiffre ici.") == set()
