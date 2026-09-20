# Termes

Petit glossaire pour le chat d’aide et l’éditeur.

## Graphe / réseau

Document enregistré de nœuds et d’arêtes. Tu l’édites dans l’éditeur, tu gères les copies dans la bibliothèque. Le réseau **actif** est celui de la sélection rapide — seul celui-là démarre avec **Démarrer**.

## Exécution (run)

Un passage du graphe actif. Il en tourne au plus **une**. Démarrer et arrêter dans l’en-tête. Résultats : en cours, succès, erreur, annulé, délai dépassé.

## Nœuds et arêtes

Briques (entrée de chat, agent, LLM, outil, connaissances, routeur, fin) et connexions typées. Des flèches arbitraires entre cases sont invalides.

## Agent

Nœud avec invite système. Modèle, message, outils et connaissances viennent par des ports, pas comme clés embarquées.

## Nœud LLM

Choisit fournisseur et modèle. Local via Ollama, sinon cloud ou URL compatible OpenAI plus identifiant.

## Entrée de chat

Seul point d’entrée du texte utilisateur dans l’exécution. Au plus une par réseau. Le chat de supervision écrit ici.

## Outil

First-party (HTTP, recherche web, date/heure, calculatrice) ou MCP. Configuration dans l’inspecteur, exécution seulement pendant le run.

## Connaissances (réseau)

Nœud knowledge : dossier **sous** le dossier de données de l’app. Index propre, topK et score. **Pas** le corpus d’aide. Pas la racine du lecteur.

## Aide-RAG

Documents dans le dossier d’aide du dossier de données (guides par défaut plus tes Markdown). Uniquement le chatbot d’aide. Après modifications, reconstruire l’index sous Paramètres → Chat d’aide.

## Identifiant / credential

Clé stockée dans le coffre Windows. Dans les listes, seulement un masque. Dans le graphe, seulement l’ID/le choix, jamais le secret. L’export ne contient pas de mots de passe.

## MCP

Model Context Protocol : serveurs d’outils externes. À créer et activer dans Paramètres, à relier dans le graphe comme nœud d’outil de type MCP. L’aide n’utilise pas MCP.

## Fournisseur

`ollama` (local), `xai`, `openai`, `anthropic` (Claude), `gemini` (cloud, clé API d’abord, puis liste de modèles), `openai_compat` (API HTTP compatible maison, p. ex. LM Studio).

## Ollama

Service séparé pour modèles locaux. L’app est le client. Le setup peut créer Ollama et deux petits modèles par défaut. Fermer l’app laisse Ollama tourner.

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
