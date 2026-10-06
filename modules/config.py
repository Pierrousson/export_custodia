"""Configuration partagée par les modules de l'application."""

from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CATEGORIES = {
    "Dessin": "dessin.csv",
    "Estampe": "estampe.csv",
    "Objet": "objet.csv",
    "Peinture": "peinture.csv",
    "Historical metadata": "historical_metadata.csv",
    "Lettres et manuscripts": "manuscript.csv",
}

URL_TEMPLATE = "https://maior-images.memorix.nl/cus/thumb/1000x1000/{uuid}.jpg"
