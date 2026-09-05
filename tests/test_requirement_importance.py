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


def test_deux_fois_le_meme_texte_donnent_le_meme_niveau():
    """
    La propriété qu'on attend d'un score servant à comparer des
    annonces : la reproductibilité.

    Le niveau a d'abord été demandé à l'IA, le texte ne comblant que
    ses silences ; puis l'inverse. Ni l'un ni l'autre n'a suffi. Deux
    captures d'une même offre, dont les seules différences étaient
    des bandeaux de navigation, obtenaient 34,6 et 44,5 — parce que
    deux termes tombaient dans le silence de l'annonce, où l'IA
    décidait encore, et qu'elle n'a pas répondu deux fois pareil.

    L'IA est écartée du classement. Ce test verrouille la raison.
    """

    annonce = (
        "Chef de projet\n"
        "Vous interviendrez sur Docker et Kubernetes.\n"
        "La maîtrise de la gestion de projet est indispensable."
    )

    exigences = ["Docker", "Kubernetes", "Gestion de projet"]

    premier = classify_requirements(exigences, annonce)
    second = classify_requirements(exigences, annonce)

    assert premier == second

    # Et le silence de l'annonce donne le niveau médian, pas un avis.
    assert premier[normalise_terme("Docker")] == SOUHAITEE
    assert (
        premier[normalise_terme("Gestion de projet")] == ESSENTIELLE
    )


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


def test_le_silence_de_l_annonce_se_distingue_d_un_souhait():
    """
    Les deux donnent « souhaitée », mais pas au même titre : quand
    l'annonce se prononce, l'IA ne peut plus la contredire ; quand
    elle se tait, l'IA a la parole. Sans cette distinction, un
    « serait un plus » explicite se faisait promouvoir en condition
    d'entrée.
    """

    from services.requirement_importance import _lire_niveau

    assert (
        _lire_niveau("Figma", "La connaissance de Figma serait un plus.")
        == SOUHAITEE
    )

    assert _lire_niveau("Figma", "Vous travaillerez sur Figma.") is None


# ============================================================
# TITRES DE SECTION
# ============================================================
#
# Le classement ne se prononçait que sur 57 exigences du corpus de
# mesure sur 178. Trois causes, toutes corrigées ici : le titre de
# section ne portait que sur sa première puce, l'exigence était
# cherchée sous un nom que l'annonce n'emploie pas, et une liste
# manifeste était rejetée pour un seul membre bavard.


def test_un_titre_de_section_porte_sur_toutes_ses_puces():
    """
    Le défaut principal : la recherche du titre ne remontait que de
    deux lignes non vides. Dans une liste à puces — la forme la plus
    répandue dans une annonce — ces deux lignes sont les puces
    voisines, jamais le titre.
    """

    annonce = (
        "Votre profil :\n"
        "- Une première expérience en gestion de projet\n"
        "- La pratique de Docker au quotidien\n"
        "- Un goût prononcé pour Kubernetes\n"
    )

    assert classify_requirement("Kubernetes", annonce) == ESSENTIELLE


def test_un_titre_ne_porte_pas_indefiniment():
    """
    Un titre trouvé vingt puces plus haut ne qualifie plus rien : la
    remontée s'arrête.
    """

    annonce = "Votre profil :\n" + "".join(
        f"- Une ligne de remplissage numéro {indice}\n"
        for indice in range(20)
    ) + "- La pratique de Kubernetes\n"

    assert classify_requirement("Kubernetes", annonce) == SOUHAITEE


def test_une_puce_n_est_jamais_prise_pour_un_titre():

    from services.requirement_importance import _ressemble_a_un_titre

    assert _ressemble_a_un_titre("Votre profil :")
    assert _ressemble_a_un_titre("Hard skills")
    assert not _ressemble_a_un_titre("- Vous maîtrisez Docker")
    assert not _ressemble_a_un_titre("• Vous maîtrisez Docker")

    # Une phrase longue n'est pas un titre, sauf si elle annonce
    # explicitement ce qui suit.
    assert not _ressemble_a_un_titre(
        "Vous rejoindrez une équipe de douze personnes réparties "
        "sur trois sites en France"
    )
    assert _ressemble_a_un_titre(
        "Pour ce poste nous recherchons impérativement les "
        "compétences suivantes :"
    )


# ============================================================
# L'EXIGENCE SOUS UN AUTRE NOM
# ============================================================

def test_un_alias_permet_de_situer_l_exigence():
    """
    L'exigence porte le nom canonique du référentiel, l'annonce
    emploie le sien. Sans les alias, l'annonce restait muette sur 69
    exigences du corpus — non pas faute de le dire, mais faute qu'on
    sache où regarder.
    """

    annonce = "La maîtrise d'Agile est indispensable."

    # Le nom canonique ne figure pas dans l'annonce.
    assert classify_requirement("Agile / Scrum", annonce) == SOUHAITEE

    niveaux = classify_requirements(
        ["Agile / Scrum"],
        annonce,
        alias_par_terme={"Agile / Scrum": ("Agile", "Scrum")},
    )

    assert niveaux[normalise_terme("Agile / Scrum")] == ESSENTIELLE


def test_l_alias_le_plus_specifique_est_essaye_en_premier():
    """
    Un alias court tombe n'importe où ; le plus long désigne le
    passage qui parle vraiment de la compétence.
    """

    from services.requirement_importance import _lire_niveau

    annonce = (
        "Environnement : outils divers, tests, suivi, reporting.\n"
        "La maîtrise du test A/B est indispensable."
    )

    assert (
        _lire_niveau(
            "Experimentation", annonce, ("Tests", "test A/B")
        )
        == ESSENTIELLE
    )


# ============================================================
# UNE LISTE RESTE UNE LISTE
# ============================================================

def test_un_element_bavard_ne_disqualifie_pas_la_liste():
    """
    Relevé tel quel : « les principales plateformes du marché : CRM,
    CDP, CMS, solutions marketing automation et e-commerce ». Trois
    éléments courts, un long — la liste redevenait une exigence.
    """

    annonce = (
        "Vous maîtrisez :\n"
        "- les principales plateformes du marché : CRM, CDP, CMS, "
        "solutions marketing automation et e-commerce\n"
    )

    assert classify_requirement("CDP", annonce) == MENTION


def test_une_enumeration_l_emporte_sur_le_titre_de_section():
    """
    « Vous maîtrisez : » chapeaute la section entière, mais la puce
    qui aligne huit leviers séparés par des virgules et se termine
    par « etc » en dit plus long sur ces huit-là.
    """

    annonce = (
        "Vous maîtrisez :\n"
        "- les leviers de performance digitale : e-commerce, "
        "acquisition, fidélisation, social media, influence, "
        "web-to-store, mobile, e-réputation, etc\n"
    )

    assert classify_requirement("web-to-store", annonce) == MENTION


def test_une_liste_de_conditions_resiste_encore():
    """
    Le pendant : une énumération que rien n'annonce comme un exemple,
    dans une phrase qui la présente comme des conditions, reste une
    liste de conditions.
    """

    annonce = "Compétences requises : Python, Docker, SQL, Git."

    assert classify_requirement("Docker", annonce) == ESSENTIELLE
