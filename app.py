import io
import re
import zipfile
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from docx_export import REQUIRED_COLUMNS, generate_catalogue, inventory_key

DATA_DIR = Path(__file__).parent / "data"

CATEGORIES = {
    "Dessin": "dessin.csv",
    "Estampe": "estampe.csv",
    "Objet": "objet.csv",
    "Peinture": "peinture.csv",
    "Historical metadata": "historical_metadata.csv",
    "Lettres et manuscripts": "manuscript.csv",
}

URL_TEMPLATE = "https://maior-images.memorix.nl/cus/thumb/1000x1000/{uuid}.jpg"

st.set_page_config(page_title="Téléchargement d'images - Collection", page_icon="🖼️")
st.title("🖼️ Téléchargement d'images de la collection")


@st.cache_data
def charger_reference(nom_fichier: str):
    chemin = DATA_DIR / nom_fichier
    if not chemin.exists():
        return None
    df = pd.read_csv(chemin, sep=";", encoding="utf-8-sig", dtype=str)
    df.columns = [c.strip() for c in df.columns]  # on garde la casse d'origine
    return df


def trouver_colonne(colonnes, mots_cles):
    """Retourne le nom de colonne d'origine dont la version normalisée contient un des mots-clés."""
    for c in colonnes:
        if any(m in c.strip().lower() for m in mots_cles):
            return c
    return None


# --- Étape 1 : catégorie ---
st.header("1. Choisir la catégorie")
categorie = st.selectbox("Catégorie", list(CATEGORIES.keys()))

reference_df = charger_reference(CATEGORIES[categorie])

if reference_df is None:
    st.warning(
        f"Le fichier de référence `{CATEGORIES[categorie]}` est introuvable dans le dossier "
        "`data/` de l'application. Vous pouvez le déposer ci-dessous pour cette session."
    )
    fichier_ref = st.file_uploader(
        f"Déposer le CSV de référence pour « {categorie} »", type="csv", key="ref"
    )
    if fichier_ref:
        reference_df = pd.read_csv(fichier_ref, sep=";", encoding="utf-8-sig", dtype=str)
        reference_df.columns = [c.strip() for c in reference_df.columns]

if reference_df is None:
    st.stop()

col_inv_ref = trouver_colonne(reference_df.columns, ["inventaire", "inventory"])
col_img_ref = trouver_colonne(reference_df.columns, ["image"])

if not col_inv_ref or not col_img_ref:
    st.error("Le CSV de référence doit contenir une colonne numéro d'inventaire et une colonne UUID image.")
    st.stop()

st.success(f"{len(reference_df)} notices chargées pour « {categorie} ».")

# --- Étape 2 : saisie des numéros d'inventaire ---
st.header("2. Fournir les numéros d'inventaire")
mode = st.radio("Méthode", ["Importer un CSV", "Coller une liste"])

numeros = []

if mode == "Importer un CSV":
    fichier = st.file_uploader("CSV avec une colonne « Inventory Number »", type="csv", key="input")
    if fichier:
        df_in = pd.read_csv(fichier, dtype=str)
        df_in.columns = [c.strip() for c in df_in.columns]
        col_in = trouver_colonne(df_in.columns, ["inventaire", "inventory"])
        if not col_in:
            st.error("Colonne « Inventory Number » introuvable dans le fichier importé.")
        else:
            numeros = df_in[col_in].dropna().astype(str).str.strip().tolist()
else:
    texte = st.text_area("Un numéro d'inventaire par ligne")
    if texte:
        numeros = [l.strip() for l in texte.splitlines() if l.strip()]

numeros = list(dict.fromkeys(numeros))  # dédoublonne en gardant l'ordre

if numeros:
    st.write(f"{len(numeros)} numéro(s) d'inventaire fourni(s).")

    ref_lookup = dict(
        zip(
            reference_df[col_inv_ref].astype(str).str.strip(),
            reference_df[col_img_ref].astype(str).str.strip(),
        )
    )

    trouves = []
    manquants = []
    for n in numeros:
        uuid_img = ref_lookup.get(n)
        if uuid_img and re.fullmatch(r"[0-9a-f-]{36}", uuid_img, re.I):
            trouves.append((n, uuid_img))
        else:
            manquants.append(n)

    st.write(f"✅ {len(trouves)} image(s) trouvée(s) — ❌ {len(manquants)} sans image trouvée")
    if manquants:
        with st.expander("Voir les numéros sans correspondance"):
            st.write(manquants)

    # --- Étape 3 : téléchargement des images ---
    st.header("3. Télécharger les images")
    if trouves and st.button("Préparer le ZIP des images"):
        zip_buffer = io.BytesIO()
        progress = st.progress(0)
        erreurs = []
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, (inv, uuid_img) in enumerate(trouves):
                url = URL_TEMPLATE.format(uuid=uuid_img)
                try:
                    r = requests.get(url, timeout=15)
                    r.raise_for_status()
                    nom_fichier = f"{inv}_{uuid_img}.jpg".replace("/", "-")
                    zf.writestr(nom_fichier, r.content)
                except Exception as e:
                    erreurs.append(f"{inv} ({uuid_img}) : {e}")
                progress.progress((i + 1) / len(trouves))

        zip_buffer.seek(0)
        st.success(f"{len(trouves) - len(erreurs)} image(s) téléchargée(s) avec succès.")
        if erreurs:
            with st.expander(f"{len(erreurs)} erreur(s) de téléchargement"):
                st.write(erreurs)

        st.download_button(
            "⬇️ Télécharger le ZIP",
            data=zip_buffer,
            file_name=f"images_{categorie.lower().replace(' ', '_')}.zip",
            mime="application/zip",
        )

    # --- Étape 4 : catalogue Word (DOCX) ---
    st.header("4. Générer un catalogue Word (DOCX)")

    colonnes_manquantes = REQUIRED_COLUMNS - set(reference_df.columns)
    if colonnes_manquantes:
        st.info(
            "Cette fonctionnalité n'est pour l'instant disponible que pour les CSV contenant "
            "toutes les colonnes du catalogue complet (actuellement : Estampe). "
            f"Colonnes manquantes pour « {categorie} » : {', '.join(sorted(colonnes_manquantes))}"
        )
    else:
        lignes_par_numero = {
            str(r[col_inv_ref]).strip(): r.to_dict() for _, r in reference_df.iterrows()
        }
        a_generer = []
        for n in numeros:
            row = lignes_par_numero.get(n)
            if row:
                row.setdefault("Inventory Number", row.get(col_inv_ref, n))
                uuid_img = str(row.get(col_img_ref) or "").strip()
                a_generer.append((row, uuid_img))
        a_generer.sort(key=lambda item: inventory_key(item[0]))

        st.write(f"{len(a_generer)} notice(s) sur {len(numeros)} trouvée(s) dans le CSV de référence.")

        if a_generer and st.button("Générer le catalogue DOCX"):
            with st.spinner("Génération du document (téléchargement des images inclus)..."):
                buffer = generate_catalogue(a_generer)
            st.download_button(
                "⬇️ Télécharger le catalogue DOCX",
                data=buffer,
                file_name=f"catalogue_{categorie.lower().replace(' ', '_')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
