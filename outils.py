"""Outils de l'agent analyste : lire le schéma, exécuter du SQL en lecture seule, tracer un graphique."""
import os
import re
import sqlite3
import time
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from langchain_core.tools import tool

DB = os.getenv("DATA_DB", "maison_verde.db")
DOSSIER_GRAPHES = "graphiques"
MAX_LIGNES = 50
TIMEOUT_S = 5


def _connexion_lecture():
    """Connexion en LECTURE SEULE : même si l'IA écrit un DELETE, SQLite le refuse."""
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    debut = time.time()
    c.set_progress_handler(lambda: 1 if time.time() - debut > TIMEOUT_S else 0, 10_000)
    return c


def _verifier_requete(sql: str) -> str | None:
    s = sql.strip().rstrip(";").strip()
    if ";" in s:
        return "Une seule requête à la fois."
    if not re.match(r"^(select|with)\b", s, re.IGNORECASE):
        return "Seules les requêtes de lecture (SELECT / WITH) sont autorisées."
    return None


def _executer(sql: str):
    erreur = _verifier_requete(sql)
    if erreur:
        raise ValueError(erreur)
    with _connexion_lecture() as c:
        cur = c.execute(sql.strip().rstrip(";"))
        colonnes = [d[0] for d in cur.description]
        lignes = cur.fetchmany(MAX_LIGNES + 1)
    return colonnes, lignes


@tool
def decrire_base() -> str:
    """Donne la liste des tables, leurs colonnes et 2 lignes d'exemple.
    À appeler en premier pour connaître la structure avant d'écrire du SQL."""
    with _connexion_lecture() as c:
        tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        blocs = []
        for t in tables:
            cols = c.execute(f"PRAGMA table_info({t})").fetchall()
            nb = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            exemples = c.execute(f"SELECT * FROM {t} LIMIT 2").fetchall()
            blocs.append(f"Table {t} ({nb} lignes) : " + ", ".join(f"{col[1]} {col[2]}" for col in cols)
                         + "\n  exemples : " + " | ".join(str(e) for e in exemples))
    return "\n".join(blocs)


@tool
def executer_sql(requete: str) -> str:
    """Exécute une requête SQL (SQLite, lecture seule) et renvoie le résultat sous forme de tableau.
    Maximum 50 lignes : utiliser GROUP BY, ORDER BY et LIMIT pour résumer."""
    try:
        colonnes, lignes = _executer(requete)
    except Exception as e:
        return f"ERREUR SQL : {e} → corrige la requête et réessaie."
    if not lignes:
        return "Aucun résultat."
    tronque = len(lignes) > MAX_LIGNES
    lignes = lignes[:MAX_LIGNES]
    texte = " | ".join(colonnes) + "\n" + "\n".join(" | ".join(str(v) for v in l) for l in lignes)
    return texte + ("\n(résultat tronqué à 50 lignes)" if tronque else "")


@tool
def creer_graphique(requete: str, type_graphique: str, titre: str, label_y: str = "") -> str:
    """Trace un graphique à partir d'une requête SQL qui renvoie exactement 2 colonnes :
    la 1re = les étiquettes (mois, catégorie...), la 2e = la valeur numérique.
    type_graphique : "barres" (comparaison), "barres_horizontales" (classement) ou "ligne" (évolution dans le temps)."""
    if type_graphique not in ("barres", "barres_horizontales", "ligne"):
        return "ERREUR : type_graphique doit être barres, barres_horizontales ou ligne."
    try:
        colonnes, lignes = _executer(requete)
    except Exception as e:
        return f"ERREUR SQL : {e} → corrige la requête et réessaie."
    if len(colonnes) != 2 or not lignes:
        return "ERREUR : la requête doit renvoyer exactement 2 colonnes et au moins une ligne."
    x = [str(l[0]) for l in lignes[:MAX_LIGNES]]
    try:
        y = [float(l[1] or 0) for l in lignes[:MAX_LIGNES]]
    except (TypeError, ValueError):
        return "ERREUR : la 2e colonne doit être numérique."

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=120)
    bleu = "#2152d9"
    if type_graphique == "ligne":
        ax.plot(x, y, color=bleu, linewidth=2.5, marker="o", markersize=4)
        ax.fill_between(range(len(x)), y, alpha=0.08, color=bleu)
    elif type_graphique == "barres":
        ax.bar(x, y, color=bleu)
    else:
        ax.barh(x[::-1], y[::-1], color=bleu)
    ax.set_title(titre, fontsize=15, fontweight="bold", loc="left", pad=14)
    if label_y:
        (ax.set_xlabel if type_graphique == "barres_horizontales" else ax.set_ylabel)(label_y)
    fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " "))
    (ax.xaxis if type_graphique == "barres_horizontales" else ax.yaxis).set_major_formatter(fmt)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x" if type_graphique == "barres_horizontales" else "y", alpha=0.25)
    if type_graphique != "barres_horizontales" and len(x) > 8:
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()

    os.makedirs(DOSSIER_GRAPHES, exist_ok=True)
    chemin = os.path.join(DOSSIER_GRAPHES, datetime.now().strftime("graphe_%Y%m%d_%H%M%S_%f.png"))
    fig.savefig(chemin)
    plt.close(fig)
    return f"Graphique enregistré : {chemin} ({len(x)} points)."


OUTILS = [decrire_base, executer_sql, creer_graphique]