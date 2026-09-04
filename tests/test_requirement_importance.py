"""
Niveau d'exigence lu dans l'annonce (services.requirement_importance).

Le moteur comptait toutes les exigences à égalité. Une annonce qui
écrit « environnement : Jira, Miro, GitLab, BaseCamp, Planner, TFS »
produisait six exigences manquantes, et le score s'effondrait sur une
énumération que l'annonce ne présente pas comme une condition.

Ces tests vérifient ce que le classement lit, et surtout ce qu'il
refuse de conclure : en cas de doute, « souhaitée ».
"""

from __future__ import annotations

from services.requirement_importance import (
    ESSENTIELLE,
    MENTION,
    SOUHAITEE,
    classify_requirement,
    classify_requirements,
    normalise_terme,
)


# ============================================================
# CONDITIONS D'ENTREE
# ============================================================

def test_une_maitrise_indispensable_est_une_condition():

    annonce = (
        "Chef de projet digital\n"
        "La maîtrise de la gestion de projet est indispensable."
    )

    assert (
        classify_requirement("gestion de projet", annonce)
        == ESSENTIELLE
    )


def test_un_prerequis_est_une_condition():

    annonce = "Prérequis : une expérience confirmée en SQL."

    assert classify_requirement("SQL", annonce) == ESSENTIELLE


def test_un_entete_de_section_qualifie_ce_qui_suit():
    """
    Une liste à puces ne répète pas « indispensable » à chaque ligne :
    le titre de section porte l'exigence pour tout le bloc.
    """

    annonce = (
        "Compétences requises :\n"
        "- Python\n"
        "- Docker\n"
    )

    assert classify_requirement("Docker", annonce) == ESSENTIELLE


# ============================================================
# SOUHAITS
# ============================================================

def test_un_plus_reste_un_souhait():

    annonce = "La connaissance de Figma serait un plus."

    assert classify_requirement("Figma", annonce) == SOUHAITEE


def test_un_souhait_l_emporte_sur_une_formule_d_exigence():
    """
    Le cœur du classement : « la maîtrise de X serait un plus »
    contient les deux marqueurs, et c'est le souhait qui décrit
    l'exigence réelle. Conclure « essentielle » gonflerait l'écart.
    """

    annonce = "La maîtrise de Kubernetes serait un vrai plus."

    assert classify_requirement("Kubernetes", annonce) == SOUHAITEE


# ============================================================
# SIMPLES MENTIONS
# ============================================================

def test_un_environnement_technique_n_est_pas_une_exigence():

    annonce = (
        "Environnement technique : Jira, Confluence, Miro.\n"
        "Vous piloterez les projets de bout en bout."
    )

    assert classify_requirement("Jira", annonce) == MENTION


def test_une_enumeration_d_outils_sans_entete_reste_une_mention():
    """
    Cas observé sur une annonce réelle : huit outils alignés, sans
    aucun marqueur de langage. La forme suffit à les reconnaître —
    beaucoup d'éléments, tous courts.
    """

    annonce = (
        "Vous travaillerez sur Jira, Miro, GitLab, BaseCamp, "
        "Planner, TFS, Clarity, MS Project."
    )

    assert classify_requirement("Clarity", annonce) == MENTION


def test_une_phrase_a_virgules_n_est_pas_une_enumeration():
    """
    Le garde-fou de la forme : une phrase séparée par des virgules
    n'est pas une liste d'outils, et ne doit pas déclasser ce qu'elle
    contient.
    """

    annonce = (
        "Vous pilotez la gestion de projet auprès des équipes "
        "internes, en lien avec les partenaires externes, sur "
        "l'ensemble du périmètre, du cadrage à la mise en "
        "production."
    )

    assert (
        classify_requirement("gestion de projet", annonce)
        == SOUHAITEE
    )


# ============================================================
# EN CAS DE DOUTE
# ============================================================

def test_sans_marqueur_le_niveau_reste_median():

    annonce = "Vous interviendrez sur des sujets de gestion de projet."

    assert (
        classify_requirement("gestion de projet", annonce)
        == SOUHAITEE
    )


def test_un_terme_absent_de_l_annonce_ne_gonfle_rien():
    """
    Le catalogue peut détecter une compétence via un alias : le
    libellé canonique n'apparaît alors pas tel quel dans l'annonce.
    Aucune conclusion n'est tirée dans ce cas.
    """

    assert (
        classify_requirement("Kubernetes", "Une annonce sans ce mot.")
        == SOUHAITEE
    )


def test_sans_texte_d_annonce_le_niveau_reste_median():

    assert classify_requirement("SQL", "") == SOUHAITEE


# ============================================================
# LECTURE DU TERME DANS LE TEXTE
# ============================================================

def test_les_accents_et_la_casse_ne_font_pas_echouer_la_lecture():

    annonce = "La maîtrise de la Gestion De Projet est obligatoire."

    assert (
        classify_requirement("gestion de projet", annonce)
        == ESSENTIELLE
    )


def test_un_mot_plus_long_ne_declenche_pas_la_lecture():
    """
    « R » ne doit pas être lu dans « marketing ». Sans frontière de
    mot, tout terme court hériterait du niveau de n'importe quelle
    phrase.
    """

    annonce = "Environnement : marketing digital et communication."

    # Aucune occurrence isolée de « R » : rien n'est conclu.
    assert classify_requirement("R", annonce) == SOUHAITEE


def test_un_separateur_entre_les_mots_est_tolere():

    annonce = "Compétences requises : la gestion-de-projet."

    assert (
        classify_requirement("gestion de projet", annonce)
        == ESSENTIELLE
    )


# ============================================================
# CLASSEMENT D'UNE LISTE
# ============================================================

def test_chaque_exigence_recoit_son_niveau():

    annonce = (
        "Compétences requises : gestion de projet.\n"
        "Environnement : Jira, Confluence, Miro, Notion.\n"
        "La connaissance de Figma serait un plus."
    )

    niveaux = classify_requirements(
        ["Gestion de projet", "Jira", "Figma"],
        annonce,
    )

    assert niveaux[normalise_terme("Gestion de projet")] == ESSENTIELLE
    assert niveaux[normalise_terme("Jira")] == MENTION
    assert niveaux[normalise_terme("Figma")] == SOUHAITEE


def test_une_proposition_de_l_ia_est_retenue():
    """
    L'IA lit mieux le découpage en sections qu'une recherche de
    marqueurs : sa proposition prime quand elle est exploitable.
    """

    niveaux = classify_requirements(
        ["Docker"],
        "Vous interviendrez sur Docker.",
        hints={"Docker": ESSENTIELLE},
    )

    assert niveaux[normalise_terme("Docker")] == ESSENTIELLE


def test_une_proposition_hors_des_valeurs_connues_est_ecartee():
    """
    Même garde-fou que pour le type de contrat : une valeur inventée
    par l'IA n'est jamais réinterprétée, le classement déterministe
    reprend la main.
    """

    annonce = "Environnement : Jira, Confluence, Miro, Notion."

    niveaux = classify_requirements(
        ["Jira"],
        annonce,
        hints={"Jira": "critique"},
    )

    assert niveaux[normalise_terme("Jira")] == MENTION


# ============================================================
# LISTES D'ALTERNATIVES
# ============================================================
#
# Ces deux cas viennent d'annonces réelles du corpus. Ils ont fait
# baisser le score au lieu de le corriger tant que le marqueur
# d'exigence l'emportait sur la forme de la liste.


def test_une_alternative_annoncee_ne_fait_pas_dix_conditions():
    """
    « un ou plusieurs » : l'annonce demande UN outil parmi dix, pas
    les dix. Compter dix conditions non couvertes là où l'annonce
    n'en pose qu'une fausse le score dans le mauvais sens.
    """

    annonce = (
        "Vous maîtrisez un ou plusieurs outils de gestion de "
        "projet : Jira, Confluence, Trello, Miro, GitLab, BaseCamp, "
        "Planner, TFS, Clarity, MS Project."
    )

    assert classify_requirement("Miro", annonce) == MENTION


def test_une_parenthese_d_exemples_ne_fait_pas_des_conditions():

    annonce = (
        "Maîtrise des principaux outils digitaux (Google Ads, "
        "Google Analytics, Meta Ads, WordPress, Pack Adobe)."
    )

    assert classify_requirement("WordPress", annonce) == MENTION


def test_ce_qui_introduit_la_liste_reste_une_condition():
    """
    Le pendant du test précédent : dans « vous maîtrisez un ou
    plusieurs outils de gestion de projet : ... », la gestion de
    projet, elle, est bien exigée. Elle précède l'ouverture de la
    liste — elle ne doit pas être déclassée avec son contenu.
    """

    annonce = (
        "Vous maîtrisez un ou plusieurs outils de gestion de "
        "projet : Jira, Confluence, Trello, Miro, GitLab, BaseCamp."
    )

    assert (
        classify_requirement("gestion de projet", annonce)
        == ESSENTIELLE
    )


def test_une_liste_de_conditions_reste_une_liste_de_conditions():
    """
    Toute énumération n'est pas illustrative : « Compétences
    requises : » n'annonce ni exemple ni alternative.
    """

    annonce = "Compétences requises : Python, Docker, SQL, Git."

    assert classify_requirement("Docker", annonce) == ESSENTIELLE


def test_des_points_de_suspension_ne_coupent_pas_la_liste():
    """
    Régression : normaliser en NFKD réécrivait « … » en trois points,
    et la fenêtre de phrase se coupait au premier. La liste perdait
    son dernier élément, cessait d'être reconnue comme énumération,
    et Jira redevenait une condition d'entrée.

    Cas relevé tel quel sur l'annonce « CHEF DE PROJETS PLATEFORME
    E-COMMERCE ».
    """

    annonce = (
        "Maîtrise des outils produits (Jira, Confluence, Figma, …)."
    )

    assert classify_requirement("Jira", annonce) == MENTION
