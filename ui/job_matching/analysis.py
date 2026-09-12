"""
Onglet "Nouvelle annonce" : formulaire d'analyse d'une offre, score de
matching, détail par compétence, points forts et points de vigilance.

Le résultat de l'analyse est conservé en session_state
("job_matching_result") : c'est ce que lit l'onglet "CV & lettre" pour
savoir sur quelle offre travailler, indépendamment de l'onglet
actuellement affiché — Streamlit réexécute tout le script à chaque
interaction, les deux onglets restent donc synchronisés.
"""

from __future__ import annotations

from uuid import uuid4

import streamlit as st

from services.ai.gemini_client import is_configured as ai_is_configured
from services.ai.job_analysis import (
    analyze_job_offer_with_ai,
    generate_fit_synthesis,
)
from services.job_offer_fetcher import fetch_job_offer_from_url
from services.job_service import save_job_offer
from services.matching import analyze_and_save_job_match
from services.experience_duration import (
    format_experience_years,
    total_experience_years,
)
from services.requirement_cleaning import clean_required_skills
from services.skill_candidate_service import record_unknown_terms
from services.text_normalization import (
    minuscules_sans_accents as _normalize_loose,
)
from services.job_requirements_service import (
    extract_required_skills,
    extract_required_skills_detailed,
    extract_required_years,
)
from services.matching.normalization import _canonical_skill_name
from services.profile_service import get_experiences


_CONTRATS = ("", "CDI", "CDD", "Freelance", "Stage")

_TELETRAVAIL = ("", "Sur site", "Hybride", "Télétravail complet")

# Message à afficher après enregistrement de la fiche, une fois la
# page relancée pour que l'intitulé corrigé s'affiche en tête.
_CLE_MESSAGE_FICHE = "job_offer_fiche_message"


def _index_connu(valeurs: tuple[str, ...], valeur: str) -> int:
    """
    La position d'une valeur dans un menu, ou zéro si l'IA en a
    rapporté une que le menu ne propose pas.
    """

    return valeurs.index(valeur) if valeur in valeurs else 0


# Un intitulé plus long qu'une ligne de titre n'en est pas un.
_LONGUEUR_MAX_TITRE = 120

# De part et d'autre de l'exigence reconnue, dans l'extrait d'annonce.
_MARGE_EXTRAIT = 180


def _titre_devine(description: str) -> str:
    """
    La première ligne non vide d'une annonce en est le titre.

    Règle déterministe, donc explicable et reproductible — et
    corrigible d'un clic une fois l'analyse faite. Elle remplace un
    champ obligatoire qui demandait à l'utilisateur de recopier la
    première ligne de ce qu'il venait de coller.
    """

    for ligne in description.split("\n"):

        nue = ligne.strip()

        if nue:
            return nue[:_LONGUEUR_MAX_TITRE]

    return ""


def _extrait_annonce(texte: str, position: int, alias: str) -> str:
    """
    Le passage de l'annonce où l'exigence a été reconnue, l'alias en
    gras.

    Montrer le passage plutôt que d'affirmer l'exigence : une
    reconnaissance qu'on peut retrouver dans le texte est vérifiable,
    et donc contestable. C'est tout l'intérêt.
    """

    fin_alias = position + len(alias)

    reconnu = texte[position:fin_alias]

    debut = max(0, position - _MARGE_EXTRAIT)
    fin = min(len(texte), fin_alias + _MARGE_EXTRAIT)

    def plat(fragment: str) -> str:
        return " ".join(fragment.split())

    # La position vient du moteur ; si elle ne retombe pas sur l'alias,
    # on montre le passage sans le mettre en gras plutôt que de
    # souligner le mauvais mot.
    if reconnu.casefold() != alias.casefold():
        return (
            ("… " if debut > 0 else "")
            + plat(texte[debut:fin])
            + (" …" if fin < len(texte) else "")
        )

    return (
        ("… " if debut > 0 else "")
        + plat(texte[debut:position])
        + " **"
        + plat(reconnu)
        + "** "
        + plat(texte[fin_alias:fin])
        + (" …" if fin < len(texte) else "")
    )


# Clés session_state utilisées pour préremplir le formulaire après une
# récupération réussie depuis un lien — le formulaire ci-dessous les
# lit comme valeurs initiales.
_PREFILL_TITLE_KEY = "job_matching_prefill_title"
_PREFILL_TEXT_KEY = "job_matching_prefill_text"


def _new_draft() -> None:
    st.session_state["job_matching_draft_id"] = f"job-{uuid4()}"
    st.session_state.pop("job_matching_result", None)
    st.session_state.pop(_PREFILL_TITLE_KEY, None)
    st.session_state.pop(_PREFILL_TEXT_KEY, None)
    st.rerun()


def render_analysis_tab(candidate_id: str) -> None:

    st.write(
        "Collez une annonce. L'intitulé, le contrat et le télétravail "
        "se lisent dans le texte — vous les corrigerez ensuite si "
        "besoin."
    )

    # ========================================================
    # INITIALISATION
    # ========================================================

    if "job_matching_draft_id" not in st.session_state:
        st.session_state["job_matching_draft_id"] = f"job-{uuid4()}"

    # ========================================================
    # RECUPERATION DEPUIS UN LIEN (OPTIONNEL)
    # ========================================================
    #
    # Purement mécanique (pas d'IA) : un téléchargement de la page et
    # une extraction du texte principal. Ne fonctionne pas partout —
    # LinkedIn notamment bloque ce type de requête. Le copier-coller
    # ci-dessous reste toujours disponible, avant comme après un échec.

    with st.expander("🔗 Récupérer depuis un lien"):

        col_lien, col_bouton = st.columns([4, 1])

        with col_lien:

            lien_annonce = st.text_input(
                "Lien de l'annonce",
                placeholder="https://...",
                label_visibility="collapsed",
                key="job_offer_url_input",
            )

        with col_bouton:

            recuperer_clic = st.button(
                "Récupérer",
                use_container_width=True,
            )

        if recuperer_clic:

            with st.spinner("Récupération en cours..."):
                resultat_fetch = fetch_job_offer_from_url(lien_annonce)

            if resultat_fetch.success:

                st.session_state[_PREFILL_TITLE_KEY] = resultat_fetch.title
                st.session_state[_PREFILL_TEXT_KEY] = resultat_fetch.text

                st.success(
                    "Contenu récupéré ci-dessous — vérifiez-le avant "
                    "d'analyser : l'extraction automatique peut être "
                    "imparfaite selon le site."
                )

                st.rerun()

            else:

                st.error(
                    f"{resultat_fetch.error} Vous pouvez toujours "
                    "coller le texte manuellement ci-dessous."
                )

    # ========================================================
    # FORMULAIRE
    # ========================================================

    with st.form("job_matching_form"):

        description = st.text_area(
            "Texte de l'annonce",
            value=st.session_state.get(_PREFILL_TEXT_KEY, ""),
            height=300,
            placeholder="Collez ici l'annonce complète.",
            label_visibility="collapsed",
        )

        submitted = st.form_submit_button(
            "Analyser l'annonce",
            type="primary",
            use_container_width=True,
        )

    # Six champs se dressaient ici entre l'utilisateur et son
    # résultat : intitulé, entreprise, localisation, contrat,
    # télétravail. Quatre d'entre eux se lisent dans le texte qu'on
    # vient de coller — le contrat et le télétravail par l'IA, qui les
    # rapportait déjà, l'intitulé par sa première ligne. Les demander
    # d'avance revenait à faire saisir à l'utilisateur ce que la
    # machine sait, avant de lui montrer quoi que ce soit.
    title = (
        st.session_state.get(_PREFILL_TITLE_KEY, "").strip()
        or _titre_devine(description)
    )

    company = ""
    location = ""
    contract_type = ""
    remote_policy = ""

    # ========================================================
    # ANALYSE
    # ========================================================

    if submitted:

        if not description.strip():
            st.error(
                "Collez le texte de l'annonce pour lancer l'analyse."
            )
            return

        required_skills = extract_required_skills(description)

        # Deterministe, sans IA : cette valeur sert a comparer avec
        # l'anciennete reelle du candidat, mieux vaut ne rien
        # annoncer qu'un chiffre suppose.
        annees_demandees = extract_required_years(description)

        # --------------------------------------------------------
        # CATEGORISATION + EXTRACTION IA (GEMINI), OPTIONNELLE
        # --------------------------------------------------------
        #
        # Ne remplace jamais une sélection manuelle explicite : elle
        # ne comble que les champs laissés vides. Les compétences
        # détectées par le catalogue restent la base ; l'IA ne fait
        # qu'y ajouter celles qu'elle a repérées en plus. La
        # déduplication ici est insensible à la casse/aux accents —
        # simple affichage — le moteur de matching applique sa propre
        # normalisation, plus poussée, au moment du calcul du score.

        avertissement_ia = ""

        if ai_is_configured():

            analyse_ia = analyze_job_offer_with_ai(
                f"{title.strip()}\n{description.strip()}"
            )

            avertissement_ia = analyse_ia.warning

            contract_type = contract_type or analyse_ia.contract_type
            remote_policy = remote_policy or analyse_ia.remote_policy
            remote_details = analyse_ia.remote_details

            deja_presentes = {
                _normalize_loose(skill) for skill in required_skills
            }

            for skill in analyse_ia.required_skills:

                cle = _normalize_loose(skill)

                if cle in deja_presentes:
                    continue

                deja_presentes.add(cle)
                required_skills.append(skill)

        else:

            remote_details = ""

        # --------------------------------------------------------
        # TRI DES EXIGENCES
        # --------------------------------------------------------
        #
        # L'extraction IA est libre : sur une annonce marketing elle
        # rapporte « Data », « mobile », « acquisition » — des mots
        # de l'annonce, pas des compétences. Comptés comme exigences,
        # ils font baisser le score et interdisent à la rédaction des
        # mots ordinaires.

        required_skills, exigences_ecartees = clean_required_skills(
            required_skills,
            job_title=title.strip(),
            job_description=description.strip(),
        )

        if not required_skills:

            st.error(
                "Aucune compétence n'a été détectée dans l'annonce. "
                "Vous pouvez les ajouter manuellement si besoin."
            )

            return

        try:

            job_offer_id = save_job_offer(
                job_offer_id=st.session_state["job_matching_draft_id"],
                title=title.strip(),
                description=description.strip(),
                company=company.strip(),
                location=location.strip(),
                contract_type=contract_type,
                remote_policy=remote_policy,
                remote_details=remote_details,
                required_years=annees_demandees,
                source="manual",
                status="selected",
            )

            result = analyze_and_save_job_match(
                candidate_id=candidate_id,
                job_offer_id=job_offer_id,
                required_skills=required_skills,
            )

            # --------------------------------------------------
            # CE QUE LE REFERENTIEL NE CONNAIT PAS
            # --------------------------------------------------
            #
            # Un terme inconnu est un trou du référentiel, pas une
            # compétence absente du candidat. On l'enregistre pour
            # que l'utilisateur puisse l'intégrer : c'est ainsi que
            # le référentiel s'étend à d'autres métiers que ceux
            # prévus à sa livraison.

            try:
                record_unknown_terms(
                    required_skills,
                    job_offer_id=job_offer_id,
                    was_counted=True,
                )
                record_unknown_terms(
                    exigences_ecartees,
                    job_offer_id=job_offer_id,
                    was_counted=False,
                )

            except Exception:
                # Ne jamais faire échouer une analyse pour un
                # apprentissage qui n'a pas abouti.
                pass

            st.session_state["job_matching_result"] = {
                "job_offer_id": job_offer_id,
                "title": title.strip(),
                # Conservé pour pouvoir montrer, exigence par
                # exigence, le passage de l'annonce où elle a été
                # reconnue.
                "description": description.strip(),
                "company": company.strip(),
                "location": location.strip(),
                "extraction_source": (
                    "catalogue + IA (Gemini)"
                    if ai_is_configured()
                    else "catalogue"
                ),
                "required_skills": required_skills,
                "requirements_dropped": exigences_ecartees,
                "result": result,
                "contract_type": contract_type,
                "remote_policy": remote_policy,
                "remote_details": remote_details,
                "required_years": annees_demandees,
            }

            st.success(
                "Annonce analysée et enregistrée. Passez à l'onglet "
                "« CV & lettre » pour générer vos documents."
            )

            if avertissement_ia:
                st.caption(avertissement_ia)

        except Exception as error:

            st.error(
                f"Analyse impossible : {error}"
            )

            return

    # ========================================================
    # RÉCUPÉRATION DU DERNIER RÉSULTAT
    # ========================================================

    stored_result = st.session_state.get(
        "job_matching_result"
    )

    if stored_result is None:

        st.info(
            "Collez une annonce puis cliquez sur "
            "« Analyser l'annonce » pour obtenir le matching."
        )

    else:

        result = stored_result["result"]

        # ====================================================
        # INFORMATIONS SUR L'ANNONCE
        # ====================================================

        st.caption(
            f"Compétences utilisées — "
            f"{stored_result['extraction_source']} : "
            f"{', '.join(stored_result['required_skills'])}"
        )

        # Ce que le tri a refusé de compter comme exigence. Affiché
        # plutôt que tu : un tri silencieux qui se trompe est
        # indétectable.
        ecartees = stored_result.get("requirements_dropped") or []

        if ecartees:
            st.caption(
                "Écartés du décompte (mots de l'annonce, pas des "
                f"compétences) : {', '.join(ecartees)}"
            )

        st.divider()

        st.subheader(
            stored_result["title"]
        )

        # ====================================================
        # CORRIGER LA FICHE
        # ====================================================
        #
        # Ce que la machine a lu est proposé, jamais imposé :
        # l'intitulé vient de la première ligne de l'annonce, le
        # contrat et le télétravail de l'IA. Trois lectures qui
        # peuvent se tromper, et qui se corrigent ici — après le
        # résultat, plutôt que d'être saisies avant lui.

        with st.expander("✏️ Corriger la fiche de l'annonce"):

            message = st.session_state.pop(_CLE_MESSAGE_FICHE, None)

            if message:
                st.success(message)

            with st.form("job_offer_fiche"):

                titre_corrige = st.text_input(
                    "Intitulé du poste",
                    value=stored_result["title"],
                )

                col_gauche, col_droite = st.columns(2)

                with col_gauche:

                    entreprise = st.text_input(
                        "Entreprise",
                        value=stored_result.get("company", ""),
                        placeholder="Nom de l'entreprise",
                    )

                    localisation = st.text_input(
                        "Localisation",
                        value=stored_result.get("location", ""),
                        placeholder="Paris / Hybride",
                    )

                with col_droite:

                    contrat = st.selectbox(
                        "Type de contrat",
                        _CONTRATS,
                        index=_index_connu(
                            _CONTRATS,
                            stored_result.get("contract_type", ""),
                        ),
                    )

                    teletravail = st.selectbox(
                        "Télétravail",
                        _TELETRAVAIL,
                        index=_index_connu(
                            _TELETRAVAIL,
                            stored_result.get("remote_policy", ""),
                        ),
                    )

                enregistrer = st.form_submit_button(
                    "Enregistrer",
                    use_container_width=True,
                )

            if enregistrer:

                titre_change = (
                    titre_corrige.strip() != stored_result["title"]
                )

                save_job_offer(
                    job_offer_id=stored_result["job_offer_id"],
                    title=titre_corrige.strip(),
                    description=stored_result.get("description", ""),
                    company=entreprise.strip(),
                    location=localisation.strip(),
                    contract_type=contrat,
                    remote_policy=teletravail,
                    remote_details=stored_result.get(
                        "remote_details", ""
                    ),
                    required_years=stored_result.get("required_years"),
                    source="manual",
                    status="selected",
                )

                stored_result["title"] = titre_corrige.strip()
                stored_result["company"] = entreprise.strip()
                stored_result["location"] = localisation.strip()
                stored_result["contract_type"] = contrat
                stored_result["remote_policy"] = teletravail

                st.session_state["job_matching_result"] = stored_result

                # L'intitulé n'est pas qu'une étiquette : il sert à
                # écarter les mots qui ne figurent que dans le titre
                # du poste. Le corriger peut donc changer le résultat,
                # et le dire vaut mieux que de laisser croire à un
                # score à jour.
                st.session_state[_CLE_MESSAGE_FICHE] = (
                    "Fiche enregistrée. L'intitulé participe à "
                    "l'analyse — relancez-la pour que le score en "
                    "tienne compte."
                    if titre_change
                    else "Fiche enregistrée."
                )

                st.rerun()

        # ====================================================
        # CATEGORISATION DE L'OFFRE
        # ====================================================

        categorisation = " · ".join(
            partie
            for partie in (
                stored_result.get("contract_type", ""),
                stored_result.get("remote_policy", ""),
                stored_result.get("remote_details", ""),
            )
            if partie
        )

        if categorisation:
            st.caption(f"📋 {categorisation}")

        # ====================================================
        # ANCIENNETE DEMANDEE vs ANCIENNETE REELLE
        # ====================================================
        #
        # Comparaison purement factuelle : deux nombres de dates, sans
        # jugement. Une ancienneté inférieure n'est pas masquée — c'est
        # un écart réel, que le candidat doit voir avant de postuler.

        annees_demandees = stored_result.get("required_years")

        if annees_demandees:

            annees_candidat = total_experience_years(get_experiences())

            message = (
                f"Ancienneté demandée : {annees_demandees} ans · "
                f"la vôtre : {format_experience_years(annees_candidat)}"
            )

            if annees_candidat >= annees_demandees:
                st.success(f"✅ {message}")

            else:
                manquant = round(annees_demandees - annees_candidat, 1)
                st.warning(
                    f"⚠️ {message} — il vous manque environ "
                    f"{format_experience_years(manquant)} pour atteindre "
                    "le seuil affiché par l'annonce."
                )

        # ====================================================
        # SCORE
        # ====================================================

        (
            score_col,
            proven_col,
            declared_col,
            inferred_col,
            missing_col,
        ) = st.columns(5)

        score_col.metric(
            "Score global",
            f"{result.score_global:.0f} / 100",
        )

        proven_col.metric(
            "Prouvées",
            len(result.proven_skills),
            help=(
                "Déclarées dans le Master CV et soutenues par "
                "au moins une preuve."
            ),
        )

        declared_col.metric(
            "Déclarées",
            len(result.declared_skills),
            help=(
                "Déclarées dans le Master CV, mais sans preuve "
                "rattachée : à documenter."
            ),
        )

        inferred_col.metric(
            "Déduites",
            len(result.inferred_skills),
            help=(
                "Non déclarées, déduites du parcours : une "
                "hypothèse, pas un fait affirmé."
            ),
        )

        missing_col.metric(
            "Manquantes",
            len(result.missing_skills),
            help=(
                "Tous niveaux confondus — un outil cité en "
                "exemple compte ici comme une condition d'entrée."
            ),
        )

        # ====================================================
        # CE QUI DÉCIDE VRAIMENT
        # ====================================================
        #
        # Un pourcentage ne dit pas si une candidature vaut la
        # peine. La liste des conditions d'entrée non couvertes,
        # si. Elle est donc affichée avant le détail, et séparément
        # des écarts sur des compétences que l'annonce ne fait que
        # citer.

        essentielles_manquantes = result.missing_essential_skills

        if essentielles_manquantes:

            st.error(
                "Exigences posées comme conditions et non "
                "couvertes : "
                + ", ".join(essentielles_manquantes)
            )

        elif result.missing_skills:

            st.info(
                "Aucune condition d'entrée non couverte. Les "
                "écarts restants portent sur des compétences que "
                "l'annonce souhaite ou cite, sans les exiger."
            )

        # ====================================================
        # DÉTAIL DU MATCHING
        # ====================================================

        status_labels = {
            "proven": "🟢 Prouvée",
            "declared": "🔵 Déclarée",
            "inferred": "🟡 Déduite",
            "missing": "🔴 Manquante",
        }

        # Le statut décrit le candidat, le niveau décrit ce que
        # l'annonce demande. Les lire côte à côte évite de
        # confondre un manque réel avec un outil cité en passant.
        importance_labels = {
            "essentielle": "❗ Condition",
            "souhaitee": "➕ Souhaitée",
            "mention": "• Citée",
        }

        st.subheader(
            "Détail du matching"
        )

        if not result.matches:

            st.info(
                "Aucun détail de matching disponible."
            )

        else:

            # Le détail tenait dans un tableau, et la justification y
            # était coupée au bord de sa colonne — celle qui porte
            # justement l'honnêteté du moteur : pourquoi cette
            # compétence a ce statut. Elle est désormais lue en
            # entier.
            #
            # Et chaque exigence peut être retrouvée dans l'annonce.
            # Le moteur sait où il l'a reconnue : le montrer rend sa
            # lecture contestable, ce qu'un score seul n'est pas.

            reconnaissances = {
                _canonical_skill_name(detail["canonical_name"]): detail
                for detail in extract_required_skills_detailed(
                    stored_result.get("description", "")
                )
            }

            filtre = st.segmented_control(
                "Filtrer le détail",
                options=[
                    "Tout",
                    "Conditions",
                    "Écarts",
                ],
                default="Tout",
                label_visibility="collapsed",
            )

            for item in result.matches:

                if (
                    filtre == "Conditions"
                    and item.importance != "essentielle"
                ):
                    continue

                if filtre == "Écarts" and item.status not in (
                    "missing",
                    "inferred",
                ):
                    continue

                with st.container(border=True):

                    col_nom, col_statut, col_niveau, col_score = (
                        st.columns([4, 2, 2, 1])
                    )

                    col_nom.markdown(f"**{item.skill}**")

                    col_statut.write(
                        status_labels.get(item.status, item.status)
                    )

                    col_niveau.write(
                        importance_labels.get(
                            item.importance, item.importance
                        )
                    )

                    col_score.write(f"{item.score * 100:.0f} %")

                    st.caption(item.explanation)

                    if item.evidence:
                        st.caption(
                            "Éléments du Master CV : "
                            + " · ".join(item.evidence)
                        )

                    reconnaissance = reconnaissances.get(
                        _canonical_skill_name(item.skill)
                    )

                    if reconnaissance:

                        with st.expander(
                            "Où est-ce écrit dans l'annonce ?"
                        ):

                            st.markdown(
                                _extrait_annonce(
                                    stored_result.get(
                                        "description", ""
                                    ),
                                    reconnaissance["position"],
                                    reconnaissance["matched_alias"],
                                )
                            )

                            if (
                                reconnaissance["matched_alias"].casefold()
                                != item.skill.casefold()
                            ):
                                st.caption(
                                    "Reconnue derrière « "
                                    + reconnaissance["matched_alias"]
                                    + " », synonyme enregistré au "
                                    "référentiel."
                                )

        # ====================================================
        # POINTS FORTS
        # ====================================================

        if result.strengths:

            st.subheader(
                "Points forts"
            )

            for strength in result.strengths:

                st.success(
                    strength
                )

        # ====================================================
        # POINTS DE VIGILANCE
        # ====================================================

        if result.weaknesses:

            st.subheader(
                "Points de vigilance"
            )

            for weakness in result.weaknesses:

                st.warning(
                    weakness
                )

        # ====================================================
        # AVIS IA SUR L'ADEQUATION (OPTIONNEL)
        # ====================================================
        #
        # Ne recalcule rien : met en mots le score et les statuts
        # déjà déterminés ci-dessus par le moteur honnête. Volontaire
        # -ment un avis à part, jamais confondu avec le score officiel.

        st.divider()

        job_offer_id = stored_result["job_offer_id"]
        synthese_key = f"fit_synthesis_{job_offer_id}"

        if not ai_is_configured():

            st.caption(
                "Avis IA sur l'adéquation indisponible — clé "
                "GEMINI_API_KEY absente de .env."
            )

        else:

            if st.button(
                "🔎 Générer un avis IA sur l'adéquation",
                key=f"generer_avis_{job_offer_id}",
            ):

                with st.spinner("Analyse en cours (Gemini)..."):
                    st.session_state[synthese_key] = (
                        generate_fit_synthesis(
                            candidate_id=candidate_id,
                            job_offer_id=job_offer_id,
                        )
                    )

            synthese = st.session_state.get(synthese_key)

            if synthese is not None:

                if synthese.text:

                    st.info(
                        "**Avis IA (indicatif — ne remplace pas "
                        "l'analyse ci-dessus)**\n\n" + synthese.text
                    )

                elif synthese.warning:

                    st.caption(synthese.warning)

    # ========================================================
    # NOUVELLE ANNONCE
    # ========================================================

    st.divider()

    if st.button(
        "Analyser une nouvelle annonce"
    ):

        _new_draft()
