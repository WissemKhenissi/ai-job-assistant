"""
Masquage des sections qui n'énoncent aucune exigence.

Une annonce ne demande rien dans ses paragraphes d'avantages, de
rémunération ou de déroulé d'entretien. Le moteur les lisait pourtant
comme le reste : sur le jeu d'évaluation, « ski » venait d'un week-end
au ski et « évènements sportifs » du paragraphe sur la vie
d'entreprise.

Ces tests verrouillent les trois propriétés qui rendent le masquage
sûr : il conserve les positions, il ne coupe que sur un intitulé
reconnu, et un intitulé d'exigence le referme.
"""

from __future__ import annotations

from services.job_requirements_service import (
    masquer_sections_hors_exigence,
)


def test_la_longueur_du_texte_est_conservee():
    """
    La propriété la plus importante, et la moins visible.

    Les positions portent l'ordre d'apparition, dont dépendent la
    pondération par rang et la fenêtre de lecture du niveau
    d'exigence. Retirer les caractères au lieu de les blanchir
    décalerait tout ce qui suit, en silence.
    """

    texte = (
        "Votre profil\n"
        "Vous maîtrisez Python.\n"
        "Nos avantages\n"
        "Un week-end Ski chaque hiver.\n"
    )

    masque = masquer_sections_hors_exigence(texte)

    assert len(masque) == len(texte)

    for ligne_masquee, ligne in zip(
        masque.split("\n"), texte.split("\n")
    ):
        assert len(ligne_masquee) == len(ligne)


def test_une_section_d_avantages_est_masquee_jusqu_a_la_fin():

    texte = (
        "Votre profil\n"
        "Vous maîtrisez Python.\n"
        "Nos avantages\n"
        "Un week-end Ski chaque hiver.\n"
        "Des évènements sportifs.\n"
    )

    masque = masquer_sections_hors_exigence(texte)

    assert "Python" in masque
    assert "Ski" not in masque
    assert "sportifs" not in masque


def test_un_intitule_d_exigence_referme_la_section():
    """
    Une annonce qui place ses avantages au milieu ne doit pas perdre
    tout ce qui suit.
    """

    texte = (
        "Nos avantages\n"
        "Un week-end Ski chaque hiver.\n"
        "Votre profil\n"
        "Vous maîtrisez Python.\n"
    )

    masque = masquer_sections_hors_exigence(texte)

    assert "Ski" not in masque
    assert "Python" in masque


def test_un_intitule_inconnu_ne_masque_rien():
    """
    L'erreur va vers la lecture complète, jamais vers la coupe à
    l'aveugle.
    """

    texte = (
        "Un titre que personne n'a prévu\n"
        "Vous maîtrisez Python.\n"
    )

    assert masquer_sections_hors_exigence(texte) == texte


def test_une_phrase_qui_parle_d_avantages_n_est_pas_un_intitule():
    """
    Seule une ligne courte se lit comme un titre de section. Une
    phrase entière qui contient le mot ne doit rien déclencher.
    """

    texte = (
        "Vous présenterez les avantages de la solution aux clients "
        "grands comptes de la région.\n"
        "Vous maîtrisez Python.\n"
    )

    assert masquer_sections_hors_exigence(texte) == texte


def test_une_puce_n_est_pas_un_intitule():
    """
    Dans une liste, « - Avantages » est un élément, pas un titre.
    """

    texte = (
        "- Avantages négociés avec nos partenaires\n"
        "Vous maîtrisez Python.\n"
    )

    assert masquer_sections_hors_exigence(texte) == texte


def test_le_process_de_recrutement_est_masque():

    texte = (
        "Votre profil\n"
        "Vous maîtrisez Python.\n"
        "Notre process de recrutement\n"
        "Un entretien technique en visio avec deux managers.\n"
    )

    masque = masquer_sections_hors_exigence(texte)

    assert "Python" in masque
    assert "entretien technique" not in masque


def test_un_texte_vide_est_rendu_tel_quel():

    assert masquer_sections_hors_exigence("") == ""
