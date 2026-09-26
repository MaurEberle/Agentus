# Agentus Network — guide rapide

Agentus Network est une **application de bureau locale**. Sur ce PC tu construis des réseaux d’agents, de modèles de langue et d’outils, tu lances **une** exécution et tu la suis en direct. L’interface appartient à l’app (sa propre fenêtre), pas à Chrome ni à une page `file://`.

Ollama est un **service à part**. Fermer ou désinstaller Agentus Network n’arrête pas Ollama et ne supprime pas les modèles. S’il est installé sur ce PC, que l’adresse dans Paramètres est locale et que le service est arrêté, l’app le démarre à l’ouverture de la fenêtre.

## Fenêtre et navigation

À gauche (sur téléphone : menu burger) :

- **Tableau de bord** — accueil, configuration, réseau actif, dernières exécutions
- **Réseau** — éditeur (un graphe)
- **Bibliothèque** — tous les réseaux enregistrés
- **Supervision** — exécution en direct
- **Historique** — exécutions terminées et statistiques

**Paramètres** sont dans l’en-tête (engrenage), pas dans la navigation de gauche.

Dans l’en-tête aussi : **Démarrer** / **Arrêter**, **sélection rapide** du réseau actif, cloche (notifications), clair/sombre/système, langue (Deutsch, English, Español, Français, Türkçe, Português, 中文, 日本語, العربية) et boutons de fenêtre (réduire, agrandir, fermer).

Glisse le logo ou l’en-tête vide pour déplacer la fenêtre. Démarrer, Arrêter, la sélection rapide et les boutons à droite ne sont pas des zones de glisser.

## Premier parcours

1. Ollama doit être joignable. L’app démarre elle-même un service local s’il est installé mais arrêté. Le setup peut créer Ollama, le lancer brièvement en arrière-plan et récupérer les petits modèles `nomic-embed-text` et `llama3.2:1b`, seulement s’il répond. Un setup silencieux sans l’option modèles ne télécharge rien. Un téléchargement raté termine quand même le setup avec succès.
2. Sous **Paramètres → Runtime**, vérifie la connexion ; la liste des modèles ne doit pas être vide.
3. Sous **Paramètres → Chat d’aide**, choisis le fournisseur et le modèle de chat (défaut : Ollama + `llama3.2:1b`). Les embeddings sont **un autre** modèle (`nomic-embed-text`).
4. Dans la **Bibliothèque** ou l’éditeur, crée un réseau, enregistre-le et **active-le** dans la sélection rapide.
5. **Démarrer** dans l’en-tête. L’exécution se voit sous **Supervision**.

Le tableau de bord affiche les étapes manquantes comme cartes de configuration.

## Un réseau minimal

Dans l’éditeur (**Réseau**) au moins :

1. **Chat** (`chat_input`) — au plus un
2. **Agent** — invite système
3. **LLM** — fournisseur et modèle
4. **Fin** (`end`) — au moins une

Connexions (ports typés, pas de flèches arbitraires) :

- Chat **Message** → Agent **Message**
- LLM **LLM** → Agent **LLM**
- Agent **Message** → Fin

**Orchestrateur** optionnel : le chat seulement vers l’orchestrateur, un LLM vers l’orchestrateur, un **Canal** de l’orchestrateur vers le canal de chaque agent, et **Message** de l’orchestrateur vers **Fin**. Il est la seule voix du chat de l’exécution, pose des questions et appelle les agents un par un. Les textes des agents et les ordres internes n’apparaissent pas comme bulles. L’app joint le dernier résultat à la tâche suivante ; inutile de le coller dans le chat. Le chat reste ouvert jusqu’à ce qu’il termine l’exécution. Sans orchestrateur, chaque agent reste sa propre chaîne via message et transfert. Un agent est soit sur le canal, soit sur la chaîne, jamais les deux.

Optionnel : **Outil** vers le port **Outil** de l’agent ou de l’orchestrateur, **Connaissances** vers **Connaissances**. Enregistrer. Dans la **Bibliothèque**, « Définir comme actif » si la sélection rapide ne l’est pas encore.

## Démarrer et arrêter

**Démarrer** lance **une** exécution du réseau **actif** (sélection rapide). Jamais un second réseau en parallèle. Un second démarrage est refusé jusqu’à **Arrêter**.

**Arrêter** annule l’exécution (résultat **Annulé**, pas **Erreur**). Ollama reste allumé.

Sans réseau actif, rien ne démarre. Un réseau invalide (erreur de validation, modèle manquant) doit être vérifié dans l’éditeur avant le démarrage.

Pendant que le réseau actif tourne, **ce** document de l’éditeur est en lecture seule. Tu peux continuer à voir d’autres réseaux ; supprimer le réseau en cours dans la bibliothèque est bloqué.

Fermer la fenêtre termine l’exécution et l’app. Ollama continue.

## Le chat d’aide n’est pas le chat du réseau

En bas à droite : bulle = **aide de l’app** (ce guide, termes du graphe, recherche web optionnelle). L’onboarding l’explique à la première ouverture.

Dans **Supervision**, l’onglet **Chat** = **chat de l’exécution** du graphe (nœud Chat). Sans orchestrateur, c’est l’entrée vers les agents. Avec orchestrateur, c’est la conversation : il peut te questionner avant d’appeler un agent.

Ils ne partagent **ni** historique, **ni** outils, **ni** identifiants. L’aide n’utilise **aucun** serveur MCP.

## Ollama et le cloud

- **Local :** Ollama, dans Paramètres comme Runtime. Tu listes et testes les modèles là. L’app **ne** télécharge **pas** de modèles en silence à l’exécution.
- **Cloud :** identifiants sous **Paramètres → Identifiants** (xAI, OpenAI, Claude, Gemini, recherche web, …). Sur le nœud LLM tu choisis Ollama, xAI, OpenAI, Claude ou Gemini. Un cloud sans identifiant adapté est invalide. Les listes n’affichent qu’un **masque**, jamais le secret. Les nœuds LLM et l’aide pointent vers l’identifiant par nom, pas avec la clé dans le graphe.

Une URL de base compatible OpenAI n’est plus proposée dans Runtime. Les identifiants de ce type déjà présents restent sous Identifiants.

## Une instance

Un second lancement ramène la fenêtre existante au premier plan. Pas de second backend ni de seconde exécution.

## Portable et installée

L’app installée place les données dans le dossier local **Agentus-Network**, pas à côté du programme. La variante portable (fichier `portable.txt` à côté de l’EXE) place les données **à côté de l’EXE**. En portable, tu dois apporter WebView2 et Ollama toi-même.
