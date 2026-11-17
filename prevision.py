"""Prévision du chiffre d'affaires : saisonnalité de l'an dernier × tendance récente.
Méthode volontairement simple et explicable : on prend le même mois l'an dernier et on applique
la croissance observée sur les 12 derniers mois. La fourchette vient de la variabilité passée."""
import os
import statistics
from calendar import monthrange
from datetime import date, datetime

import matplotlib.pyplot as plt
import matplotlib.ticker
from langchain_core.tools import tool

from outils import DOSSIER_GRAPHES, _connexion_lecture

import re



REQUETE_MENSUELLE = """
SELECT strftime('%Y-%m', c.date) AS mois, SUM(l.quantite * l.prix_unitaire) AS ca
FROM commandes c JOIN lignes_commande l ON l.commande_id = c.id
WHERE c.statut = 'livrée' GROUP BY mois ORDER BY mois"""


def _decaler(mois: str, n: int) -> str:
    a, m = int(mois[:4]), int(mois[5:])
    total = a * 12 + (m - 1) + n
    return f"{total // 12}-{total % 12 + 1:02d}"


def _euros(v: float) -> str:
    return f"{v:,.0f} €".replace(",", " ")


@tool
def prevoir_chiffre_affaires(jusqu_a: str) -> str:
    """Prévoit le chiffre d'affaires (commandes livrées) mois par mois, du mois en cours jusqu'au mois
    jusqu_a INCLUS (format AAAA-MM, ex. "2026-12" pour « d'ici Noël »), avec une fourchette basse/haute
    et le total de la période. Trace aussi le graphique historique + prévision."""
    if not re.fullmatch(r"\d{4}-\d{2}", jusqu_a or ""):
        return "ERREUR : jusqu_a doit être au format AAAA-MM, par exemple 2026-12."
    with _connexion_lecture() as c:
        ca = {m: v for m, v in c.execute(REQUETE_MENSUELLE)}
        derniere = c.execute("SELECT MAX(date) FROM commandes").fetchone()[0]
    if not ca or not derniere:
        return "ERREUR : pas de données de ventes."

    d = date.fromisoformat(derniere)
    mois_en_cours = derniere[:7]
    partiel = d.day < monthrange(d.year, d.month)[1]
    complets = sorted(m for m in ca if not (partiel and m == mois_en_cours))

    # Croissance : 12 derniers mois complets comparés aux mêmes mois un an avant
    paires = [(ca[m], ca[_decaler(m, -12)]) for m in complets[-12:] if _decaler(m, -12) in ca]
    if len(paires) < 3:
        return "ERREUR : pas assez d'historique (il faut au moins 15 mois) pour une prévision fiable."
    croissance = sum(a for a, _ in paires) / sum(b for _, b in paires)
    ecarts = [(a / b) / croissance - 1 for a, b in paires if b]
    marge = min(0.40, max(0.10, statistics.pstdev(ecarts)))

    premier = _decaler(complets[-1], 1)
    if jusqu_a < premier:
        return f"ERREUR : {jusqu_a} est déjà passé. Le premier mois à prévoir est {premier}."
    mois_a_prevoir = []
    while len(mois_a_prevoir) < 12 and (not mois_a_prevoir or mois_a_prevoir[-1] < jusqu_a):
        mois_a_prevoir.append(_decaler(premier, len(mois_a_prevoir)))
    lignes, prev = [], {}
    for m in mois_a_prevoir:
        base = ca.get(_decaler(m, -12))
        if base is None and _decaler(m, -24) in ca:
            base = ca[_decaler(m, -24)] * croissance
        if base is None:
            continue
        v, bas, haut = base * croissance, base * croissance * (1 - marge), base * croissance * (1 + marge)
        note = ""
        if partiel and m == mois_en_cours:   # le mois en cours ne peut pas finir sous ce qui est déjà encaissé
            deja = ca[m]
            v, bas, haut = max(v, deja), max(bas, deja), max(haut, deja)
            note = f" (déjà réalisé : {_euros(deja)} au {d.strftime('%d/%m')})"
        prev[m] = (v, bas, haut)
        lignes.append(f"{m} | {_euros(v)} | {_euros(bas)} | {_euros(haut)}{note}")

    # Graphique : 24 derniers mois réels + prévision en pointillés avec fourchette
    hist = complets[-24:]
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=120)
    bleu, orange = "#2152d9", "#e8710a"
    xs_h = list(range(len(hist)))
    ax.plot(xs_h, [ca[m] for m in hist], color=bleu, linewidth=2.5, marker="o", markersize=4, label="Réalisé")
    mois_prev = list(prev)
    xs_p = list(range(len(hist), len(hist) + len(mois_prev)))
    ax.plot([xs_h[-1]] + xs_p, [ca[hist[-1]]] + [prev[m][0] for m in mois_prev],
            color=orange, linewidth=2.5, linestyle="--", marker="o", markersize=5, label="Prévision")
    ax.fill_between(xs_p, [prev[m][1] for m in mois_prev], [prev[m][2] for m in mois_prev],
                    color=orange, alpha=0.15, label="Fourchette")
    etiquettes = hist + mois_prev
    ax.set_xticks(range(len(etiquettes)))
    ax.set_xticklabels(etiquettes, rotation=45, ha="right")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " ")))
    ax.set_ylabel("€")
    ax.set_title("Chiffre d'affaires : réalisé et prévision", fontsize=15, fontweight="bold", loc="left", pad=14)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    os.makedirs(DOSSIER_GRAPHES, exist_ok=True)
    chemin = os.path.join(DOSSIER_GRAPHES, datetime.now().strftime("graphe_%Y%m%d_%H%M%S_%f.png"))
    fig.savefig(chemin)
    plt.close(fig)

    total = sum(v for v, _, _ in prev.values())
    return (
        f"Méthode : même mois de l'an dernier × croissance des 12 derniers mois ({(croissance - 1) * 100:+.1f} %). "
        f"Fourchette ±{marge * 100:.0f} % (variabilité passée).\n"
        f"Données jusqu'au {d.strftime('%d/%m/%Y')}" + (" (mois en cours incomplet, prévu en entier)." if partiel else ".") + "\n"
        "mois | prévision | bas | haut\n" + "\n".join(lignes) +
        f"\nTotal prévu de {mois_a_prevoir[0]} à {mois_a_prevoir[-1]} : {_euros(total)}\n"
        f"Graphique enregistré : {chemin}"
    )