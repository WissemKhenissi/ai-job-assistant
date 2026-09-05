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

Une seconde entrée mène au même parcours : **documenter une
compétence déclarée**. Une compétence que le candidat affirme sans
qu'aucune preuve ne la soutienne est classée « declared » par le
moteur — elle ne peut pas figurer comme compétence explicite sur un
CV généré, et elle pèse moins face à une annonce qui la demande. Ce
n'est pas un défaut du candidat : il a fait ces choses, il ne les a
pas racontées. Les questions portent alors sur une compétence plutôt
que sur une expérience, et la suite est identique.

Rien n'entre au Master CV sans validation explicite. Chaque
proposition reste rattachée à l'expérience en cours, ce qui permet
ensuite de générer un CV ciblé cohérent.

Et rien n'est coché d'office quand la réponse ne rapporte aucun fait
situé : valider une ligne rend sa compétence « prouvée », et une
affirmation reformulée ne prouve rien.
"""

from __future__ import annotations

import streamlit as st

from services.ai.gemini_client import is_configured as ai_is_configured
from services.ai.interview import (
    InterviewAnswer,
    InterviewQuestion,
    evidence_is_situated,
    generate_followup_questions,
    generate_skill_questions,
    propose_evidence_from_answers,
    transcribe_audio,
)
from services.interview_history_service import (
    get_asked_questions,
    get_exchanges,
    save_answer,
    save_questions,
)
from services.profile_service import (
    add_evidence,
    add_skill,
    get_experiences,
    get_undocumented_skills,
)


_STATE_KEY = "master_cv_interview"


def _etat_initial() -> dict:
    return {
        "experience_id": None,
        "experience_label": "",
        # Renseigné dans la variante « documenter une compétence » :
        # les propositions qui en sortent se rattachent à cette
        # compétence-là, pas à une compétence devinée par l'IA.
        "skill_name": "",
        # La réponse dont sont tirées les propositions : c'est elle
        # qui décide si elles sont cochées par défaut.
        "reponse": "",
        "etape": "recit",
        "narration": "",
        "questions": [],
        "exchange_ids": [],
        "proposals": None,
        "warning": "",
        # Dernier enregistrement déjà traité, par étape : sert à
        # déclencher l'envoi dès qu'un nouvel enregistrement arrive,
        # sans le rejouer à chaque réexécution du script.
        "dernier_audio": {},
    }


def _audio_a_traiter(etat: dict, cle: str, fichier_audio) -> bool:
    """
    True si un enregistrement vient d'arriver et n'a pas encore été
    traité.

    Streamlit ne reçoit l'audio qu'une fois l'enregistrement arrêté
    dans le navigateur : Python ne peut pas l'arrêter lui-même. Plutôt
    que d'imposer « arrêter » puis « envoyer », c'est donc l'arrêt de
    l'enregistrement qui vaut envoi — un seul geste.
    """

    if fichier_audio is None:
        return False

    identifiant = getattr(fichier_audio, "file_id", None)

    if identifiant is None or etat["dernier_audio"].get(cle) == identifiant:
        return False

    etat["dernier_audio"][cle] = identifiant

    return True


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

    st.caption(
        "À l'oral, arrêter l'enregistrement suffit : l'envoi part "
        "tout seul. Le bouton ne sert que pour une réponse écrite."
    )

    envoi_auto = _audio_a_traiter(etat, "recit", audio)

    if texte.strip() and audio is None:
        st.info(
            "Votre récit est prêt — cliquez sur **« Envoyer mon "
            "récit »** ci-dessous."
        )

    if st.button(
        "🤖 Envoyer mon récit",
        type="primary",
        key=f"{_STATE_KEY}_envoyer_recit",
        use_container_width=True,
    ) or envoi_auto:

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
# VARIANTE : DOCUMENTER UNE COMPETENCE DECLAREE
# ============================================================
#
# Une compétence déclarée sans preuve est classée « declared » par le
# moteur : elle ne peut pas figurer comme compétence explicite sur un
# CV généré, et elle pèse moins qu'une compétence prouvée face à une
# annonce qui la demande.
#
# Ce n'est pas un défaut du candidat, c'est une documentation
# manquante — il a fait ces choses, il ne les a pas racontées. Le
# parcours est donc le même que pour une expérience : questions,
# réponse libre, propositions à valider. Seule l'entrée change.


def _render_choix_competence(candidate_id: str, etat: dict) -> None:

    competences = get_undocumented_skills(candidate_id)

    if not competences:

        st.success(
            "Toutes vos compétences déclarées sont documentées par "
            "au moins une preuve."
        )

        return

    st.caption(
        f"{len(competences)} compétence(s) que vous déclarez sans "
        "qu'aucun élément de votre parcours ne les démontre. Le "
        "moteur les compte comme « déclarées » : elles n'apparaissent "
        "pas comme compétences explicites sur un CV généré."
    )

    par_identifiant = {
        competence["id"]: competence["name"]
        for competence in competences
    }

    identifiant = st.selectbox(
        "Compétence à documenter",
        options=list(par_identifiant),
        format_func=lambda cle: par_identifiant[cle],
        key=f"{_STATE_KEY}_competence_choisie",
    )

    poste_recherche = st.text_input(
        "Poste recherché (optionnel)",
        placeholder="Ex. Product Owner Digital",
        key=f"{_STATE_KEY}_poste_competence",
        help=(
            "Sert à orienter les questions vers ce qui compte pour "
            "ce type de poste."
        ),
    )

    st.divider()

    if st.button(
        "🤖 Me poser des questions sur cette compétence",
        type="primary",
        key=f"{_STATE_KEY}_questions_competence",
        use_container_width=True,
    ):

        nom = par_identifiant[identifiant]

        with st.spinner("Préparation des questions (Gemini)..."):

            questions, avertissement = generate_skill_questions(
                candidate_id=candidate_id,
                skill_name=nom,
                target_role=poste_recherche,
                already_asked=get_asked_questions(candidate_id),
            )

        if not questions:

            st.warning(
                avertissement
                or "Aucune question n'a pu être générée : réessayez."
            )

            return

        etat["skill_name"] = nom
        etat["experience_id"] = None
        etat["experience_label"] = nom
        etat["questions"] = questions
        etat["exchange_ids"] = save_questions(
            candidate_id=candidate_id,
            questions=questions,
            target_role=poste_recherche,
        )
        etat["warning"] = avertissement
        etat["etape"] = "relance"

        st.rerun()


# ============================================================
# ETAPE 2 : LES RELANCES
# ============================================================

def _render_relance(etat: dict) -> None:

    documente_une_competence = bool(etat.get("skill_name"))

    if etat["experience_label"]:

        st.caption(
            f"Compétence à documenter : {etat['skill_name']}"
            if documente_une_competence
            else f"Expérience en cours : {etat['experience_label']}"
        )

    if etat["warning"]:
        st.caption(etat["warning"])

    st.markdown(
        "**L'IA vous interroge sur cette compétence :**"
        if documente_une_competence
        else "**L'IA vous relance sur cette expérience :**"
    )

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
        "en une seule fois — l'IA fera le tri. À l'oral, arrêter "
        "l'enregistrement suffit : l'envoi part tout seul."
    )

    envoi_auto = _audio_a_traiter(etat, "relance", audio)

    if st.button(
        "🤖 Envoyer mes réponses",
        type="primary",
        key=f"{_STATE_KEY}_envoyer_relance",
        use_container_width=True,
    ) or envoi_auto:

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

            etat["reponse"] = reponse

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

    if st.button("↩️ Recommencer"):
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
        "Chaque ligne retenue rejoint votre Master CV comme preuve, "
        "ce qui rend sa compétence « prouvée » — et la rend "
        "affichable telle quelle sur un CV généré."
    )

    # Une preuve est un fait situé. Si la réponse n'en rapporte aucun
    # — ni chiffre, ni rythme, ni nom de projet ou d'outil — les
    # lignes qui en sortent reformulent une affirmation plutôt que de
    # la démontrer, et les cocher rendrait « prouvées » des
    # compétences que rien ne prouve.
    #
    # Le contrôle porte sur la réponse, pas sur chaque ligne : un
    # récit situé situe les lignes qu'il porte, même celles qui ne
    # répètent pas son chiffre.
    reponse_situee = evidence_is_situated(etat.get("reponse", ""))

    if not reponse_situee:

        st.warning(
            "Votre réponse ne rapporte aucun fait situé — ni chiffre, "
            "ni rythme, ni nom de projet, d'outil ou d'entreprise. "
            "Ces lignes redisent ce que vous affirmez sans le "
            "démontrer : elles sont décochées par défaut. Complétez "
            "votre réponse, ou cochez celles qui vous conviennent "
            "malgré tout."
        )

    retenues = []

    for proposition in propositions:

        with st.container(border=True):

            # Une ligne qui porte elle-même un chiffre ou un nom
            # propre se suffit, même si le reste de la réponse est
            # resté vague.
            garder = st.checkbox(
                "Ajouter cette ligne",
                value=(
                    reponse_situee
                    or evidence_is_situated(proposition.text)
                ),
                key=f"{_STATE_KEY}_garder_{proposition.id}",
            )

            texte = st.text_area(
                "Ligne d'expérience",
                value=proposition.text,
                key=f"{_STATE_KEY}_texte_{proposition.id}",
                height=80,
            )

            # Quand l'entretien porte sur une compétence
            # déclarée, c'est elle qu'il s'agit de documenter : la
            # preuve doit s'y rattacher, pas à une compétence voisine
            # que l'IA aurait nommée autrement — sinon la déclarée
            # reste sans preuve et une jumelle apparaît à côté.
            competence = st.text_input(
                "Compétence associée",
                value=etat.get("skill_name") or proposition.skill_name,
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

        # Le choix n'est offert qu'au repos : le proposer en cours
        # d'entretien reviendrait à changer de sujet au milieu d'une
        # réponse.
        depart = st.radio(
            "Par quoi commencer ?",
            options=("experience", "competence"),
            format_func=lambda cle: (
                "Raconter une expérience"
                if cle == "experience"
                else "Documenter une compétence déclarée"
            ),
            horizontal=True,
            key=f"{_STATE_KEY}_depart",
        )

        st.divider()

        if depart == "competence":
            _render_choix_competence(candidate_id, etat)

        else:
            _render_recit(candidate_id, etat, get_experiences())
