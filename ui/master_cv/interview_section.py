"""
Section "Entretien IA" de la page Master CV.

Un seul round volontairement large (voir services/ai/interview.py) :
poste recherché optionnel + fichiers optionnels (CV externe, captures
d'écran LinkedIn) → éventail de questions couvrant plusieurs
expériences → réponses libres, aucune obligatoire, à l'écrit ou à
l'oral → propositions de preuves, chacune éditable et à valider
explicitement, une par une, avant d'entrer au Master CV. Rejeter
n'écrit jamais rien.

Deux façons de répondre, au choix du candidat :

- question par question (texte et/ou audio pour chacune) ;
- en un seul champ libre (texte et/ou audio), l'IA se chargeant de
  trier ce qui est exploitable — l'idée étant de donner de la matière
  à réflexion plutôt que d'imposer une structure rigide.

Chaque réponse orale est transcrite (services.ai.interview.
transcribe_audio) avant d'être traitée exactement comme une réponse
écrite : le garde-fou de traçabilité de propose_evidence_from_answers
s'applique donc de la même façon, quelle que soit la modalité.
"""

from __future__ import annotations

import streamlit as st

from services.ai.gemini_client import is_configured as ai_is_configured
from services.ai.interview import (
    InterviewAnswer,
    generate_interview_questions,
    propose_evidence_from_answers,
    transcribe_audio,
)
from services.profile_service import add_evidence, add_skill


_STATE_KEY = "master_cv_interview"


def _etat_initial() -> dict:
    return {
        "questions": [],
        "proposals": None,
        "warning": "",
    }


def _transcrire_si_fourni(fichier_audio) -> tuple[str, str]:
    """Transcrit un enregistrement st.audio_input, ou ("", "") si absent."""

    if fichier_audio is None:
        return "", ""

    return transcribe_audio(
        fichier_audio.getvalue(),
        mime_type=fichier_audio.type or "audio/wav",
    )


def _combiner(texte: str, transcription: str) -> str:

    texte = texte.strip()
    transcription = transcription.strip()

    if texte and transcription:
        return f"{texte}\n{transcription}"

    return texte or transcription


def render_interview_section(candidate_id: str) -> None:

    st.subheader("🎙️ Entretien IA")

    st.caption(
        "Gemini pose un éventail de questions à partir de votre "
        "parcours actuel (et, si vous en fournissez, d'un CV externe "
        "ou de captures d'écran) pour faire émerger des compétences "
        "ou des détails d'expérience que vous n'auriez pas pensé à "
        "écrire. Répondez à l'écrit ou à l'oral. Rien n'est ajouté au "
        "Master CV sans votre validation explicite, phrase par "
        "phrase."
    )

    if not ai_is_configured():
        st.info(
            "Entretien IA indisponible — clé GEMINI_API_KEY absente "
            "de .env."
        )
        return

    etat = st.session_state.setdefault(_STATE_KEY, _etat_initial())

    # ============================================================
    # ETAPE 1 : DEMARRER L'ENTRETIEN
    # ============================================================

    if not etat["questions"]:

        poste_recherche = st.text_input(
            "Poste recherché (optionnel)",
            placeholder="Ex. Product Owner Digital",
            key=f"{_STATE_KEY}_poste",
        )

        fichiers = st.file_uploader(
            "CV à jour ou captures d'écran LinkedIn (optionnel)",
            type=["pdf", "docx", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key=f"{_STATE_KEY}_fichiers",
        )

        if st.button("Générer des questions", type="primary"):

            with st.spinner("Génération des questions (Gemini)..."):
                questions, avertissement = generate_interview_questions(
                    candidate_id,
                    target_role=poste_recherche,
                    uploaded_files=fichiers,
                )

            if not questions:
                st.error(
                    avertissement or "Aucune question n'a pu être générée."
                )
                return

            etat["questions"] = questions
            etat["warning"] = avertissement
            st.rerun()

        return

    # ============================================================
    # ETAPE 2 : REPONDRE AUX QUESTIONS
    # ============================================================

    if etat["proposals"] is None:

        if etat["warning"]:
            st.caption(etat["warning"])

        st.write(
            f"{len(etat['questions'])} question(s) — répondez à ce "
            "qui vous parle, aucune n'est obligatoire. Aucun champ "
            "n'est dans un formulaire : vous pouvez enregistrer un "
            "audio ou taper, dans l'ordre qui vous convient, puis "
            "cliquer sur \"Envoyer\" en bas."
        )

        mode_libre = st.toggle(
            "Répondre librement en un seul champ, plutôt que "
            "question par question",
            key=f"{_STATE_KEY}_mode_libre",
            help=(
                "Les questions ci-dessous servent alors de simple "
                "matière à réflexion : répondez-y dans l'ordre que "
                "vous voulez, en une seule fois, à l'écrit ou à "
                "l'oral — l'IA se charge de trier ce qui est "
                "exploitable."
            ),
        )

        st.divider()

        if mode_libre:

            st.markdown("**Pistes de réflexion :**")

            for question in etat["questions"]:
                st.caption(f"· {question.question}")

            st.divider()

            texte_libre = st.text_area(
                "Votre réponse, à l'écrit",
                key=f"{_STATE_KEY}_libre_texte",
                height=200,
            )

            audio_libre = st.audio_input(
                "Ou votre réponse, à l'oral",
                key=f"{_STATE_KEY}_libre_audio",
            )

            envoyer = st.button(
                "Envoyer ma réponse", type="primary", key=f"{_STATE_KEY}_envoyer_libre"
            )

            if st.button("Recommencer l'entretien"):
                st.session_state[_STATE_KEY] = _etat_initial()
                st.rerun()

            if envoyer:

                avertissements = []

                with st.spinner("Traitement de votre réponse (Gemini)..."):

                    transcription, avert = _transcrire_si_fourni(audio_libre)

                    if avert:
                        avertissements.append(avert)

                    texte_final = _combiner(texte_libre, transcription)

                    reponses = [
                        InterviewAnswer(
                            question="Réponse libre à l'ensemble des questions",
                            answer=texte_final,
                        )
                    ]

                    propositions, avertissement = propose_evidence_from_answers(
                        reponses,
                        inspiration_questions=etat["questions"],
                    )

                if avertissement:
                    avertissements.append(avertissement)

                etat["proposals"] = propositions
                etat["warning"] = " ".join(avertissements)
                st.rerun()

            return

        # --------------------------------------------------------
        # MODE : QUESTION PAR QUESTION
        # --------------------------------------------------------

        for indice, question in enumerate(etat["questions"]):

            with st.container(border=True):

                if question.experience_label:
                    st.caption(f"À propos de : {question.experience_label}")

                st.markdown(f"**{question.question}**")

                st.text_area(
                    "Réponse écrite",
                    key=f"{_STATE_KEY}_reponse_{indice}",
                    height=80,
                    label_visibility="collapsed",
                )

                st.audio_input(
                    "🎤 Ou répondez à l'oral",
                    key=f"{_STATE_KEY}_audio_{indice}",
                )

        envoyer = st.button(
            "Envoyer mes réponses", type="primary", key=f"{_STATE_KEY}_envoyer"
        )

        if st.button("Recommencer l'entretien"):
            st.session_state[_STATE_KEY] = _etat_initial()
            st.rerun()

        if envoyer:

            reponses = []
            avertissements = []

            with st.spinner("Traitement de vos réponses (Gemini)..."):

                for indice, question in enumerate(etat["questions"]):

                    texte_tape = st.session_state.get(
                        f"{_STATE_KEY}_reponse_{indice}", ""
                    )

                    audio_fichier = st.session_state.get(
                        f"{_STATE_KEY}_audio_{indice}"
                    )

                    transcription, avert = _transcrire_si_fourni(audio_fichier)

                    if avert:
                        avertissements.append(avert)

                    reponses.append(
                        InterviewAnswer(
                            question=question.question,
                            answer=_combiner(texte_tape, transcription),
                            experience_id=question.experience_id,
                            experience_label=question.experience_label,
                        )
                    )

                propositions, avertissement = propose_evidence_from_answers(
                    reponses
                )

            if avertissement:
                avertissements.append(avertissement)

            etat["proposals"] = propositions
            etat["warning"] = " ".join(avertissements)
            st.rerun()

        return

    # ============================================================
    # ETAPE 3 : VALIDATION DES PROPOSITIONS
    # ============================================================

    if etat["warning"]:
        st.info(etat["warning"])

    if not etat["proposals"]:
        st.success("Aucune proposition à valider pour cette session.")

    for proposition in list(etat["proposals"]):

        with st.container(border=True):

            legende = " · ".join(
                partie
                for partie in (
                    proposition.experience_label,
                    (
                        f"Compétence : {proposition.skill_name}"
                        if proposition.skill_name
                        else ""
                    ),
                )
                if partie
            )

            if legende:
                st.caption(legende)

            texte = st.text_area(
                "Texte proposé (modifiable avant validation)",
                value=proposition.text,
                key=f"{_STATE_KEY}_texte_{proposition.id}",
                height=80,
            )

            if proposition.source_excerpt:
                st.caption(
                    "D'après votre réponse : "
                    f"« {proposition.source_excerpt} »"
                )

            col_valider, col_rejeter = st.columns(2)

            with col_valider:

                if st.button(
                    "✅ Valider",
                    key=f"{_STATE_KEY}_valider_{proposition.id}",
                    use_container_width=True,
                ):

                    skill_id = add_skill(
                        candidate_id=candidate_id,
                        name=proposition.skill_name or texte[:60],
                    )

                    add_evidence(
                        candidate_id=candidate_id,
                        skill_id=skill_id,
                        description=texte,
                        experience_id=proposition.experience_id,
                        evidence_type=(
                            "Entretien IA (validé par le candidat)"
                        ),
                    )

                    etat["proposals"] = [
                        item
                        for item in etat["proposals"]
                        if item.id != proposition.id
                    ]

                    st.success("Ajouté au Master CV.")
                    st.rerun()

            with col_rejeter:

                if st.button(
                    "❌ Rejeter",
                    key=f"{_STATE_KEY}_rejeter_{proposition.id}",
                    use_container_width=True,
                ):

                    etat["proposals"] = [
                        item
                        for item in etat["proposals"]
                        if item.id != proposition.id
                    ]

                    st.rerun()

    if st.button("Terminer et recommencer"):
        st.session_state[_STATE_KEY] = _etat_initial()
        st.rerun()
