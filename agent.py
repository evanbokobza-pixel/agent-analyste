"""Agent analyste de données : on pose une question en français, il écrit le SQL, l'exécute, trace un graphique."""
import os
from datetime import date

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from outils import OUTILS
from verif import nombres_non_sources

load_dotenv()

_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_aujourdhui = date.today()

SYSTEME = f"""Tu es un analyste de données pour Maison Lumière, une boutique de décoration et d'art de vivre.
Nous sommes le {_JOURS[_aujourdhui.weekday()]} {_aujourdhui.isoformat()}.

Méthode, à suivre à chaque question :
1. Si tu ne connais pas encore la structure de la base, appelle decrire_base.
2. Écris une requête SQL (dialecte SQLite : dates au format texte AAAA-MM-JJ, utilise strftime) et exécute-la avec executer_sql.
3. Si tu obtiens une ERREUR, lis-la, corrige la requête et réessaie.
4. Vérifie que le résultat est cohérent avant de conclure (ordre de grandeur, période couverte).
5. Si la question porte sur une évolution, une comparaison ou un classement, trace UN graphique avec creer_graphique.

Règles métier :
- Chiffre d'affaires (CA) = SUM(lignes_commande.quantite * lignes_commande.prix_unitaire), uniquement sur les commandes au statut 'livrée', sauf demande contraire.
- Panier moyen = chiffre d'affaires / COUNT(DISTINCT commandes.id), pas une moyenne par ligne.
- Un « trimestre » ou un « mois » sans précision = le dernier complet.

Règles SQL :
- Pour une période, filtre sur la colonne date brute : date >= '2026-04-01' AND date < '2026-07-01'. Ne compare jamais le résultat de strftime à une date complète.
- Tout total, moyenne ou pourcentage se calcule en SQL, jamais de tête.
- Pour compter des éléments, utilise COUNT en SQL. Ne compte jamais les lignes d'un résultat.
- Si un résultat semble incomplet (mois manquant, période plus courte que demandé), suppose que ta requête est fausse et corrige-la.

Règles de réponse :
- N'écris aucun chiffre qui ne figure pas dans un résultat de requête.
- Aucune supposition ni interprétation non vérifiée (pas de « probablement », pas de commentaires sur la clientèle).
- Ne mentionne pas le chemin du fichier graphique : il s'affiche automatiquement.

Réponse finale : en français, courte. Les chiffres clés (avec unités), puis 1 à 3 phrases d'analyse."""


def creer_llm():
    """Choisit le modèle via la variable LLM : claude (par défaut), mistral (API) ou ollama (local)."""
    fournisseur = os.getenv("LLM", "claude")
    if fournisseur == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=os.getenv("OLLAMA_MODEL", "ministral-3:8b"), temperature=0)
    if fournisseur == "mistral":
        from langchain_core.rate_limiters import InMemoryRateLimiter
        from langchain_mistralai import ChatMistralAI
        limiteur = InMemoryRateLimiter(requests_per_second=0.07, check_every_n_seconds=0.5, max_bucket_size=1)
        return ChatMistralAI(
            model=os.getenv("MISTRAL_MODEL", "ministral-8b-2512"),
            temperature=0,
            rate_limiter=limiteur,   # environ 4 appels par minute (offre gratuite)
            max_retries=0,
        )
    return ChatAnthropic(model="claude-haiku-5-5", max_tokens=2048)


modele = creer_llm().bind_tools(OUTILS)


def agent(etat: MessagesState):
    return {"messages": [modele.invoke([SystemMessage(SYSTEME)] + etat["messages"])]}


# ---------- Nœud de vérification ----------

MARQUEUR = "[VÉRIFICATION]"
MAX_VERIFS = 2
VERIF = os.getenv("VERIF", "1") == "1"   # VERIF=0 pour désactiver et comparer


def est_verif(m) -> bool:
    return isinstance(m, HumanMessage) and str(m.content).startswith(MARQUEUR)


def messages_du_tour(messages):
    """Messages depuis la dernière vraie question de l'utilisateur."""
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage) and not est_verif(messages[i]):
            return messages[i:]
    return messages


def verifier(etat: MessagesState):
    """Renvoie la réponse à l'agent si elle cite des chiffres qui ne viennent d'aucune requête."""
    tour = messages_du_tour(etat["messages"])
    if sum(est_verif(m) for m in tour) >= MAX_VERIFS:
        return {}
    suspects = nombres_non_sources(texte_reponse(tour[-1]), tour)
    if not suspects:
        return {}
    liste = ", ".join(f"{n:g}" for n in suspects)
    return {"messages": [HumanMessage(
        f"{MARQUEUR} Ta réponse contient des chiffres qui ne viennent d'aucun résultat de requête : {liste}. "
        "Pour chacun, soit tu le calcules avec une requête SQL, soit tu le retires. "
        "Puis redonne ta réponse finale complète."
    )]}


def router(etat: MessagesState):
    if etat["messages"][-1].tool_calls:
        return "outils"
    return "verifier" if VERIF else END


def apres_verif(etat: MessagesState):
    return "agent" if est_verif(etat["messages"][-1]) else END


graphe = StateGraph(MessagesState)
graphe.add_node("agent", agent)
graphe.add_node("outils", ToolNode(OUTILS))
graphe.add_node("verifier", verifier)
graphe.add_edge(START, "agent")
graphe.add_conditional_edges("agent", router, ["outils", "verifier", END])
graphe.add_edge("outils", "agent")
graphe.add_conditional_edges("verifier", apres_verif, ["agent", END])
app = graphe.compile()


# ---------- Affichage ----------

def texte_reponse(msg) -> str:
    if isinstance(msg.content, str):
        return msg.content
    return "\n".join(b.get("text", "") for b in msg.content if isinstance(b, dict) and b.get("type") == "text")


def afficher_coulisses(messages):
    for m in messages:
        if isinstance(m, AIMessage):
            for tc in m.tool_calls:
                detail = tc["args"].get("requete", "") or ""
                print(f"   🔧 {tc['name']}" + (f"\n      {detail.strip()}" if detail else ""))
        elif isinstance(m, ToolMessage):
            apercu = m.content if len(m.content) < 300 else m.content[:300] + " …"
            print("      → " + apercu.replace("\n", "\n        "))
        elif est_verif(m):
            print(f"   🛡️ {m.content}")


if __name__ == "__main__":
    if not os.path.exists(os.getenv("DATA_DB", "maison_verde.db")):
        raise SystemExit("Base absente : lance d'abord  python donnees.py")
    historique = []
    print("Agent analyste — pose ta question (vide pour quitter)\n")
    while True:
        question = input("Toi : ").strip()
        if not question:
            break
        historique.append(HumanMessage(question))
        resultat = app.invoke({"messages": historique}, {"recursion_limit": 25})
        nouveaux = resultat["messages"][len(historique):]
        print("\n--- coulisses ---")
        afficher_coulisses(nouveaux)
        print("-----------------\n")
        print("Agent :", texte_reponse(resultat["messages"][-1]), "\n")
        historique = resultat["messages"]