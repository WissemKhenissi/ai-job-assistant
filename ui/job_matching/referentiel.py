"""
Onglet "Référentiel" : les termes d'annonce que le système ne connaît
pas encore, et ce que l'utilisateur décide d'en faire.

Le référentiel pilote le matching, le vocabulaire autorisé à la
rédaction et le tri des exigences. Livré figé, il ne couvre que les
métiers prévus par son auteur. Cet onglet est la boucle qui lui permet
de grandir : chaque analyse d'annonce y dépose les termes inconnus,
l'utilisateur tranche.

Trois décisions, jamais prises automatiquement :

- **Rattacher** : l'annonce nomme autrement une compétence déjà
  connue. C'est le cas le plus fréquent.
- **Créer** : le terme désigne une compétence que le référentiel
  ignore — le seul moyen d'ouvrir l'outil à un nouveau métier.
- **Ignorer** : ce n'est pas une compétence.

Créer une compétence, c'est affirmer qu'un terme en désigne une. Cette
affirmation revient à l'utilisateur, pas à la machine.
"""

from __future__ import annotations

import streamlit as st

from services.ai.gemini_client import is_configured as ai_is_configured
from services.ai.skill_proposal import propose_catalog_entry
from services.job_service import get_job_offer_text

from services.skill_candidate_service import (
    INTEGRE,
    RATTACHE,
    attach_as_alias,
    get_candidates,
    ignore_candidate,
    promote_to_catalog,
    undo_decision,
)
from services.skill_catalog_service import get_active_skills


def _categories_existantes(competences) -> list[str]:
    """
    Les catégories réellement présentes au référentiel.

    Volontairement pas une liste figée : elle refléterait les métiers
    prévus à la livraison, et l'outil doit pouvoir servir un candidat
    dont le métier n'y figure pas.
    """

    return sorted(
        {
            competence.category.strip()
            for competence in competences
            if competence.category and competence.category.strip()
        }
    )


def _contexte_du_terme(candidat: dict) -> str:
    """
    Extrait de l'annonce où le terme est apparu.

    Un sigle n'a pas le même sens partout : « CDP » désigne une
    Customer Data Platform dans une annonce marketing, autre chose
    ailleurs. Sans contexte, la proposition serait un pari.
    """

    identifiants = candidat.get("job_offer_ids") or []

    if not identifiants:
        return ""

    try:
        texte = get_job_offer_text(identifiants[0])

    except Exception:
        return ""

    if not texte:
        return ""

    position = texte.casefold().find(candidat["term"].casefold())

    if position < 0:
        return texte[:600]

    return texte[max(0, position - 300) : position + 300]


def _rendre_proposition(identifiant: str, proposition) -> bool:
    """
    Affiche ce que l'IA propose. Retourne True si un rattachement
    proposé a été appliqué.
    """

    if proposition is None:
        return False

    if proposition.reasoning:
        st.caption(f"💡 {proposition.reasoning}")

    if proposition.warning:
        st.warning(proposition.warning)

    if not proposition.attach_to_id:
        return False

    st.info(
        f"L'IA estime que ce terme désigne « "
        f"{proposition.attach_to_name} », déjà au référentiel. "
        "Mieux vaut l'y rattacher que créer un doublon."
    )

    if st.button(
        f"🔗 Rattacher à « {proposition.attach_to_name} »",
        key=f"proposition_rattacher_{identifiant}",
        type="primary",
        use_container_width=True,
    ):
        attach_as_alias(identifiant, proposition.attach_to_id)
        st.session_state.pop(f"proposition_{identifiant}", None)
        return True

    return False


def _defauts_du_formulaire(candidat: dict, proposition) -> dict:
    """
    Valeurs initiales du formulaire de création.

    `version` change dès qu'une proposition arrive : sans cela,
    Streamlit conserverait la saisie précédente et la proposition
    resterait invisible.
    """

    if proposition is None or not proposition.canonical_name:
        return {
            "nom": candidat["term"],
            "categorie": "",
            "alias": "",
            "description": "",
            "version": "manuel",
        }

    autres = [
        alias
        for alias in proposition.aliases
        if alias.casefold() != proposition.canonical_name.casefold()
    ]

    return {
        "nom": proposition.canonical_name,
        "categorie": proposition.category,
        "alias": "\n".join(autres),
        "description": proposition.description,
        "version": f"ia-{abs(hash(proposition.canonical_name))}",
    }


def _rendre_un_terme(
    candidat: dict,
    competences,
    categories: list[str],
) -> bool:
    """Affiche un terme et ses trois issues. Retourne True si traité."""

    identifiant = candidat["id"]

    entete = f"**{candidat['term']}**"

    if candidat["occurrences"] > 1:
        entete += f" — vu {candidat['occurrences']} fois"

    if not candidat["was_counted"]:
        entete += " — écarté du décompte"

    st.markdown(entete)

    col_rattacher, col_creer, col_ignorer = st.columns([3, 3, 1])

    traite = False

    # ----------------------------------------------------------
    # RATTACHER A UNE COMPETENCE EXISTANTE
    # ----------------------------------------------------------

    with col_rattacher:

        with st.popover("🔗 Rattacher", use_container_width=True):

            st.caption(
                "L'annonce nomme autrement une compétence que le "
                "référentiel connaît déjà."
            )

            choix = st.selectbox(
                "Compétence",
                options=[item.id for item in competences],
                format_func=lambda cle: _libelle(competences, cle),
                key=f"rattacher_choix_{identifiant}",
                label_visibility="collapsed",
            )

            if st.button(
                "Rattacher",
                key=f"rattacher_{identifiant}",
                type="primary",
                use_container_width=True,
            ):
                attach_as_alias(identifiant, choix)
                traite = True

    # ----------------------------------------------------------
    # CREER UNE COMPETENCE
    # ----------------------------------------------------------

    with col_creer:

        with st.popover("➕ Créer", use_container_width=True):

            st.caption(
                "Le terme désigne une compétence que le référentiel "
                "ignore. C'est ce qui ouvre l'outil à un métier qu'il "
                "ne couvrait pas."
            )

            proposition = st.session_state.get(
                f"proposition_{identifiant}"
            )

            if st.button(
                "✨ Demander une proposition à l'IA",
                key=f"proposer_{identifiant}",
                use_container_width=True,
                disabled=not ai_is_configured(),
            ):
                with st.spinner("Analyse du terme..."):
                    proposition = propose_catalog_entry(
                        candidat["term"],
                        context=_contexte_du_terme(candidat),
                    )

                st.session_state[f"proposition_{identifiant}"] = (
                    proposition
                )

            if not ai_is_configured():
                st.caption(
                    "Clé GEMINI_API_KEY absente : remplissez le "
                    "formulaire à la main."
                )

            if _rendre_proposition(identifiant, proposition):
                traite = True

            defauts = _defauts_du_formulaire(candidat, proposition)

            nom = st.text_input(
                "Nom de la compétence",
                value=defauts["nom"],
                key=f"creer_nom_{identifiant}_{defauts['version']}",
            )

            categorie = st.text_input(
                "Catégorie",
                value=defauts["categorie"],
                key=(
                    f"creer_categorie_{identifiant}"
                    f"_{defauts['version']}"
                ),
                help=(
                    "Catégories déjà utilisées : "
                    + (", ".join(categories) if categories else "aucune")
                ),
            )

            alias_saisis = st.text_area(
                "Autres façons de nommer cette compétence "
                "(une par ligne)",
                value=defauts["alias"],
                key=f"creer_alias_{identifiant}_{defauts['version']}",
                height=90,
            )

            deductible = st.checkbox(
                "Cette compétence peut être déduite d'un parcours",
                value=True,
                key=(
                    f"creer_deductible_{identifiant}"
                    f"_{defauts['version']}"
                ),
                help=(
                    "Un savoir-faire se devine du récit d'une "
                    "expérience. Un outil, une technologie ou un "
                    "corpus de connaissances non : décochez pour "
                    "« Jira », « Python » ou « droit du travail », "
                    "que le moteur ne devra jamais supposer."
                ),
            )

            if st.button(
                "Créer",
                key=f"creer_{identifiant}",
                type="primary",
                use_container_width=True,
            ):
                try:
                    promote_to_catalog(
                        identifiant,
                        canonical_name=nom,
                        category=categorie,
                        description=defauts["description"],
                        aliases=[
                            ligne.strip()
                            for ligne in alias_saisis.splitlines()
                            if ligne.strip()
                        ],
                        is_inferable=deductible,
                    )
                    st.session_state.pop(
                        f"proposition_{identifiant}", None
                    )
                    traite = True

                except ValueError as erreur:
                    st.error(str(erreur))

    # ----------------------------------------------------------
    # IGNORER
    # ----------------------------------------------------------

    with col_ignorer:

        if st.button(
            "🗑️",
            key=f"ignorer_{identifiant}",
            help="Ce n'est pas une compétence",
            use_container_width=True,
        ):
            ignore_candidate(identifiant)
            traite = True

    return traite


def _libelle(competences, identifiant: str) -> str:

    for item in competences:
        if item.id == identifiant:
            return (
                f"{item.canonical_name}"
                + (f" ({item.category})" if item.category else "")
            )

    return identifiant


def _decrire_decision(candidat: dict) -> str:

    if candidat["status"] == RATTACHE:
        return (
            f"rattaché à **{candidat['resolved_skill_name']}**"
            if candidat["resolved_skill_name"]
            else "rattaché"
        )

    if candidat["status"] == INTEGRE:
        return (
            f"créé comme **{candidat['resolved_skill_name']}**"
            if candidat["resolved_skill_name"]
            else "créé"
        )

    return "ignoré"


def _rendre_les_traites() -> None:
    """
    Les décisions déjà prises, avec leur marche arrière.

    Une décision de vocabulaire se prend sur un terme sorti de son
    contexte : se tromper est facile, et une erreur sans retour
    resterait dans le référentiel indéfiniment.
    """

    traites = [
        item
        for item in get_candidates(only_pending=False)
        if item["status"] != "nouveau"
    ]

    if not traites:
        return

    with st.expander(f"Décisions prises ({len(traites)})"):

        for candidat in traites:

            col_terme, col_annuler = st.columns([5, 1])

            with col_terme:
                st.markdown(
                    f"**{candidat['term']}** — "
                    f"{_decrire_decision(candidat)}"
                )

            with col_annuler:

                if st.button(
                    "↩️",
                    key=f"annuler_{candidat['id']}",
                    help="Annuler cette décision",
                    use_container_width=True,
                ):
                    message = undo_decision(candidat["id"])
                    st.session_state["referentiel_message"] = message
                    st.rerun()


def _rendre_attribution() -> None:
    """
    Attribution exigée par la licence du référentiel importé.

    ESCO est publiée sous CC BY 4.0 : la réutilisation est libre, le
    crédit est obligatoire. Il est affiché ici plutôt que caché dans
    un fichier — c'est sur cette page que le référentiel se regarde.
    """

    from database.db import SessionLocal
    from database.models import SkillCatalogDB

    session = SessionLocal()

    try:
        importees = (
            session.query(SkillCatalogDB)
            .filter(SkillCatalogDB.id.like("esco-%"))
            .count()
        )

    finally:
        session.close()

    if not importees:
        return

    st.caption(
        f"{importees} compétences proviennent d'**ESCO** "
        "(European Skills, Competences, Qualifications and "
        "Occupations), publiée par la Commission européenne sous "
        "licence [CC BY 4.0]"
        "(https://creativecommons.org/licenses/by/4.0/)."
    )


def render_referentiel_tab() -> None:

    st.write(
        "Les termes rencontrés dans vos annonces que le référentiel "
        "ne reconnaît pas encore."
    )

    st.caption(
        "Un terme inconnu n'est pas une compétence qui vous manque : "
        "c'est un trou du référentiel. Tant qu'il y reste, l'annonce "
        "qui l'emploie compte une exigence que rien ne peut couvrir, "
        "et la rédaction s'interdit ce mot."
    )

    _rendre_attribution()

    message = st.session_state.pop("referentiel_message", "")

    if message:
        st.success(message)

    candidats = get_candidates()

    if not candidats:

        st.success(
            "Rien à trier : toutes les exigences rencontrées sont "
            "reconnues par le référentiel."
        )

        _rendre_les_traites()

        return

    competences = get_active_skills()
    categories = _categories_existantes(competences)

    st.info(
        f"{len(candidats)} terme(s) à trier. Après un ajout, "
        "relancez l'analyse des annonces concernées pour en voir "
        "l'effet sur votre score."
    )

    for candidat in candidats:

        with st.container(border=True):

            if _rendre_un_terme(
                candidat, competences, categories
            ):
                st.rerun()

    _rendre_les_traites()
