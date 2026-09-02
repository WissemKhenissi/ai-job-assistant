import streamlit as st

from services.profile_service import (
    get_candidate,
    get_experiences,
)

from ui.job_matching import render_job_matching_page
from ui.master_cv import render_master_cv_page


st.set_page_config(
    page_title="AI Job Assistant",
    page_icon="🤖",
    layout="wide"
)


# ============================================================
# DONNÉES
# ============================================================

candidate = get_candidate()
experiences = get_experiences()


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


