"""
Point d'entrée de l'application.

Ne contient que ce qui vaut pour toutes les pages : le profil courant,
la barre latérale, et le lancement de la page choisie. Les pages
elles-mêmes sont décrites dans ui/navigation.py.
"""

from pathlib import Path

import streamlit as st

from services.profile_service import (
    get_candidate,
    get_experiences,
)

from ui.candidate_switcher import (
    profil_courant,
    render_candidate_switcher,
)
from ui.navigation import construire_navigation


st.set_page_config(
    page_title="AI Job Assistant",
    page_icon="🤖",
    layout="wide",
)

# Le nom du produit vit ici, dans l'emplacement que Streamlit réserve
# au-dessus du menu. Il était auparavant réaffiché en tête de chaque
# page, avec son sous-titre : deux cents pixels de hauteur utile
# consommés à chaque écran pour rappeler où l'on est déjà.
st.logo(str(Path(__file__).parent / "assets" / "logo.svg"), size="large")


# ============================================================
# PROFIL COURANT
# ============================================================
#
# Résolu avant toute chose : la navigation se construit à partir de
# lui, et chaque page le reçoit explicitement. Aucune ne devine « le
# premier candidat de la base ».

candidate_id = profil_courant()

if candidate_id is None:

    st.title("🤖 AI Job Assistant")

    render_candidate_switcher()

    st.info(
        "Aucun profil n'existe encore. Créez-en un depuis le menu "
        "de gauche, puis importez votre CV pour l'amorcer."
    )

    st.stop()

candidate = get_candidate(candidate_id)

experiences = get_experiences(candidate_id)


# ============================================================
# BARRE LATERALE
# ============================================================
#
# Streamlit place toujours le menu en haut de la barre latérale, quel
# que soit l'ordre des appels. Ce qui suit s'affiche donc en dessous :
# ici le sélecteur de profil.

page = construire_navigation(candidate, experiences)

st.sidebar.divider()

render_candidate_switcher()


# ============================================================
# PAGE COURANTE
# ============================================================

page.run()
