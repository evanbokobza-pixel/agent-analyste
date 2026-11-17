"""Détection des chiffres non sourcés, partagée entre l'agent et le banc d'essai."""
import re

from langchain_core.messages import ToolMessage

TOLERANCE = 0.01  # 1 % d'écart accepté


def nombres(texte: str) -> list[float]:
    """Extrait les nombres d'un texte en français : '123 456,78 €' -> 123456.78"""
    t = str(texte).replace("\u202f", " ").replace("\xa0", " ")
    t = re.sub(r"(?<=\d) (?=\d{3}\b)", "", t)  # espaces des milliers
    t = t.replace(",", ".")
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]


def nombres_non_sources(reponse: str, messages) -> list[float]:
    """Nombres cités dans la réponse qui n'apparaissent dans aucun résultat d'outil."""
    sources = []
    for m in messages:
        if isinstance(m, ToolMessage):
            sources += nombres(m.content)
    suspects = []
    for n in nombres(reponse):
        if n <= 12:  # numérotation de liste, mois, petits entiers
            continue
        if not any(abs(n - s) <= max(1, abs(s) * TOLERANCE) for s in sources):
            suspects.append(n)
    return suspects