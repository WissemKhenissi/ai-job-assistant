"""
Écriture du profil candidat (Master CV).

Ces tests portent sur deux garanties : les écritures ne créent pas de
doublons silencieux (c'est ce qui avait produit 13 lignes de
compétences en double), et un champ inconnu est refusé plutôt
qu'ignoré.
"""

from __future__ import annotations

from datetime import date

import pytest

from conftest import (
    add_candidate,
    add_candidate_skill,
    add_catalog_skill,
    add_evidence,
)


CANDIDATE_ID = "candidate-test"


# ============================================================
# CANDIDAT
# ============================================================

def test_update_candidate_modifie_les_coordonnees(session_factory):
    from services.profile_service import get_candidate, update_candidate

    session = session_factory()
    add_candidate(session)
    session.close()

    update_candidate(
        CANDIDATE_ID,
        phone="06 12 34 56 78",
        location="Lyon / Auvergne-Rhône-Alpes",
    )

    candidate = get_candidate()

    assert candidate.phone == "06 12 34 56 78"
    assert candidate.location == "Lyon / Auvergne-Rhône-Alpes"
    # Les autres champs ne sont pas touchés.
    assert candidate.email == "test@example.com"


def test_update_candidate_refuse_un_champ_inconnu(session_factory):
    from services.profile_service import update_candidate

    session = session_factory()
    add_candidate(session)
    session.close()

    with pytest.raises(ValueError, match="inconnus"):
        update_candidate(CANDIDATE_ID, nom_de_famille="Moreau")


def test_update_candidate_sur_un_id_inexistant_echoue(
    session_factory,
):
    from services.profile_service import update_candidate

    session = session_factory()
    add_candidate(session)
    session.close()

    with pytest.raises(ValueError, match="introuvable"):
        update_candidate("candidate-fantome", phone="0000000000")


# ============================================================
# EXPERIENCE
# ============================================================

def test_add_experience_puis_relecture(session_factory):
    from services.profile_service import add_experience, get_experiences

    session = session_factory()
    add_candidate(session)
    session.close()

    experience_id = add_experience(
        candidate_id=CANDIDATE_ID,
        company="Cobalt Studio",
        job_title="Traffic Manager",
        start_date=date(2015, 1, 1),
        end_date=date(2016, 1, 1),
    )

    experiences = get_experiences()

    assert len(experiences) == 1
    assert experiences[0].id == experience_id
    assert experiences[0].company == "Cobalt Studio"


def test_get_experiences_est_triee_par_date_decroissante(
    session_factory,
):
    from services.profile_service import add_experience, get_experiences

    session = session_factory()
    add_candidate(session)
    session.close()

    add_experience(
        CANDIDATE_ID,
        "Cobalt Studio",
        "Traffic Manager",
        date(2015, 1, 1),
        date(2016, 1, 1),
    )

    add_experience(
        CANDIDATE_ID,
        "Ticketis",
        "Chef de Publicité",
        date(2017, 11, 1),
        date(2025, 6, 30),
    )

    experiences = get_experiences()

    assert [e.company for e in experiences] == [
        "Ticketis",
        "Cobalt Studio",
    ]


def test_update_experience_modifie_les_champs_fournis(
    session_factory,
):
    from services.profile_service import (
        add_experience,
        get_experiences,
        update_experience,
    )

    session = session_factory()
    add_candidate(session)
    session.close()

    experience_id = add_experience(
        CANDIDATE_ID,
        "Groupe Meridiem",
        "Account Manager",
        date(2016, 1, 1),
    )

    update_experience(
        experience_id,
        description="Monétisation des supports ticketis.fr.",
    )

    experience = get_experiences()[0]

    assert experience.description == (
        "Monétisation des supports ticketis.fr."
    )
    # Champ non fourni : inchangé.
    assert experience.company == "Groupe Meridiem"


# ============================================================
# REALISATION
# ============================================================

def test_add_achievement_rattachee_a_une_experience(
    session_factory,
):
    from services.profile_service import (
        add_achievement,
        add_experience,
        get_achievements,
    )

    session = session_factory()
    add_candidate(session)
    session.close()

    experience_id = add_experience(
        CANDIDATE_ID,
        "Groupe Meridiem",
        "Account Manager",
        date(2016, 1, 1),
    )

    add_achievement(
        experience_id,
        title="Optimisation des campagnes display",
        result="Amélioration du taux de conversion.",
    )

    achievements = get_achievements(experience_id)

    assert len(achievements) == 1
    assert achievements[0].title == (
        "Optimisation des campagnes display"
    )


# ============================================================
# COMPETENCE — GARDE-FOU ANTI-DOUBLON
# ============================================================

def test_add_skill_deux_fois_ne_cree_pas_de_doublon(
    session_factory,
):
    """
    C'est précisément l'absence de ce contrôle qui avait produit 13
    lignes de compétences en double dans le Master CV.
    """

    from services.profile_service import add_skill, get_skills

    session = session_factory()
    add_candidate(session)
    session.close()

    premier_id = add_skill(CANDIDATE_ID, "Adtech")
    second_id = add_skill(CANDIDATE_ID, "Adtech")

    assert premier_id == second_id
    assert len(get_skills(CANDIDATE_ID)) == 1


def test_add_skill_avec_des_noms_differents_cree_deux_lignes(
    session_factory,
):
    from services.profile_service import add_skill, get_skills

    session = session_factory()
    add_candidate(session)
    session.close()

    add_skill(CANDIDATE_ID, "Adtech")
    add_skill(CANDIDATE_ID, "E-commerce")

    assert len(get_skills(CANDIDATE_ID)) == 2


def test_update_skill_modifie_les_champs_fournis(session_factory):
    from services.profile_service import (
        add_skill,
        get_skills,
        update_skill,
    )

    session = session_factory()
    add_candidate(session)
    session.close()

    skill_id = add_skill(CANDIDATE_ID, "Adtech")

    update_skill(skill_id, level="Avancé")

    skill = get_skills(CANDIDATE_ID)[0]

    assert skill.level == "Avancé"
    assert skill.name == "Adtech"


# ============================================================
# PREUVE — LE PASSAGE A "PROVEN"
# ============================================================

def test_add_evidence_rend_une_competence_prouvable(
    session_factory,
):
    """
    add_evidence est la seule fonction qui peut faire passer une
    compétence de "declared" à "proven" côté moteur de matching.
    """

    from services.matching import analyze_candidate_against_skills
    from services.profile_service import add_evidence, add_skill

    session = session_factory()
    add_candidate(session)

    from conftest import add_catalog_skill

    add_catalog_skill(
        session,
        canonical_name="Adtech",
        aliases=["Adtech"],
    )

    session.close()

    skill_id = add_skill(CANDIDATE_ID, "Adtech")

    add_evidence(
        candidate_id=CANDIDATE_ID,
        skill_id=skill_id,
        description=(
            "Référent sur les environnements Smart AdServer, "
            "Xandr et Criteo."
        ),
    )

    result = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Adtech"],
    )

    assert result.matches[0].status == "proven"


# ============================================================
# FORMATION
# ============================================================

def test_add_education_puis_relecture(session_factory):
    from services.profile_service import add_education, get_educations

    session = session_factory()
    add_candidate(session)
    session.close()

    add_education(
        candidate_id=CANDIDATE_ID,
        institution="Université Lumière Lyon 2",
        degree="Master AEI E-Commerce",
        field_of_study="Cybersécurité",
        start_year=2015,
        end_year=2017,
    )

    educations = get_educations(CANDIDATE_ID)

    assert len(educations) == 1
    assert educations[0].institution == (
        "Université Lumière Lyon 2"
    )
    assert educations[0].end_year == 2017


def test_update_education_modifie_les_champs_fournis(
    session_factory,
):
    from services.profile_service import (
        add_education,
        get_educations,
        update_education,
    )

    session = session_factory()
    add_candidate(session)
    session.close()

    education_id = add_education(
        CANDIDATE_ID,
        institution="Lyon 2",
        degree="Master AEI",
    )

    update_education(education_id, end_year=2017)

    assert get_educations(CANDIDATE_ID)[0].end_year == 2017


def test_delete_education_la_retire_de_la_liste(session_factory):
    from services.profile_service import (
        add_education,
        delete_education,
        get_educations,
    )

    session = session_factory()
    add_candidate(session)
    session.close()

    education_id = add_education(
        CANDIDATE_ID,
        institution="Lyon 2",
        degree="Master AEI",
    )

    delete_education(education_id)

    assert get_educations(CANDIDATE_ID) == []


# ============================================================
# CERTIFICATION
# ============================================================

def test_add_certification_puis_relecture(session_factory):
    from services.profile_service import (
        add_certification,
        get_certifications,
    )

    session = session_factory()
    add_candidate(session)
    session.close()

    add_certification(
        candidate_id=CANDIDATE_ID,
        name="Professional Scrum Product Owner I (PSPO I)",
        organization="Scrum.org",
    )

    certifications = get_certifications(CANDIDATE_ID)

    assert len(certifications) == 1
    assert certifications[0].name == (
        "Professional Scrum Product Owner I (PSPO I)"
    )


def test_certification_ne_stocke_que_l_annee(session_factory):
    """
    Le mois d'obtention d'une certification n'est presque jamais
    connu : le champ ne conserve que l'année plutôt que d'imposer une
    date complète, ce qui forcerait à fabriquer un jour arbitraire.
    """

    from services.profile_service import (
        add_certification,
        get_certifications,
    )

    session = session_factory()
    add_candidate(session)
    session.close()

    add_certification(
        candidate_id=CANDIDATE_ID,
        name="Google Project Management Certificate",
        obtained_year=2026,
    )

    assert get_certifications(CANDIDATE_ID)[0].obtained_year == 2026


def test_delete_certification_la_retire_de_la_liste(
    session_factory,
):
    from services.profile_service import (
        add_certification,
        delete_certification,
        get_certifications,
    )

    session = session_factory()
    add_candidate(session)
    session.close()

    certification_id = add_certification(
        CANDIDATE_ID,
        name="PSPO I",
    )

    delete_certification(certification_id)

    assert get_certifications(CANDIDATE_ID) == []


# ============================================================
# SUPPRESSION D'UNE COMPETENCE
# ============================================================

def test_delete_skill_supprime_aussi_ses_preuves(session_factory):
    """
    Supprimer la compétence seule laisserait des preuves orphelines,
    que le moteur de matching continuerait de compter : la compétence
    resterait "prouvée" alors qu'elle n'existe plus.
    """

    from database.models import EvidenceDB
    from services.profile_service import (
        add_evidence,
        add_skill,
        delete_skill,
        get_skills,
    )

    session = session_factory()
    add_candidate(session)
    session.close()

    skill_id = add_skill(candidate_id=CANDIDATE_ID, name="Gestion de budget")

    add_evidence(
        candidate_id=CANDIDATE_ID,
        skill_id=skill_id,
        description="Budget de 50k€ piloté par trimestre.",
    )

    delete_skill(skill_id)

    assert get_skills(CANDIDATE_ID) == []

    session = session_factory()
    restantes = (
        session.query(EvidenceDB)
        .filter(EvidenceDB.skill_id == skill_id)
        .all()
    )
    session.close()

    assert restantes == []


def test_delete_skill_ne_touche_pas_aux_autres_competences(session_factory):
    from services.profile_service import add_skill, delete_skill, get_skills

    session = session_factory()
    add_candidate(session)
    session.close()

    a_supprimer = add_skill(candidate_id=CANDIDATE_ID, name="À supprimer")
    add_skill(candidate_id=CANDIDATE_ID, name="À conserver")

    delete_skill(a_supprimer)

    assert [s.name for s in get_skills(CANDIDATE_ID)] == ["À conserver"]


def test_delete_skill_sur_un_identifiant_inconnu_ne_leve_rien(
    session_factory,
):
    from services.profile_service import delete_skill

    session = session_factory()
    add_candidate(session)
    session.close()

    delete_skill("skill-inexistant")


# ============================================================
# DOCUMENTER UNE COMPETENCE DECLAREE
# ============================================================
#
# Une compétence déclarée sans preuve est classée « declared » : elle
# ne peut pas figurer comme compétence explicite sur un CV généré, et
# elle pèse moins face à une annonce qui la demande. Ce n'est pas un
# défaut du candidat — il a fait ces choses, il ne les a pas
# racontées.


def test_les_competences_sans_preuve_sont_listees(session_factory):

    from services.profile_service import get_undocumented_skills

    session = session_factory()

    add_candidate(session)

    prouvee = add_candidate_skill(
        session, candidate_id=CANDIDATE_ID, name="Gestion de projet"
    )

    add_evidence(
        session,
        candidate_id=CANDIDATE_ID,
        skill_id=prouvee.id,
        description="Refonte du tunnel d'achat.",
    )

    add_candidate_skill(
        session,
        candidate_id=CANDIDATE_ID,
        name="Veille concurrentielle",
        skill_id="skill-veille",
    )

    session.close()

    noms = [
        competence["name"]
        for competence in get_undocumented_skills(CANDIDATE_ID)
    ]

    assert noms == ["Veille concurrentielle"]


def test_les_competences_d_un_autre_profil_restent_dehors(
    session_factory,
):
    """
    Le cloisonnement par candidat vaut ici comme ailleurs : proposer
    à quelqu'un de documenter la compétence d'un autre profil serait
    une fuite de données, pas seulement une gêne.
    """

    from services.profile_service import get_undocumented_skills

    session = session_factory()

    add_candidate(session)
    add_candidate(session, candidate_id="candidate-autre")

    add_candidate_skill(
        session, candidate_id=CANDIDATE_ID, name="Veille"
    )
    add_candidate_skill(
        session,
        candidate_id="candidate-autre",
        name="Soudure TIG",
        skill_id="skill-soudure",
    )

    session.close()

    noms = [
        competence["name"]
        for competence in get_undocumented_skills(CANDIDATE_ID)
    ]

    assert noms == ["Veille"]


def test_une_preuve_validee_rend_la_competence_prouvee(
    session_factory,
):
    """
    Le bout du parcours : la preuve se rattache à la compétence
    DÉJÀ déclarée, qui passe de « declared » à « proven ». Sans
    cela, l'entretien créerait une jumelle et laisserait la déclarée
    orpheline.
    """

    from services.matching import analyze_candidate_against_skills
    from services.profile_service import (
        add_evidence as ajouter_preuve,
        add_skill,
        get_undocumented_skills,
    )

    session = session_factory()

    add_candidate(session)
    add_catalog_skill(
        session,
        canonical_name="Veille concurrentielle",
        aliases=["Veille concurrentielle"],
    )
    add_candidate_skill(
        session,
        candidate_id=CANDIDATE_ID,
        name="Veille concurrentielle",
    )

    session.close()

    avant = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Veille concurrentielle"],
    )

    assert avant.matches[0].status == "declared"

    # Ce que fait l'interface après validation : add_skill retrouve
    # la compétence existante plutôt que d'en créer une seconde.
    skill_id = add_skill(
        candidate_id=CANDIDATE_ID, name="Veille concurrentielle"
    )

    ajouter_preuve(
        candidate_id=CANDIDATE_ID,
        skill_id=skill_id,
        description=(
            "Veille hebdomadaire sur cinq concurrents, restituée en "
            "comité produit."
        ),
        evidence_type="Entretien IA (validé par le candidat)",
    )

    apres = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Veille concurrentielle"],
    )

    assert apres.matches[0].status == "proven"
    assert get_undocumented_skills(CANDIDATE_ID) == []
