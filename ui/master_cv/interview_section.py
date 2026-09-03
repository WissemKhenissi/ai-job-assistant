"""
Onglet "Entretien IA" de la page Master CV.

Parcours **expérience par expérience**, en commençant par la plus
récente (structure retenue avec l'utilisateur après comparaison de
plusieurs options) :

1. **Racontez** — un seul champ libre, à l'écrit et/ou à l'oral. Le
   candidat parle de son expérience comme il le sent, sans grille
   imposée.
2. **Relances** — l'IA lit ce récit et pose des questions ciblées sur
   cette expérience (outils, méthodes, résultats, formations,
   interlocuteurs). Le candidat y répond en un seul bloc, là encore à
   l'écrit ou à l'oral.
3. **Propositions** — l'IA propose des lignes d'expérience et des
   compétences, toutes cochées par défaut : le candidat décoche ce
   qu'il ne veut pas, corrige les textes, en ajoute au besoin, puis
   valide le lot d'un seul geste.

Le mode "question par question" a été retiré : répondre à dix
questions une par une décourageait, alors que raconter puis se faire
relancer correspond à la façon dont on parle réellement de son
parcours.

Rien n'entre au Master CV sans validation explicite. Chaque
proposition reste rattachée à l'expérience en cours, ce qui permet
ensuite de générer un CV ciblé cohérent.
"""

from __future__ import annotations

import streamlit as st

from services.ai.gemini_client import is_configured as ai_is_configured
from services.ai.interview import (
    InterviewAnswer,
    InterviewQuestion,
    generate_followup_questions,
    propose_evidence_from_answers,
    transcribe_audio,
)
from services.interview_history_service import (
    get_asked_questions,
    get_exchanges,
    save_answer,
    save_questions,
)
from services.profile_service import add_evidence, add_skill, get_experiences


_STATE_KEY = "master_cv_interview"


def _etat_initial() -> dict:
    return {
        "experience_id": None,
        "experience_label": "",
        "etape": "recit",
        "narration": "",
        "questions": [],
        "exchange_ids": [],
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

    texte = (texte or "").strip()
    transcription = (transcription or "").strip()

    if texte and transcription:
        return f"{texte}\n{transcription}"

    return texte or transcription


def _saisie_libre(cle: str, label_texte: str, label_audio: str) -> tuple:
    """
    Un champ texte et un enregistreur, tous deux optionnels — le
    candidat choisit sa modalité, ou combine les deux.
    """

    texte = st.text_area(
        label_texte,
        key=f"{_STATE_KEY}_{cle}_texte",
        height=180,
    )

    audio = st.audio_input(
        label_audio,
        key=f"{_STATE_KEY}_{cle}_audio",
    )

    return texte, audio


# ============================================================
# HISTORIQUE
# ============================================================

def _render_historique(candidate_id: str) -> None:
    """
    Échanges des sessions précédentes : relisibles, modifiables et
    ré-analysables.

    C'est ce qui permet de revenir compléter une réponse donnée trop
    vite, sans refaire tout un entretien — et de vérifier ce qui a
    réellement été enregistré.
    """

    echanges = get_exchanges(candidate_id)

    if not echanges:
        return

    repondus = [e for e in echanges if e["answer"].strip()]

    with st.expander(
        f"🗂️ Historique — {len(echanges)} question(s) posée(s), "
        f"{len(repondus)} avec réponse"
    ):

        st.caption(
            "Les questions déjà posées ne seront plus reproposées. "
            "Vous pouvez compléter ou corriger une réponse, puis la "
            "faire ré-analyser."
        )

        for echange in echanges:

            with st.container(border=True):

                if echange["experience_label"]:
                    st.caption(
                        f"À propos de : {echange['experience_label']}"
                    )

                st.markdown(f"**{echange['question']}**")

                reponse = st.text_area(
                    "Votre réponse",
                    value=echange["answer"],
                    key=f"{_STATE_KEY}_hist_{echange['id']}",
                    height=100,
                    label_visibility="collapsed",
                )

                col_enregistrer, col_analyser = st.columns(2)

                with col_enregistrer:

                    if st.button(
                        "💾 Enregistrer",
                        key=f"{_STATE_KEY}_hist_save_{echange['id']}",
                        use_container_width=True,
                    ):
                        save_answer(echange["id"], reponse)
                        st.success("Réponse enregistrée.")
                        st.rerun()

                with col_analyser:

                    if st.button(
                        "🤖 Analyser cette réponse",
                        key=f"{_STATE_KEY}_hist_run_{echange['id']}",
                        use_container_width=True,
                    ):

                        if not reponse.strip():
                            st.warning("Cette réponse est vide.")

                        else:

                            save_answer(echange["id"], reponse)

                            with st.spinner("Analyse (Gemini)..."):
                                propositions, avertissement = (
                                    propose_evidence_from_answers(
                                        [
                                            InterviewAnswer(
                                                question=echange["question"],
                                                answer=reponse,
                                                experience_id=echange[
                                                    "experience_id"
                                                ],
                                                experience_label=echange[
                                                    "experience_label"
                                                ],
                                            )
                                        ]
                                    )
                                )

                            etat = st.session_state[_STATE_KEY]
                            etat["proposals"] = propositions
                            etat["warning"] = avertissement
                            etat["experience_id"] = echange["experience_id"]
                            etat["experience_label"] = echange[
                                "experience_label"
                            ]
                            etat["etape"] = "propositions"
                            st.rerun()


# ============================================================
# ETAPE 1 : LE RECIT
# ============================================================

def _render_recit(candidate_id: str, etat: dict, experiences) -> None:

    if not experiences:
        st.info(
            "Ajoutez d'abord une expérience dans l'onglet "
            "« Expériences » pour démarrer un entretien."
        )
        return

    libelles = {
        experience.id: f"{experience.job_title} — {experience.company}"
        for experience in experiences
    }

    # get_experiences trie déjà de la plus récente à la plus ancienne :
    # la première option est donc la dernière expérience, comme voulu.
    experience_id = st.selectbox(
        "Expérience à approfondir",
        options=[experience.id for experience in experiences],
        format_func=lambda identifiant: libelles[identifiant],
        key=f"{_STATE_KEY}_experience",
    )

    poste_recherche = st.text_input(
        "Poste recherché (optionnel)",
        placeholder="Ex. Product Owner Digital",
        key=f"{_STATE_KEY}_poste",
        help=(
            "Sert à orienter les relances vers ce qui compte pour ce "
            "type de poste."
        ),
    )

    fichiers = st.file_uploader(
        "CV à jour ou captures d'écran LinkedIn (optionnel)",
        type=["pdf", "docx", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key=f"{_STATE_KEY}_fichiers",
    )

    st.divider()

    st.markdown(f"**Racontez : {libelles[experience_id]}**")

    st.caption(
        "Ce que vous faisiez au quotidien, les projets marquants, ce "
        "dont vous êtes fier, les difficultés rencontrées. Pas de "
        "format imposé — l'IA posera ses questions ensuite."
    )

    texte, audio = _saisie_libre(
        "recit",
        "Votre récit, à l'écrit",
        "Ou votre récit, à l'oral",
    )

    if texte.strip() or audio is not None:
        st.info(
            "Votre récit est prêt — cliquez sur **« Envoyer mon "
            "récit »** ci-dessous."
        )

    if st.button(
        "🤖 Envoyer mon récit",
        type="primary",
        key=f"{_STATE_KEY}_envoyer_recit",
        use_container_width=True,
    ):

        avertissements = []

        with st.spinner("Analyse de votre récit (Gemini)..."):

            transcription, avert = _transcrire_si_fourni(audio)

            if avert:
                avertissements.append(avert)

            narration = _combiner(texte, transcription)

            if not narration.strip():
                st.warning(
                    "Racontez cette expérience, à l'écrit ou à l'oral, "
                    "avant d'envoyer."
                )
                return

            # Le récit est enregistré avant même les relances : s'il
            # n'y a pas de suite, il reste retrouvable.
            identifiants_recit = save_questions(
                candidate_id,
                [
                    InterviewQuestion(
                        question=f"Récit — {libelles[experience_id]}",
                        experience_id=experience_id,
                        experience_label=libelles[experience_id],
                    )
                ],
                target_role=poste_recherche,
            )

            save_answer(identifiants_recit[0], narration)

            questions, avertissement = generate_followup_questions(
                candidate_id=candidate_id,
                experience_id=experience_id,
                narration=narration,
                target_role=poste_recherche,
                uploaded_files=fichiers,
                already_asked=get_asked_questions(candidate_id),
            )

        if avertissement:
            avertissements.append(avertissement)

        if not questions:
            st.error(
                avertissement
                or "Aucune relance n'a pu être générée. Réessayez."
            )
            return

        etat["experience_id"] = experience_id
        etat["experience_label"] = libelles[experience_id]
        etat["narration"] = narration
        etat["questions"] = questions
        etat["exchange_ids"] = save_questions(
            candidate_id, questions, target_role=poste_recherche
        )
        etat["warning"] = " ".join(avertissements)
        etat["etape"] = "relance"
        st.rerun()


# ============================================================
# ETAPE 2 : LES RELANCES
# ============================================================

def _render_relance(etat: dict) -> None:

    if etat["experience_label"]:
        st.caption(f"Expérience en cours : {etat['experience_label']}")

    if etat["warning"]:
        st.caption(etat["warning"])

    st.markdown("**L'IA vous relance sur cette expérience :**")

    for question in etat["questions"]:
        st.markdown(f"- {question.question}")

    st.divider()

    texte, audio = _saisie_libre(
        "relance",
        "Vos réponses, à l'écrit",
        "Ou vos réponses, à l'oral",
    )

    st.caption(
        "Répondez à ce qui vous parle, dans l'ordre que vous voulez et "
        "en une seule fois — l'IA fera le tri."
    )

    if st.button(
        "🤖 Envoyer mes réponses",
        type="primary",
        key=f"{_STATE_KEY}_envoyer_relance",
        use_container_width=True,
    ):

        avertissements = []

        with st.spinner("Analyse de vos réponses (Gemini)..."):

            transcription, avert = _transcrire_si_fourni(audio)

            if avert:
                avertissements.append(avert)

            reponse = _combiner(texte, transcription)

            if not reponse.strip():
                st.warning(
                    "Répondez à l'écrit ou à l'oral avant d'envoyer."
                )
                return

            # Enregistrée avant l'extraction : si l'analyse échoue,
            # la réponse reste dans l'historique.
            if etat["exchange_ids"]:
                save_answer(etat["exchange_ids"][0], reponse)

            propositions, avertissement = propose_evidence_from_answers(
                [
                    InterviewAnswer(
                        question="Réponses aux relances",
                        answer=reponse,
                        experience_id=etat["experience_id"],
                        experience_label=etat["experience_label"],
                    )
                ],
                inspiration_questions=etat["questions"],
            )

        if avertissement:
            avertissements.append(avertissement)

        etat["proposals"] = propositions
        etat["warning"] = " ".join(avertissements)
        etat["etape"] = "propositions"
        st.rerun()

    if st.button("↩️ Recommencer avec une autre expérience"):
        st.session_state[_STATE_KEY] = _etat_initial()
        st.rerun()


# ============================================================
# ETAPE 3 : VALIDATION GROUPEE
# ============================================================

def _render_propositions(candidate_id: str, etat: dict) -> None:

    if etat["warning"]:
        st.info(etat["warning"])

    propositions = etat["proposals"] or []

    if not propositions:

        st.warning(
            "Aucune proposition exploitable n'a été extraite. Si votre "
            "réponse était pourtant détaillée, vérifiez l'historique "
            "ci-dessus : l'IA n'a peut-être pas capté l'enregistrement."
        )

        if st.button("↩️ Reprendre l'entretien"):
            st.session_state[_STATE_KEY] = _etat_initial()
            st.rerun()

        return

    if etat["experience_label"]:
        st.caption(f"Expérience : {etat['experience_label']}")

    st.markdown(
        f"**{len(propositions)} proposition(s)** — décochez ce que "
        "vous ne voulez pas, corrigez les textes, puis validez le lot."
    )

    st.caption(
        "Chaque ligne retenue rejoint votre Master CV comme preuve "
        "rattachée à cette expérience, ce qui rend sa compétence "
        "« prouvée »."
    )

    retenues = []

    for proposition in propositions:

        with st.container(border=True):

            garder = st.checkbox(
                "Ajouter cette ligne",
                value=True,
                key=f"{_STATE_KEY}_garder_{proposition.id}",
            )

            texte = st.text_area(
                "Ligne d'expérience",
                value=proposition.text,
                key=f"{_STATE_KEY}_texte_{proposition.id}",
                height=80,
            )

            competence = st.text_input(
                "Compétence associée",
                value=proposition.skill_name,
                key=f"{_STATE_KEY}_competence_{proposition.id}",
            )

            if proposition.source_excerpt:
                st.caption(
                    "D'après votre réponse : "
                    f"« {proposition.source_excerpt} »"
                )

            if garder:
                retenues.append((texte, competence))

    st.divider()

    with st.popover(
        "➕ Ajouter une ligne manquante", use_container_width=True
    ):

        texte_manuel = st.text_area(
            "Ligne d'expérience",
            key=f"{_STATE_KEY}_manuel_texte",
            height=80,
        )

        competence_manuelle = st.text_input(
            "Compétence associée",
            key=f"{_STATE_KEY}_manuel_competence",
        )

        if st.button("Ajouter", key=f"{_STATE_KEY}_manuel_ajouter"):

            if texte_manuel.strip() and competence_manuelle.strip():

                add_evidence(
                    candidate_id=candidate_id,
                    skill_id=add_skill(
                        candidate_id=candidate_id,
                        name=competence_manuelle.strip(),
                    ),
                    description=texte_manuel.strip(),
                    experience_id=etat["experience_id"],
                    evidence_type="Entretien IA (ajout manuel)",
                )

                st.success("Ajouté au Master CV.")
                st.rerun()

            else:
                st.warning("Renseignez la ligne et la compétence.")

    col_valider, col_passer = st.columns(2)

    with col_valider:

        if st.button(
            f"✅ Ajouter les {len(retenues)} ligne(s) au Master CV",
            type="primary",
            key=f"{_STATE_KEY}_valider_lot",
            use_container_width=True,
        ):

            ajoutees = 0

            for texte, competence in retenues:

                if not texte.strip() or not competence.strip():
                    continue

                skill_id = add_skill(
                    candidate_id=candidate_id, name=competence.strip()
                )

                add_evidence(
                    candidate_id=candidate_id,
                    skill_id=skill_id,
                    description=texte.strip(),
                    experience_id=etat["experience_id"],
                    evidence_type="Entretien IA (validé par le candidat)",
                )

                ajoutees += 1

            st.session_state[_STATE_KEY] = _etat_initial()
            st.success(f"{ajoutees} ligne(s) ajoutée(s) au Master CV.")
            st.rerun()

    with col_passer:

        if st.button(
            "⏭️ Passer sans rien ajouter",
            key=f"{_STATE_KEY}_passer",
            use_container_width=True,
        ):
            st.session_state[_STATE_KEY] = _etat_initial()
            st.rerun()


# ============================================================
# ORCHESTRATION
# ============================================================

def render_interview_section(candidate_id: str) -> None:

    st.subheader("🎙️ Entretien IA")

    st.caption(
        "Une expérience à la fois, en commençant par la plus récente. "
        "Vous racontez, l'IA vous relance, puis vous propose des "
        "lignes d'expérience et des compétences à valider. Rien "
        "n'entre dans votre Master CV sans votre accord."
    )

    if not ai_is_configured():
        st.info(
            "Entretien IA indisponible — clé GEMINI_API_KEY absente "
            "de .env."
        )
        return

    etat = st.session_state.setdefault(_STATE_KEY, _etat_initial())

    _render_historique(candidate_id)

    if etat["etape"] == "propositions":
        _render_propositions(candidate_id, etat)

    elif etat["etape"] == "relance":
        _render_relance(etat)

    else:
        _render_recit(candidate_id, etat, get_experiences())
