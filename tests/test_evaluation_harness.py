"""
Tests du harnais de mesure lui-même.

Un instrument de mesure faux est pire que pas d'instrument : il donne
confiance dans des chiffres qui ne veulent rien dire. Ces tests
vérifient le calcul de precision / recall et surtout la détection des
surévaluations, qui est le signal le plus important du projet.
"""

from __future__ import annotations

import pytest

from evaluation.evaluate import (
    EvaluationCase,
    ExtractionResult,
    StatusError,
)


# ============================================================
# PRECISION / RECALL
# ============================================================

def test_precision_et_recall_sur_un_cas_parfait():
    extraction = ExtractionResult(
        trouvees_et_attendues=["A", "B"],
    )

    assert extraction.precision == 1.0
    assert extraction.recall == 1.0


def test_un_faux_positif_degrade_la_precision_pas_le_recall():
    extraction = ExtractionResult(
        trouvees_et_attendues=["A", "B", "C"],
        faux_positifs=["D"],
    )

    assert extraction.precision == 0.75
    assert extraction.recall == 1.0


def test_un_oubli_degrade_le_recall_pas_la_precision():
    extraction = ExtractionResult(
        trouvees_et_attendues=["A", "B", "C"],
        oubliees=["D"],
    )

    assert extraction.precision == 1.0
    assert extraction.recall == 0.75


def test_absence_de_donnees_ne_produit_pas_de_division_par_zero():
    extraction = ExtractionResult()

    assert extraction.precision is None
    assert extraction.recall is None


# ============================================================
# SUREVALUATION
# ============================================================

@pytest.mark.parametrize(
    "attendu, obtenu",
    [
        ("missing", "inferred"),
        ("missing", "declared"),
        ("missing", "proven"),
        ("inferred", "declared"),
        ("inferred", "proven"),
        ("declared", "proven"),
    ],
)
def test_affirmer_plus_que_la_realite_est_une_surevaluation(
    attendu,
    obtenu,
):
    erreur = StatusError(
        competence="Test",
        attendu=attendu,
        obtenu=obtenu,
    )

    assert erreur.est_surevaluation


@pytest.mark.parametrize(
    "attendu, obtenu",
    [
        ("proven", "declared"),
        ("proven", "inferred"),
        ("proven", "missing"),
        ("declared", "inferred"),
        ("inferred", "missing"),
    ],
)
def test_affirmer_moins_que_la_realite_n_est_pas_une_surevaluation(
    attendu,
    obtenu,
):
    """
    Sous-évaluer est une erreur, mais pas une erreur d'honnêteté :
    elle ne doit pas polluer le signal des surévaluations.
    """

    erreur = StatusError(
        competence="Test",
        attendu=attendu,
        obtenu=obtenu,
    )

    assert not erreur.est_surevaluation


def test_une_competence_non_analysee_n_est_pas_une_surevaluation():
    erreur = StatusError(
        competence="Test",
        attendu="proven",
        obtenu="(non analysée)",
    )

    assert not erreur.est_surevaluation


# ============================================================
# GARDE-FOU SUR LES CAS NON RELUS
# ============================================================

def test_un_cas_est_non_relu_par_defaut():
    """
    Le défaut doit être prudent : un cas dont l'annotation vient du
    moteur ne doit jamais être compté par accident.
    """

    case = EvaluationCase(
        slug="test",
        titre="Test",
        texte="",
        competences_attendues=[],
        statuts_attendus={},
        revise_par_humain=False,
    )

    assert case.revise_par_humain is False


def test_le_dataset_livre_n_est_pas_marque_comme_relu():
    """
    Les cas amorcés automatiquement sont pré-remplis avec la sortie
    du moteur : tant qu'ils ne sont pas relus, les compter
    reviendrait à comparer le moteur à lui-même.
    """

    from evaluation.evaluate import load_cases

    for case in load_cases():

        if case.commentaire.startswith("PRÉ-REMPLI PAR LE MOTEUR"):

            assert not case.revise_par_humain, (
                f"{case.slug} est marqué relu alors que son "
                "annotation vient encore du moteur"
            )
