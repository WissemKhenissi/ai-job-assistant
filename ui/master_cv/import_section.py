"""
Import d'un CV pour amorcer le Master CV.

Sans cette porte d'entrée, un nouvel utilisateur doit tout ressaisir à
la main — expérience par expérience, preuve par preuve. Personne ne le
fait, et tout le reste de l'outil reste hors d'atteinte.

Le parcours est en trois temps, et le troisième n'arrive jamais tout
seul :

1. déposer le CV (.pdf ou .docx) ;
2. **relire** ce que l'IA en a tiré, décocher ce qui est faux ;
3. importer ce qui reste.

Rien n'est écrit avant le clic final. Ce que cette étape produit
devient le Master CV, c'est-à-dire la source de vérité de tout le
reste : une erreur acceptée ici serait tenue pour vraie partout
ensuite.
"""

from __future__ import annotations

from dataclasses import replace

import streamlit as st

from services.ai.gemini_client import is_configured as ai_is_configured
from services.ai.profile_extraction import extract_profile_from_cv
from services.document_extraction import extract_text_from_upload
from services.profile_import_service import import_profile


ETAT = "import_cv_profil"


SANS_COMPETENCE = "— aucune —"


def _rendre_experience(experience, indice: int, competences: list[str]):
    """
    Une expérience et ses puces, à cocher. Retourne l'expérience
    réduite à ce qui reste coché, ou None si elle est refusée.

    Chaque puce porte le choix de la compétence qu'elle démontre. Ce
    n'est pas un détail : une puce sans compétence ne devient pas une
    preuve, et sur un CV réel l'IA en laisse volontiers la moitié
    sans rattachement, faute d'oser choisir. C'est au candidat de
    trancher — lui sait ce que sa ligne démontre.
    """

    periode = " – ".join(
        partie
        for partie in (
            experience.start_date.strftime("%m/%Y")
            if experience.start_date
            else "?",
            experience.end_date.strftime("%m/%Y")
            if experience.end_date
            else "en cours",
        )
        if partie
    )

    retenue = st.checkbox(
        f"**{experience.label}** — {periode}",
        value=bool(experience.start_date),
        key=f"import_exp_{indice}",
    )

    if not retenue:
        return None

    if experience.start_date is None:
        st.warning(
            "Sans date de début, cette expérience ne peut pas être "
            "importée : complétez-la à la main après l'import."
        )
        return None

    options = [SANS_COMPETENCE, *competences]

    lignes = []

    for rang, ligne in enumerate(experience.lines):

        col_texte, col_competence = st.columns([3, 2])

        with col_texte:
            retenue_ligne = st.checkbox(
                ligne.text,
                value=True,
                key=f"import_ligne_{indice}_{rang}",
            )

        with col_competence:

            defaut = (
                options.index(ligne.skill)
                if ligne.skill in options
                else 0
            )

            choix = st.selectbox(
                "Compétence démontrée",
                options=options,
                index=defaut,
                key=f"import_skill_{indice}_{rang}",
                label_visibility="collapsed",
            )

        if not retenue_ligne:
            continue

        if choix == SANS_COMPETENCE:
            st.caption(
                "↳ sans compétence, cette ligne ne deviendra pas "
                "une preuve et restera invisible du moteur."
            )
            continue

        lignes.append(replace(ligne, skill=choix))

    return replace(experience, lines=tuple(lignes))


def _rendre_relecture(profil, candidate_id: str) -> None:

    st.success(
        "CV lu. **Relisez ci-dessous avant d'importer** : tout ce qui "
        "reste coché sera écrit dans votre Master CV."
    )

    for avertissement in profil.warnings:
        st.warning(avertissement)

    # ----------------------------------------------------------
    # IDENTITE
    # ----------------------------------------------------------

    with st.expander("Identité et profil", expanded=True):

        col_gauche, col_droite = st.columns(2)

        with col_gauche:
            prenom = st.text_input(
                "Prénom", value=profil.first_name, key="import_prenom"
            )
            email = st.text_input(
                "Email", value=profil.email, key="import_email"
            )
            lieu = st.text_input(
                "Localisation", value=profil.location, key="import_lieu"
            )

        with col_droite:
            nom = st.text_input(
                "Nom", value=profil.last_name, key="import_nom"
            )
            telephone = st.text_input(
                "Téléphone", value=profil.phone, key="import_tel"
            )
            lien = st.text_input(
                "LinkedIn", value=profil.linkedin_url, key="import_lien"
            )

        accroche = st.text_input(
            "Accroche", value=profil.headline, key="import_accroche"
        )

        resume = st.text_area(
            "Résumé", value=profil.summary, key="import_resume", height=90
        )

        langues = st.text_input(
            "Langues", value=profil.languages, key="import_langues"
        )

    # ----------------------------------------------------------
    # COMPETENCES
    # ----------------------------------------------------------
    #
    # Choisies avant les expériences : chaque puce doit pouvoir
    # désigner celle qu'elle démontre.

    competences = st.multiselect(
        "Compétences",
        options=list(profil.skills),
        default=list(profil.skills),
        key="import_competences",
    )

    # ----------------------------------------------------------
    # EXPERIENCES
    # ----------------------------------------------------------

    experiences = []

    if profil.experiences:

        st.markdown("**Expériences**")

        for indice, experience in enumerate(profil.experiences):

            with st.container(border=True):

                retenue = _rendre_experience(
                    experience, indice, competences
                )

                if retenue is not None:
                    experiences.append(retenue)

    # ----------------------------------------------------------
    # FORMATION ET CERTIFICATIONS
    # ----------------------------------------------------------

    formations = []

    if profil.educations:

        with st.expander(f"Formation ({len(profil.educations)})"):

            for indice, formation in enumerate(profil.educations):

                if st.checkbox(
                    f"{formation.degree} — {formation.institution}",
                    value=True,
                    key=f"import_formation_{indice}",
                ):
                    formations.append(formation)

    certifications = []

    if profil.certifications:

        with st.expander(
            f"Certifications ({len(profil.certifications)})"
        ):

            for indice, certification in enumerate(
                profil.certifications
            ):

                if st.checkbox(
                    certification.name,
                    value=True,
                    key=f"import_certif_{indice}",
                ):
                    certifications.append(certification)

    # ----------------------------------------------------------
    # ECRITURE
    # ----------------------------------------------------------

    st.divider()

    ecraser = st.checkbox(
        "Remplacer les informations déjà présentes dans mon profil",
        value=False,
        key="import_ecraser",
        help=(
            "Par défaut, l'import ne complète que les champs vides : "
            "ce que vous avez saisi à la main est conservé."
        ),
    )

    col_importer, col_annuler = st.columns([3, 1])

    with col_importer:

        if st.button(
            "Importer dans mon Master CV",
            type="primary",
            use_container_width=True,
        ):

            a_importer = replace(
                profil,
                first_name=prenom,
                last_name=nom,
                email=email,
                phone=telephone,
                location=lieu,
                linkedin_url=lien,
                headline=accroche,
                summary=resume,
                languages=langues,
                experiences=tuple(experiences),
                skills=tuple(competences),
                educations=tuple(formations),
                certifications=tuple(certifications),
            )

            resume_import = import_profile(
                candidate_id,
                a_importer,
                overwrite_identity=ecraser,
            )

            st.session_state.pop(ETAT, None)
            st.session_state["import_cv_resume"] = resume_import
            st.rerun()

    with col_annuler:

        if st.button("Annuler", use_container_width=True):
            st.session_state.pop(ETAT, None)
            st.rerun()


def _rendre_resultat(resume) -> None:

    st.success(
        f"Import terminé : {resume.experiences} expérience(s), "
        f"{resume.lines} preuve(s), {resume.skills} compétence(s), "
        f"{resume.educations} formation(s), "
        f"{resume.certifications} certification(s)."
    )

    if resume.fields_filled:
        st.caption(
            "Champs de profil complétés : "
            + ", ".join(resume.fields_filled)
        )

    if resume.skipped:

        with st.expander(f"Non importé ({len(resume.skipped)})"):
            for item in resume.skipped:
                st.write(f"· {item}")


def render_import_section(candidate_id: str, profil_vide: bool) -> None:

    resultat = st.session_state.pop("import_cv_resume", None)

    if resultat is not None:
        _rendre_resultat(resultat)

    with st.expander(
        "📄 Importer depuis un CV", expanded=profil_vide
    ):

        st.caption(
            "L'IA transcrit votre CV — elle ne l'interprète pas. "
            "Chaque ligne retenue doit figurer mot pour mot dans le "
            "document, et vous relisez tout avant que quoi que ce "
            "soit ne soit écrit."
        )

        profil = st.session_state.get(ETAT)

        if profil is None:

            fichier = st.file_uploader(
                "Votre CV (.pdf ou .docx)",
                type=["pdf", "docx"],
                key="import_cv_fichier",
            )

            if not ai_is_configured():
                st.warning(
                    "Clé GEMINI_API_KEY absente : la lecture "
                    "automatique est indisponible."
                )
                return

            if fichier is not None and st.button(
                "Lire ce CV", type="primary", use_container_width=True
            ):

                texte = extract_text_from_upload(fichier)

                if not texte.strip():
                    st.error(
                        "Aucun texte n'a pu être extrait — un PDF "
                        "scanné ne contient que des images. "
                        "Réessayez avec un fichier texte."
                    )
                    return

                with st.spinner("Lecture du CV..."):
                    profil = extract_profile_from_cv(texte)

                if profil.is_empty:
                    for avertissement in profil.warnings:
                        st.error(avertissement)
                    return

                st.session_state[ETAT] = profil
                st.rerun()

            return

        _rendre_relecture(profil, candidate_id)
