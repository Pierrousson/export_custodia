import io
import re
import streamlit as st

from modules.download_images import telecharger_images

st.set_page_config(page_title="Export Custodia", page_icon="🖼️")
st.title("🖼️ Téléchargement d'images de la collection")

tab1, tab2, tab3 = st.tabs(["Téléchargement d'images", "Téléchargement des cartes d'inventaire", "Export Word de la base"])

with tab1:
    telecharger_images()
