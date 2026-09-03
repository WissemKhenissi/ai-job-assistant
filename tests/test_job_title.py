"""
Nettoyage de l'intitulé d'annonce (services.job_title).

Les annonces enregistrées depuis un lien portent le titre de la page,
pas celui du poste. Écrit tel quel sous le nom du candidat, cela ruine
le CV. Ces tests vérifient que le nettoyage coupe sans jamais
réécrire, et qu'il préfère ne rien renvoyer plutôt qu'un fragment.
"""

from __future__ import annotations

import pytest

from services.job_title import clean_job_title


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        (
            "Anonyme hiring Chef de Projet Marketing Digital in "
            "Paris, Île-de-France, France | LinkedIn",
            "Chef de Projet Marketing Digital",
        ),
        (
            "Chef(fe) de Projet CRM Senior (H/F) at IODA Group "
            "– Greater Paris",
            "Chef(fe) de Projet CRM Senior",
        ),
        (
            "Product Owner (F/H)",
            "Product Owner",
        ),
        (
            "Product Manager chez Cdiscount",
            "Product Manager",
        ),
    ],
)
def test_un_titre_de_page_est_ramene_a_l_intitule(brut, attendu):
    assert clean_job_title(brut) == attendu


def test_un_titre_deja_propre_n_est_pas_touche():
    assert clean_job_title("Product Owner") == "Product Owner"


def test_un_titre_vide_reste_vide():
    assert clean_job_title("") == ""


def test_une_phrase_entiere_est_ecartee():
    """
    Mieux vaut afficher le positionnement du candidat qu'un fragment
    de page web étalé sous son nom.
    """

    phrase = (
        "Nous recherchons pour notre client un profil confirmé "
        "capable de piloter des projets digitaux complexes dans un "
        "environnement exigeant"
    )

    assert clean_job_title(phrase) == ""


def test_le_nettoyage_ne_reecrit_jamais():
    """
    Le titre nettoyé est toujours un extrait du titre d'origine :
    aucun mot n'est ajouté ni remplacé.
    """

    brut = "Chef(fe) de Projet CRM Senior (H/F) at IODA Group"

    propre = clean_job_title(brut)

    for mot in propre.split():
        assert mot in brut
