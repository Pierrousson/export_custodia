def trouver_colonne(colonnes, mots_cles):
    """Retourne le nom de colonne d'origine dont la version normalisée contient un des mots-clés."""
    for c in colonnes:
        if any(m in c.strip().lower() for m in mots_cles):
            return c
    return None
