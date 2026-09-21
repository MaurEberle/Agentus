# Termes

Petit glossaire pour le chat d’aide et l’éditeur.

## Graphe / réseau

Document enregistré de nœuds et d’arêtes. Tu l’édites dans l’éditeur, tu gères les copies dans la bibliothèque. Le réseau **actif** est celui de la sélection rapide — seul celui-là démarre avec **Démarrer**.

## Exécution (run)

Un passage du graphe actif. Il en tourne au plus **une**. Démarrer et arrêter dans l’en-tête. Résultats : en cours, succès, erreur, annulé, délai dépassé.

## Nœuds et arêtes

Briques (chat, orchestrateur, agent, LLM, outil, connaissances, routeur, fin) et connexions typées. Des flèches arbitraires entre cases sont invalides.

## Agent

Nœud avec invite système. Modèle, message, outils et connaissances arrivent par des ports. Sans orchestrateur, le message le démarre, et message ou transfert transmet la réponse. Avec orchestrateur, il tient à son propre canal : une tâche entre, un résultat revient.

## Nœud LLM

Choisit fournisseur et modèle. Local via Ollama, sinon cloud plus identifiant.

## Chat

Seul point d’entrée du texte utilisateur dans l’exécution. Au plus un par réseau. Le chat de supervision écrit ici. Avec orchestrateur, la conversation reste ouverte sur plusieurs messages.

## Orchestrateur

Nœud avec son propre LLM. Il est la seule voix du chat de l’exécution, pose des questions et appelle les agents reliés un par un, chacun par un canal. Au plus un. Le chat ne se branche que sur lui. Sa sortie message va vers Fin ou un routeur. Tu ne vois ni les textes des agents ni les ordres internes comme bulles. L’app joint le dernier résultat à la tâche suivante. Un agent est sur le canal ou dans la chaîne de messages.

## Outil

First-party (HTTP, recherche web, date/heure, calculatrice, accès aux fichiers) ou MCP. L’accès aux fichiers reste dans un dossier racine, pas à la racine d’un lecteur. Configuration dans l’inspecteur, exécution seulement pendant le run.

## Connaissances (réseau)

Nœud de connaissances : un dossier de textes pour le réseau. Il peut être n’importe où, sauf une racine de lecteur ou de système et le corpus d’aide. Modèle d’embeddings, index, topK et score propres. **Pas** le corpus d’aide. Au démarrage tu vois l’indexation ; un index déjà à jour est sauté.

## Aide-RAG

Documents dans le dossier d’aide du dossier de données (guides par défaut plus tes Markdown). Uniquement le chatbot d’aide. Après modifications, reconstruire l’index sous Paramètres → Chat d’aide.

## Identifiant / credential

Clé stockée dans le coffre Windows. Dans les listes, seulement un masque. Dans le graphe, seulement l’ID/le choix, jamais le secret. L’export ne contient pas de mots de passe.

## MCP

Model Context Protocol : serveurs d’outils externes. À créer et activer dans Paramètres, à relier dans le graphe comme nœud d’outil de type MCP. L’aide n’utilise pas MCP.

## Fournisseur

Dans la liste : `ollama` (local), `xai`, `openai`, `anthropic` (Claude), `gemini` (cloud : identifiant d’abord, puis la liste de modèles). Embeddings : Ollama, OpenAI, Gemini. `openai_compat` reste valable pour d’anciens graphes et identifiants, mais n’est plus dans la liste de modèles.

## Ollama

Service séparé pour modèles locaux. L’app est le client. S’il est installé, que l’adresse est locale et que le port ne répond pas, l’app le démarre et ne l’arrête pas. Le setup peut créer Ollama, attendre un court instant et charger deux petits modèles par défaut s’il répond.

## Tableau de bord, supervision, historique

Tableau de bord = aperçu et configuration. Supervision = direct. Historique = archive. Pas la même page trois fois.

## Valide / invalide

Validation du graphe. Invalide enregistrable, mais inadapté au démarrage. Seul un réseau valide peut être défini comme actif.

## Sélection rapide

Choix dans l’en-tête du réseau actif. Équivaut à « Définir comme actif » dans la bibliothèque.

## Mode économique

L’aide bascule sur le modèle de repli si le modèle principal ne tient pas. Le tableau de bord peut l’afficher sous Environnement.

## Portable

`portable.txt` à côté de l’EXE : données à côté de l’application. Copie installée : données dans le dossier de l’app, programmes à part.
