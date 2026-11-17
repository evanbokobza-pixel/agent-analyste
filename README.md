# Agent analyste de données — LangGraph + modèles souverains

Un agent qui répond en français à des questions business sur une base SQL : il découvre la structure de la base, écrit la requête, l'exécute, se corrige en cas d'erreur et trace un graphique si besoin.

Le projet sert surtout de **banc d'essai** pour une question précise : **comment garder des réponses fiables avec un petit modèle**, par exemple Ministral 8B en local, au lieu d'un grand modèle propriétaire ?

## Fonctionnement

```
question ──> agent ──(appel d'outil)──> outils ──> agent
               └──(réponse finale)──> vérificateur ──(chiffres non sourcés)──> agent
                                           └──(tout est sourcé)──> réponse
```

- **Boucle ReAct (LangGraph)** avec trois outils : `decrire_base`, `executer_sql`, `creer_graphique`.
- **Nœud de vérification** : chaque nombre cité dans la réponse doit apparaître dans un résultat de requête. Sinon, la réponse est renvoyée à l'agent (2 fois au maximum).
- **Modèle interchangeable** : Claude (API), Mistral (API) ou Mistral en local via Ollama, avec la variable `LLM`.

## Sécurité

Les garde-fous sont dans le code, pas dans le prompt :
- connexion SQLite en **lecture seule** ;
- uniquement des requêtes `SELECT` / `WITH`, une seule à la fois ;
- timeout de 5 secondes par requête ;
- résultats limités à 50 lignes, avec un avertissement explicite en cas de troncature.

## Banc d'essai

`eval.py` pose 10 questions dont la bonne réponse est calculée par une requête SQL de référence (`questions.json`). Il mesure :
- le **score** (bonne valeur dans la réponse) ;
- les **chiffres non sourcés** (nombres absents de tous les résultats de requête) ;
- le nombre de **vérifications** déclenchées et d'**erreurs SQL** corrigées.

### Résultats (Ministral 8B en local, Ollama)

| Version | Score | Chiffres non sourcés |
|---|---|---|
| Prompt de base, sans vérification | 8/10 | 2 |
| Avec nœud de vérification | 8/10 | 0 |
| + règles SQL (COUNT, dates) et troncature explicite | 10/10 | 0 |

*Résultats sur un lancement par configuration ; les sorties d'un LLM varient d'un lancement à l'autre.*

### Erreurs typiques observées sur les petits modèles
- **Chiffres inventés** dans le commentaire (dates, moyennes) : corrigé par le nœud de vérification.
- **Requêtes fausses** : comparaison de `strftime('%Y-%m')` avec une date complète (un mois exclu), moyenne par ligne au lieu de par commande, sous-requête qui compte plusieurs fois les ventes, lignes comptées dans un résultat tronqué à 50. Corrigé par des règles métier explicites et un message de troncature clair.

## Limites et pistes
- Le vérificateur contrôle les **nombres**, pas les **affirmations qualitatives** (« en hausse », « probablement »). Prochaine étape : un juge ou une réponse limitée aux faits.
- Contrôle de vraisemblance des résultats (un CA mensuel ne peut pas dépasser le CA total).
- Plusieurs lancements par configuration pour mesurer la variance.

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install langgraph langchain-anthropic langchain-mistralai langchain-ollama python-dotenv matplotlib fastapi uvicorn
python donnees.py            # génère la base de démo (boutique fictive)
```

Clés dans un fichier `.env` (non versionné) : `ANTHROPIC_API_KEY=...`, `MISTRAL_API_KEY=...`

## Utilisation

```bash
python agent.py                                   # agent en ligne de commande (Claude)
LLM=ollama python agent.py                        # Mistral en local (ollama pull ministral-3:8b)
VERIF=0 LLM=ollama python eval.py                 # banc d'essai sans vérification
VERIF=1 LLM=ollama python eval.py                 # banc d'essai avec vérification
uvicorn app_web:app --reload                      # interface web avec les coulisses en direct
```

## Structure

| Fichier | Rôle |
|---|---|
| `agent.py` | graphe LangGraph, prompt, nœud de vérification |
| `outils.py` | outils SQL et graphique, garde-fous |
| `verif.py` | détection des chiffres non sourcés |
| `eval.py` / `questions.json` | banc d'essai |
| `donnees.py` | génération de la base de démo |
| `app_web.py` / `static/` | interface web |