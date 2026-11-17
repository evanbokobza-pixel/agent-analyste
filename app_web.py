"""Interface web de l'agent analyste : les coulisses (SQL, résultats) s'affichent EN DIRECT pendant que l'agent travaille."""
import json
import os
import re
import uuid

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

from agent import graphe, texte_reponse
from outils import DOSSIER_GRAPHES

os.makedirs(DOSSIER_GRAPHES, exist_ok=True)
agent_web = graphe.compile(checkpointer=MemorySaver())

app = FastAPI(title="Agent analyste Maison Lumière")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/graphiques", StaticFiles(directory=DOSSIER_GRAPHES), name="graphiques")

RE_GRAPHE = re.compile(r"graphiques/(graphe_\w+\.png)")


class Question(BaseModel):
    question: str
    session: str | None = None


@app.get("/")
def accueil():
    return FileResponse("static/index.html")


def _evenement(**donnees) -> str:
    """Une ligne JSON par événement (format NDJSON), envoyée au navigateur dès qu'elle est prête."""
    return json.dumps(donnees, ensure_ascii=False) + "\n"


@app.post("/question")
def poser_question(q: Question):
    session = q.session or str(uuid.uuid4())
    config = {"configurable": {"thread_id": session}, "recursion_limit": 25}

    def flux():
        yield _evenement(type="debut", session=session)
        graphiques, reponse = [], ""
        try:
            # stream_mode="updates" : on reçoit la sortie de chaque nœud du graphe dès qu'il a fini
            for maj in agent_web.stream({"messages": [HumanMessage(q.question)]}, config, stream_mode="updates"):
                for noeud, sortie in maj.items():
                    for m in sortie.get("messages", []):
                        if isinstance(m, AIMessage) and m.tool_calls:
                            for tc in m.tool_calls:
                                yield _evenement(type="appel", id=tc["id"], outil=tc["name"],
                                                 requete=tc["args"].get("requete", ""))
                        elif isinstance(m, AIMessage):
                            reponse = texte_reponse(m)
                        elif isinstance(m, ToolMessage):
                            trouve = RE_GRAPHE.search(m.content)
                            if trouve:
                                graphiques.append(f"/graphiques/{trouve.group(1)}")
                            yield _evenement(type="resultat", id=m.tool_call_id, resultat=m.content)
        except Exception as e:
            yield _evenement(type="erreur", message=str(e))
            return
        # le graphique s'affiche déjà dans la page : on retire la phrase qui donne son chemin
        reponse = re.sub(r"[^.\n]*`?graphiques/graphe_\w+\.png`?[^.\n]*\.?", "", reponse).strip()
        yield _evenement(type="fin", reponse=reponse, graphiques=graphiques)

    return StreamingResponse(flux(), media_type="application/x-ndjson")