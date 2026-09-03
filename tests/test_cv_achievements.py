"""
Mise en ligne de CV d'une réalisation (services.cv.achievements).

Le Master CV range les chiffres du parcours dans les réalisations —
aucune preuve n'en porte. La composition doit donc les faire ressortir
sans les répéter deux fois dans la même puce.
"""

from __future__ import annotations

from services.cv.achievements import (
    achievement_source_text,
    build_achievement_line,
    is_redundant,
)


# Données réelles du Master CV, en plus court.
RESULTAT_CHIFFRE = (
    "Marge publicitaire passée d'environ 1,4 M€ à environ 2,5 M€ "
    "sur la période."
)

METRIQUES_MARGE = (
    "≈ 1,4 M€ de marge à l'arrivée\n"
    "≈ 2,5 M€ de marge lors de la dernière année\n"
    "≈ +79 % sur 7 ans"
)

METRIQUES_AUTOMATISATION = (
    "30 à 60 minutes avant automatisation\n"
    "2 à 5 minutes après automatisation\n"
    "≈ 90 % de réduction du temps de traitement"
)


# ============================================================
# COMPOSITION
# ============================================================

def test_le_titre_et_le_resultat_composent_la_puce():
    titre, detail = build_achievement_line(
        "Structuration de l'offre publicitaire digitale",
        RESULTAT_CHIFFRE,
    )

    assert titre == "Structuration de l'offre publicitaire digitale"
    assert detail.startswith("marge publicitaire passée")


def test_un_pourcentage_est_prefere_parmi_les_metriques():
    """
    C'est la forme qui frappe le plus à la lecture — et ici, la seule
    métrique qui n'était pas déjà dans le résultat.
    """

    _titre, detail = build_achievement_line(
        "Structuration de l'offre publicitaire digitale",
        RESULTAT_CHIFFRE,
        METRIQUES_MARGE,
    )

    assert "+79 %" in detail


def test_une_metrique_deja_dans_le_resultat_n_est_pas_repetee():
    _titre, detail = build_achievement_line(
        "Création d'un produit serviciel post-achat",
        "Environ 100 k€ de chiffre d'affaires sur les 18 premiers mois.",
        "≈ 100 k€ de CA sur 18 mois",
    )

    assert detail.count("100") == 1


def test_un_resultat_vague_est_precise_par_sa_metrique():
    """
    « Réduction importante du temps de traitement » ne dit rien ;
    « ≈ 90 % » dit tout.
    """

    _titre, detail = build_achievement_line(
        "Automatisation des ordres d'insertion",
        "Réduction importante du temps nécessaire au traitement.",
        METRIQUES_AUTOMATISATION,
    )

    assert "90 %" in detail


def test_une_realisation_sans_resultat_garde_son_titre():
    titre, detail = build_achievement_line(
        "Monétisation des supports ticketis.fr"
    )

    assert titre == "Monétisation des supports ticketis.fr"
    assert detail == ""


def test_un_sigle_en_tete_de_resultat_reste_en_majuscules():
    _titre, detail = build_achievement_line(
        "Suivi des campagnes",
        "KPI suivis chaque semaine.",
    )

    assert detail.startswith("KPI")


def test_le_point_final_disparait_devant_une_parenthese():
    _titre, detail = build_achievement_line(
        "Structuration de l'offre publicitaire digitale",
        RESULTAT_CHIFFRE,
        METRIQUES_MARGE,
    )

    assert ". (" not in detail


# ============================================================
# DOUBLONS
# ============================================================

def test_une_realisation_qui_repete_une_puce_est_redondante():
    """
    Cas réel : la réalisation disait moins bien ce que la puce disait
    déjà, et les deux se suivaient sur le CV.
    """

    assert is_redundant(
        "Monétisation des supports ticketis.fr",
        "suivi opérationnel du bon déroulement des campagnes.",
        [
            "Participation à la monétisation des supports ticketis.fr : "
            "display on-site, extension d'audience et asile colis."
        ],
    )


def test_une_realisation_chiffree_n_est_jamais_redondante():
    """
    Le chiffre est précisément ce que la puce n'a pas.
    """

    assert not is_redundant(
        "Monétisation des supports ticketis.fr",
        "environ 100 k€ de CA sur 18 mois",
        [
            "Participation à la monétisation des supports ticketis.fr : "
            "display on-site."
        ],
    )


def test_une_realisation_distincte_est_conservee():
    assert not is_redundant(
        "Pilotage de campagnes emailing d'acquisition",
        "analyse des résultats et amélioration continue.",
        ["Géré des comptes axés sur l'e-mailing d'acquisition."],
    )


def test_la_composition_n_invente_aucun_chiffre():
    """
    Tous les chiffres de la puce viennent du Master CV : c'est ce que
    le validateur vérifiera ensuite.
    """

    from services.text_numbers import numbers_in

    titre, detail = build_achievement_line(
        "Structuration de l'offre publicitaire digitale",
        RESULTAT_CHIFFRE,
        METRIQUES_MARGE,
    )

    source = achievement_source_text(
        "Structuration de l'offre publicitaire digitale",
        "",
        "",
        RESULTAT_CHIFFRE,
        METRIQUES_MARGE,
    )

    assert numbers_in(f"{titre} {detail}") <= numbers_in(source)
