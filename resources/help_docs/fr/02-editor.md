# Éditeur et bibliothèque

L’éditeur sous **Réseau** édite **un** document de graphe. La **Bibliothèque** est le catalogue : liste, import, suppression, activation. Le canevas n’existe que dans l’éditeur, pas en Bibliothèque, Supervision ni Historique.

## Deux endroits

| Lieu | Sens de l’URL | Actions typiques |
|-----|----------|-------------------|
| Éditeur | Nouveau ou un réseau chargé | Dessiner, inspecteur, enregistrer, dialogue Ouvrir, dupliquer, exporter le graphe ouvert |
| Bibliothèque | tous les réseaux | Recherche, étiquettes, définir comme actif, import/export de plusieurs fichiers, supprimer |

**Définir comme actif** et **Supprimer** appartiennent à la bibliothèque (ou à la sélection rapide pour actif). Le dialogue Ouvrir de l’éditeur ouvre seulement **un** réseau et ne supprime rien.

## Surface de l’éditeur

En haut le **ruban** : Nouveau, Enregistrer, Enregistrer sous, Ouvrir, Dupliquer, Exporter, Valider, Annuler/Rétablir, Affichage (ajuster, grille, magnétisme, mini-carte), Vers la bibliothèque.

Centre : **Palette** (gauche), **canevas**, **Inspecteur** (droite). Sur le bureau, on peut les replier. Sur écrans étroits, ce sont des tiroirs. Un réseau vide n’affiche que l’indication de glisser le premier nœud de la palette sur le canevas. Les arêtes sont des courbes, comme en supervision et dans l’historique.

Nœuds par glisser depuis la palette. Les cartes restent compactes ; les formulaires sont dans l’inspecteur. Sélection multiple avec Maj ou lasso. Suppr efface la sélection. Annuler : Ctrl+Z.

Pendant que **précisément ce** réseau tourne : bannière **Lecture seule** — d’abord arrêter dans l’en-tête.

## Types de nœuds

| Nom | Type | Rôle |
|-------------|-----|---------|
| Chat | `chat_input` | Conversation de l’exécution. **Au plus un.** Sortie **Message**. Avec orchestrateur, le chat reste ouvert pour les questions. |
| Orchestrateur | `orchestrator` | Voix du chat de l’exécution. Entrées **Message**, **LLM** et **Outil**. Une sortie **Canal** par agent. **Message** seulement vers **Fin** (ou un routeur). **Au plus un.** |
| LLM | `llm` | Fournisseur (Ollama, xAI, OpenAI, Claude, Gemini), modèle, identifiant cloud, température, limite de jetons. Sortie **LLM**. |
| Agent | `agent` | Invite système. Entrées Message, LLM, Outil, Connaissances, **Canal** optionnel. Sorties Message et transfert. Le canal vient seulement de l’orchestrateur. Sans canal, l’agent s’exécute une fois via le message. |
| Outil | `tool` | First-party : HTTP, recherche web, date/heure, calculatrice, accès aux fichiers — ou **MCP**. Sortie **Outil**. |
| Connaissances | `knowledge` | Dossier de fichiers pour le réseau. Sortie **Connaissances**, uniquement vers le port Connaissances de l’agent. |
| Routeur | `router` | Branche le message selon des conditions (première ligne / branches nommées) plus sortie par défaut. |
| Fin | `end` | Clôture. **Au moins une.** |

## Connexions

Uniquement des ports compatibles :

- Message vers Message (Chat → Agent ou Chat → Orchestrateur, Agent → Fin, Agent → Routeur, branches du routeur → …). L’orchestrateur n’envoie Message qu’à Fin ou à un routeur.
- Canal vers Canal (Orchestrateur → Agent). Un port par agent. La réponse revient dans l’exécution, sans seconde arête.
- Sortie LLM vers **LLM** de l’agent ou de l’orchestrateur — chaque agent et l’orchestrateur ont besoin d’**exactement une** telle arête
- Sortie d’outil vers **Outil** de l’agent ou de l’orchestrateur (plusieurs autorisées). Un outil peut aller aux deux.
- Sortie de connaissances uniquement vers **Connaissances** de l’agent
- Les cycles sont interdits (graphe orienté sans boucle)

Un glisser invalide est refusé.

## Inspecteur

Aucun nœud choisi : nom, description, étiquettes, statistiques, liste de validation du réseau **ouvert**.

Nœud choisi :

- **LLM :** fournisseur, modèle (liste du runtime), identifiant cloud, ping, avancé température / jetons max. Cloud sans identifiant est invalide.
- **Agent :** invite système et nom affiché. Si l’agent est sur un canal, l’inspecteur explique que les tâches viennent de l’orchestrateur.
- **Outil :** type. HTTP : méthode et URL, identifiant optionnel. Recherche web : identifiant de type recherche web. Accès aux fichiers : dossier racine, pas la racine d’un lecteur ; l’agent ne travaille qu’en dessous, et écrire et supprimer sont des interrupteurs. MCP : serveur activé dans Paramètres ; par défaut tous les outils de ce serveur.
- **Connaissances :** dossier source (choix de dossier), fournisseur d’embeddings (Ollama, OpenAI ou Gemini) et modèle d’embeddings, topK, seuil de score, **Reconstruire l’index**. Le dossier peut être n’importe où, sauf une racine de lecteur ou de système et le corpus d’aide. Les embeddings cloud exigent un identifiant. L’index appartient à ce réseau, pas à l’aide.
- **Chat :** espace réservé, texte de départ, interrupteur « Saisie obligatoire ».
- **Orchestrateur :** invite système. Le modèle choisit une question, une tâche vers un agent par son canal, une réponse ou la fin. Les agents sont les canaux, pas une seconde liste. Il appelle lui-même les outils branchés. Seule une question attend l’utilisateur.
- **Routeur :** branches nommées (nom + condition) et défaut.

Les secrets n’appartiennent **pas** au texte de l’inspecteur ni à l’export du graphe — seulement le choix d’un identifiant.

## Validation

**Valider** dans le ruban vérifie notamment :

- Nom non vide
- au plus un chat, au plus un orchestrateur, au moins une fin
- chaque agent : exactement une arête LLM. Sans orchestrateur, un message entrant. Avec orchestrateur, exactement un canal et pas de chaîne de messages sur le même agent
- LLM : modèle défini ; cloud : identifiant
- Outil : type ; MCP : serveur actif, chemin racine si la recette l’exige ; accès aux fichiers : un dossier qui n’est pas une racine de lecteur
- Connaissances : chemin défini, pas une racine, pas le corpus d’aide, identifiant d’embeddings si le fournisseur l’exige
- pas d’arêtes pendantes, pas de cycles, types de ports compatibles

Valide/Invalide se voit comme badge. Les réseaux invalides se sauvegardent, mais démarrent mal.

## Enregistrer, ouvrir, exporter

- **Enregistrer** (Ctrl+S) : première fois dialogue de nom, ensuite mise à jour. L’URL devient `/network/…`.
- **Enregistrer sous :** nouveau document, devient l’ouvert.
- **Ouvrir :** un réseau enregistré ; recherche et tri. Actions groupées et suppression seulement dans la bibliothèque.
- **Dupliquer :** seulement si le document est déjà enregistré ; ouvre la copie.
- **Exporter :** téléchargement du graphe ouvert. Contient `credentialId`, pas de clés. L’import dans la bibliothèque jette les secrets joints.

Quitter sans enregistrer : dialogue Enregistrer / Abandonner / Annuler.

## Bibliothèque

Liste avec recherche (nom, description, étiquettes), tri, filtres « valides seulement » / « actifs seulement ». Sélection multiple.

Actions : Nouveau (éditeur), Ouvrir, Dupliquer, Renommer, Ajouter des étiquettes, **Définir comme actif** (un seul réseau valide), Supprimer, Importer, Exporter.

Supprimer retire l’entrée de l’espace de travail, pas tes fichiers source de connaissances sur le disque, ni le corpus d’aide, ni les exécutions d’historique. Un réseau **en cours** est ignoré. Supprimer le réseau actif vide la sélection rapide.

Import : fichiers en collision de nom à renommer ou ignorer. Les versions de schéma non prises en charge sont refusées.
