"""Banc d'essai : mesure le taux de bonnes réponses de l'agent (Claude vs Mistral, avec ou sans vérification)."""
import json
import os
import sqlite3
import time

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent import MARQUEUR, VERIF, graphe, texte_reponse
from verif import TOLERANCE, nombres, nombres_non_sources

DB = os.getenv("DATA_DB", "maison_verde.db")


def valeur_attendue(sql: str):
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as c:
        return c.execute(sql).fetchone()[0]


def est_correct(reponse: str, attendu) -> bool:
    if isinstance(attendu, str):
        return attendu.lower() in reponse.lower()
    return any(abs(n - attendu) <= max(1, abs(attendu) * TOLERANCE) for n in nombres(reponse))


def requetes_sql(messages) -> list[str]:
    """Toutes les requêtes SQL écrites par l'agent, sur une seule ligne chacune."""
    return [" ".join(tc["args"]["requete"].split())
            for m in messages if isinstance(m, AIMessage)
            for tc in m.tool_calls if tc["args"].get("requete")]


def main():
    agent = graphe.compile()
    with open("questions.json", encoding="utf-8") as f:
        questions = json.load(f)

    bonnes, erreurs_sql, total_suspects, verifs, debut = 0, 0, 0, 0, time.time()
    for q in questions:
        attendu = valeur_attendue(q["sql"])
        messages = []
        try:
            res = agent.invoke({"messages": [HumanMessage(q["question"])]}, {"recursion_limit": 25})
            messages = res["messages"]
            reponse = texte_reponse(messages[-1])
            erreurs_sql += sum(1 for m in messages
                               if isinstance(m, ToolMessage) and m.content.startswith("ERREUR"))
            verifs += sum(1 for m in messages
                          if isinstance(m, HumanMessage) and str(m.content).startswith(MARQUEUR))
        except Exception as e:
            reponse = f"[PLANTAGE] {e}"

        ok = est_correct(reponse, attendu)
        suspects = nombres_non_sources(reponse, messages)
        bonnes += ok
        total_suspects += len(suspects)

        print(f"{'✅' if ok else '❌'} {q['question']}\n   attendu : {attendu}\n   réponse : {reponse[:200]}")
        if suspects:
            print(f"   ⚠️ chiffres non sourcés : {suspects}")
        if not ok:
            for sql in requetes_sql(messages):
                print(f"   🔍 SQL : {sql}")
        print()
        time.sleep(3)

    nom = os.getenv("MISTRAL_MODEL", "ministral-14b-2512") if os.getenv("LLM") == "mistral" else "claude"
    print(f"Modèle : {nom} | vérif : {'oui' if VERIF else 'non'} | Score : {bonnes}/{len(questions)} "
          f"| chiffres non sourcés : {total_suspects} | vérifications : {verifs} "
          f"| erreurs SQL : {erreurs_sql} | durée : {time.time() - debut:.0f} s")


if __name__ == "__main__":
    main()