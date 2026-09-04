import streamlit as st

from services.profile_service import (
    get_candidate,
    get_experiences,
)

from ui.candidate_switcher import render_candidate_switcher
from ui.job_matching import render_job_matching_page
from ui.master_cv import render_master_cv_page


st.set_page_config(
    page_title="AI Job Assistant",
    page_icon="🤖",
    layout="wide"
)


# ============================================================
# HEADER
# ============================================================

st.title("🤖 AI Job Assistant")

st.write(
    "Ton assistant intelligent pour construire, adapter "
    "et suivre tes candidatures."
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Aller vers",
    [
        "Mon Master CV",
        "Mes candidatures",
    ]
)

st.sidebar.divider()

# Le profil courant est choisi ici et passé explicitement aux pages :
# aucune ne doit deviner « le premier candidat de la base ».
candidate_id = render_candidate_switcher()


# ============================================================
# DONNÉES
# ============================================================

if candidate_id is None:

    st.info(
        "Aucun profil n'existe encore. Créez-en un depuis le menu "
        "de gauche, puis importez votre CV pour l'amorcer."
    )

    st.stop()

candidate = get_candidate(candidate_id)

experiences = get_experiences(candidate_id)


# ============================================================
# PAGE : MON MASTER CV
# ============================================================

if page == "Mon Master CV":

    render_master_cv_page(candidate, experiences)


# ============================================================
# PAGE : MES CANDIDATURES
# ============================================================

elif page == "Mes candidatures":
    render_job_matching_page(candidate.id)
