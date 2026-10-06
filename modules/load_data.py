import pandas as pd
import streamlit as st

from modules.config import DATA_DIR


@st.cache_data
def charger_reference(nom_fichier: str):
    chemin = DATA_DIR / nom_fichier
    if not chemin.exists():
        return None
    df = pd.read_csv(chemin, sep=";", encoding="utf-8-sig", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    return df
