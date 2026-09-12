"""
Le cycle de vie d'une candidature suivie.

Le suivi ne commençait qu'après la génération des documents : une
annonce repérée, ou une candidature envoyée à la main, ne pouvait pas
être suivie. « reperee » ouvre le cycle plus tôt, ce qui introduit la
seule promotion automatique de statut du projet — et donc le seul
endroit où le système peut écraser ce que l'utilisateur a saisi.

Ces tests bornent exactement cette promotion.
"""

from __future__ import annotations

import pytest

from tests.conftest import add_candidate

from models.application import (
    APPLICATION_COLUMNS,
    APPLICATION_STATUS_LABELS,
    APPLICATION_STATUSES,
)
from services.application_service import (
    get_application,
    list_applications,
    record_application,
    update_application_status,
)


CANDIDAT = "candidate-test"

OFFRE = "job-test"


@pytest.fixture
def base(session_factory):

    from models.job import JobOfferDB

    session = session_factory()

    add_candidate(session)

    session.add(
        JobOfferDB(
            id=OFFRE,
            title="Product Owner",
            company="Novalis",
            description="Une annonce.",
        )
    )
    session.commit()
    session.close()


def test_une_annonce_peut_etre_suivie_sans_documents(base):
    """
    Le défaut d'origine : rien ne pouvait être suivi avant d'avoir
    généré un CV.
    """

    record_application(
        candidate_id=CANDIDAT,
        job_offer_id=OFFRE,
        statut_initial="reperee",
    )

    candidature = get_application(CANDIDAT, OFFRE)

    assert candidature is not None
    assert candidature.status == "reperee"
    assert not candidature.a_ses_documents


def test_generer_des_documents_promeut_une_annonce_reperee(base):

    record_application(
        candidate_id=CANDIDAT,
        job_offer_id=OFFRE,
        statut_initial="reperee",
    )

    record_application(
        candidate_id=CANDIDAT,
        job_offer_id=OFFRE,
        cv_pdf_path="exports/cv.pdf",
    )

    assert get_application(CANDIDAT, OFFRE).status == "generee"


def test_la_promotion_ne_remonte_jamais_un_statut_plus_avance(base):
    """
    Régénérer le CV d'une candidature déjà envoyée ne doit pas la
    ramener à « Documents générés » : ce serait perdre ce que
    l'utilisateur a constaté lui-même.
    """

    identifiant = record_application(
        candidate_id=CANDIDAT,
        job_offer_id=OFFRE,
        statut_initial="reperee",
    )

    update_application_status(identifiant, "entretien")

    record_application(
        candidate_id=CANDIDAT,
        job_offer_id=OFFRE,
        cv_pdf_path="exports/cv.pdf",
    )

    assert get_application(CANDIDAT, OFFRE).status == "entretien"


def test_suivre_deux_fois_la_meme_annonce_ne_cree_qu_une_candidature(
    base,
):

    record_application(
        candidate_id=CANDIDAT,
        job_offer_id=OFFRE,
        statut_initial="reperee",
    )
    record_application(
        candidate_id=CANDIDAT,
        job_offer_id=OFFRE,
        statut_initial="reperee",
    )

    assert len(list_applications(CANDIDAT)) == 1


def test_une_offre_non_suivie_ne_retourne_rien(base):

    assert get_application(CANDIDAT, OFFRE) is None


def test_chaque_statut_appartient_a_une_colonne():
    """
    Un statut absent des colonnes ferait disparaître sa candidature
    de l'écran de suivi, sans que rien ne le signale.
    """

    dans_les_colonnes = {
        statut
        for _titre, statuts in APPLICATION_COLUMNS
        for statut in statuts
    }

    assert dans_les_colonnes == set(APPLICATION_STATUSES)


def test_chaque_statut_a_un_libelle():

    for statut in APPLICATION_STATUSES:
        assert APPLICATION_STATUS_LABELS.get(statut)
