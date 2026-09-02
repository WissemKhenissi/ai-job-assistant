"""
Suivi de candidature.

Principe de cadrage couvert ici : « chaque candidature laisse une
trace. Ce qui a été généré et envoyé doit rester retrouvable. »
"""

from __future__ import annotations

from datetime import datetime

import pytest

from conftest import add_candidate


CANDIDATE_ID = "candidate-test"
JOB_OFFER_ID = "job-test"


def _add_job_offer(
    session,
    job_offer_id: str = JOB_OFFER_ID,
    title: str = "Product Owner",
    company: str = "Groupe Meridiem",
):
    from models.job import JobOfferDB

    session.add(
        JobOfferDB(
            id=job_offer_id,
            title=title,
            company=company,
            description="Une annonce.",
            status="selected",
        )
    )

    session.commit()


# ============================================================
# CREATION
# ============================================================

def test_une_candidature_est_enregistree(session_factory):
    from services.application_service import (
        list_applications,
        record_application,
    )

    session = session_factory()
    add_candidate(session)
    _add_job_offer(session)
    session.close()

    record_application(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        cv_docx_path="exports/cv.docx",
        letter_docx_path="exports/lettre.docx",
    )

    candidatures = list_applications(CANDIDATE_ID)

    assert len(candidatures) == 1

    candidature = candidatures[0]

    assert candidature.job_offer_title == "Product Owner"
    assert candidature.company == "Groupe Meridiem"
    assert candidature.status == "generee"
    assert candidature.status_label == "Documents générés"
    assert candidature.a_ses_documents


def test_regenerer_les_documents_ne_cree_pas_de_doublon(
    session_factory,
):
    """
    Idempotence : une offre donne une candidature, quel que soit le
    nombre de régénérations.
    """

    from services.application_service import (
        list_applications,
        record_application,
    )

    session = session_factory()
    add_candidate(session)
    _add_job_offer(session)
    session.close()

    identifiants = {
        record_application(
            candidate_id=CANDIDATE_ID,
            job_offer_id=JOB_OFFER_ID,
            cv_docx_path="exports/cv.docx",
        )
        for _ in range(3)
    }

    assert len(identifiants) == 1
    assert len(list_applications(CANDIDATE_ID)) == 1


def test_regenerer_un_seul_document_conserve_l_autre(
    session_factory,
):
    from services.application_service import (
        list_applications,
        record_application,
    )

    session = session_factory()
    add_candidate(session)
    _add_job_offer(session)
    session.close()

    record_application(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        cv_docx_path="exports/cv.docx",
        letter_docx_path="exports/lettre.docx",
    )

    # On ne régénère que le CV.
    record_application(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        cv_docx_path="exports/cv-v2.docx",
    )

    candidature = list_applications(CANDIDATE_ID)[0]

    assert candidature.cv_docx_path == "exports/cv-v2.docx"
    assert candidature.letter_docx_path == "exports/lettre.docx"


def test_le_statut_saisi_n_est_pas_ecrase_par_une_regeneration(
    session_factory,
):
    """
    Régénérer un CV ne doit pas faire oublier qu'on a déjà passé un
    entretien pour cette offre.
    """

    from services.application_service import (
        list_applications,
        record_application,
        update_application_status,
    )

    session = session_factory()
    add_candidate(session)
    _add_job_offer(session)
    session.close()

    application_id = record_application(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        cv_docx_path="exports/cv.docx",
    )

    update_application_status(application_id, "entretien")

    record_application(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        cv_docx_path="exports/cv-v2.docx",
    )

    assert list_applications(CANDIDATE_ID)[0].status == "entretien"


# ============================================================
# SUIVI MANUEL
# ============================================================

def test_le_statut_se_met_a_jour_manuellement(session_factory):
    from services.application_service import (
        list_applications,
        record_application,
        update_application_status,
    )

    session = session_factory()
    add_candidate(session)
    _add_job_offer(session)
    session.close()

    application_id = record_application(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
    )

    envoi = datetime(2026, 9, 2, 10, 0)

    update_application_status(
        application_id,
        "envoyee",
        notes="Envoyée via LinkedIn.",
        sent_at=envoi,
    )

    candidature = list_applications(CANDIDATE_ID)[0]

    assert candidature.status == "envoyee"
    assert candidature.status_label == "Candidature envoyée"
    assert candidature.notes == "Envoyée via LinkedIn."
    assert candidature.sent_at == envoi


def test_un_statut_inconnu_est_refuse(session_factory):
    """
    Le suivi n'accepte pas de statut arbitraire : une faute de frappe
    doit échouer, pas créer un statut fantôme.
    """

    from services.application_service import (
        record_application,
        update_application_status,
    )

    session = session_factory()
    add_candidate(session)
    _add_job_offer(session)
    session.close()

    application_id = record_application(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
    )

    with pytest.raises(ValueError, match="Statut inconnu"):
        update_application_status(application_id, "peut-etre")


def test_mettre_a_jour_une_candidature_inexistante_echoue(
    session_factory,
):
    from services.application_service import (
        update_application_status,
    )

    session = session_factory()
    add_candidate(session)
    session.close()

    with pytest.raises(ValueError, match="introuvable"):
        update_application_status("application-inconnue", "envoyee")


# ============================================================
# CHEMINS DE FICHIERS
# ============================================================

def test_les_chemins_sont_stockes_relativement_au_projet(
    session_factory,
):
    """
    Un chemin absolu deviendrait invalide dès que le dossier du
    projet est déplacé ou synchronisé sur une autre machine.
    """

    from services.application_service import (
        PROJECT_ROOT,
        list_applications,
        record_application,
    )

    session = session_factory()
    add_candidate(session)
    _add_job_offer(session)
    session.close()

    absolu = PROJECT_ROOT / "exports" / "cv-test.docx"

    record_application(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        cv_docx_path=absolu,
    )

    candidature = list_applications(CANDIDATE_ID)[0]

    assert candidature.cv_docx_path == "exports/cv-test.docx"


# ============================================================
# PLUSIEURS OFFRES
# ============================================================

def test_chaque_offre_a_sa_propre_candidature(session_factory):
    from services.application_service import (
        list_applications,
        record_application,
    )

    session = session_factory()
    add_candidate(session)
    _add_job_offer(session, "job-1", "Product Owner")
    _add_job_offer(session, "job-2", "Product Manager")
    session.close()

    record_application(CANDIDATE_ID, "job-1")
    record_application(CANDIDATE_ID, "job-2")

    candidatures = list_applications(CANDIDATE_ID)

    assert len(candidatures) == 2

    titres = {item.job_offer_title for item in candidatures}

    assert titres == {"Product Owner", "Product Manager"}
