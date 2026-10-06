import io
import re
import time
import webbrowser
import zipfile
import pandas as pd
import requests
import streamlit as st

from modules.config import CATEGORIES, URL_TEMPLATE
from modules.import_csv import trouver_colonne
from modules.load_data import charger_reference

def telecharger_images():
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
    mode = st.radio("Méthode", ["Coller une liste", "Importer un CSV"])

    numeros = []

    if mode == "Importer un CSV":
        fichier = st.file_uploader("CSV avec une colonne « Inventory Number »", type="csv", key="input")
        if fichier:
            df_in = pd.read_csv(fichier, dtype=str, sep=";")
            df_in.columns = [c.strip() for c in df_in.columns]
            col_in = "Inventory Number" if "Inventory Number" in df_in.columns else None
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
        definition_image = st.radio("Choisir la définition", ["Définition basse", "Définition haute"])
        if definition_image == "Définition basse":
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
                            nom_fichier = re.sub(r"[^\w.-]", "_", f"{inv}_{uuid_img}.jpg")
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
        if definition_image == "Définition haute":
            st.warning("attention déconseillé car ouvre des fenêtres dans le navigateur")
            if trouves and st.button("Ouvrir les images en définition haute"):
                base_url = "https://cus.maior.memorix.nl"
                size = "maiorfullsize"
                entries = [
                    {"image_uuid": uuid_img, "file_name": inv}
                    for inv, uuid_img in trouves
                ]

                for i, e in enumerate(entries):
                    uuid_img = e["image_uuid"]
                    name = re.sub(r"[^\w-]", "_", e["file_name"])
                    url = (
                        f"{base_url}/api/file/download/"
                        f"tenant/cus/uuid/{uuid_img}/size/{size}/ext/jpg/locale/en"
                    )

                    st.write(f"[{i + 1}/{len(entries)}] {name}")
                    webbrowser.open_new_tab(url)
                    time.sleep(0.2)
    
