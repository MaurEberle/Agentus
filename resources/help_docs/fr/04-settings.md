# Paramètres

Engrenage dans l’en-tête. Sections à gauche : Apparence, Identifiants, Runtime, Chat d’aide, Serveurs MCP, Données, À propos. Champs non enregistrés au changement : dialogue Rester / Abandonner.

## Apparence

Clair, sombre ou système — pour toute l’app, y compris l’en-tête. **Langue** est une liste déroulante avec drapeau : Deutsch, English, Español, Français, Türkçe, Português, 中文, 日本語, العربية. Le nom entre parenthèses est la traduction dans la langue d’interface actuelle.

Interrupteur **Bouton d’aide** : affiche ou masque la bulle en bas à droite. La **configuration** du chatbot reste sous **Chat d’aide**, même si la bulle est masquée.

## Identifiants

Secrets nommés pour modèles cloud, recherche web et certaines recettes MCP. Créer : nom, type, secret **une fois**. Ensuite seulement le **masque**. Modifier peut remplacer le secret (vide = inchangé).

Types notamment : xAI, OpenAI, Claude, Gemini, compatible OpenAI, recherche web, GitHub, Azure, GitLab, Slack, Notion, Atlassian, Linear, Postgres, jeton.

**Supprimer** est bloqué tant que le profil d’aide, un réseau (LLM/outil) ou un serveur MCP utilise l’identifiant. D’abord retirer l’affectation.

## Runtime

**URL de base Ollama** (souvent l’adresse locale d’Ollama). **Vérifier la connexion** et la **liste des modèles** passent par l’app. La liste se partage en **Modèles normaux** et **Modèles d’embeddings**. Un modèle compte comme embedding si le nom contient `embed`. Un groupe vide affiche **Aucun**.

Si l’adresse est locale et qu’Ollama est installé mais arrêté, l’app démarre le service à l’ouverture et ne l’arrête pas. Sans Ollama joignable, les nœuds LLM locaux et l’aide par défaut restent bloqués. Tu installes les modèles avec Ollama ou au setup ; l’app **ne** pull **pas** en silence à l’exécution. Une URL de base compatible OpenAI n’est plus proposée ici.

## Chat d’aide

Seul endroit pour le widget d’aide. Incomplet sans fournisseur et modèle de chat.

- Fournisseur et modèle de chat (défaut Ollama / `llama3.2:1b`)
- identifiant cloud optionnel
- **Fournisseur et modèle d’embeddings** (défaut Ollama / `nomic-embed-text`) — ce n’est **pas** le modèle de chat
- modèle économique optionnel (repli, défaut le même petit chat)
- recherche web on/off plus identifiant de recherche ; sans identifiant le chat reste configuré, la recherche est off
- vérifier la connexion, effacer l’historique, **reconstruire l’index**, réafficher l’onboarding

Après changement du modèle d’embeddings ou de nouveaux fichiers dans le corpus d’aide : **reconstruire l’index**. Le travail continue si tu quittes Paramètres. Un second clic n’en lance pas un autre. Le corpus est le dossier des documents d’aide dans le dossier de données, pas le savoir du réseau. Les nouveaux guides livrés n’écrasent pas les fichiers déjà présents.

L’aide répond dans la langue de l’interface. Si le modèle ne peut pas l’utiliser, il répond en anglais. Elle ne cite pas les titres des guides. Seule une recherche web montre des sources, titre et adresse. Les blocs de réflexion internes du modèle restent cachés. L’aide n’utilise **aucun** serveur MCP ni le knowledge des graphes.

## Serveurs MCP

Modèles (**recettes**) pour outils externes : GitHub, système de fichiers, Git, Playwright, Postgres, Slack, Notion, formats Office et autres. Les recettes ne sont pas des programmes livrés. Beaucoup ont besoin de Node/`npx`, Docker ou `uvx` sur le PC plus un identifiant.

Défaut : serveur **inactif**. L’app ne démarre pas les processus MCP à l’ouverture, mais quand une exécution a besoin d’un nœud d’outil MCP connecté.

Créer depuis une recette (identifiant, chemin racine optionnel) ou comme **serveur personnalisé** (commande, arguments ou URL). N’utilise des commandes inconnues que si tu leur fais confiance. La sonde vérifie la joignabilité ; « Runtime manquant » si Node/Docker/`uvx` n’est pas là.

Office regroupe PDF et formats Office ; n’active les presets individuels que si tu en as vraiment besoin.

Supprimer retire la configuration du serveur, pas Ollama ni les identifiants.

## Données

Affiche le **dossier de données** et l’état des stores : Paramètres, Aide, Espace de travail, Historique — sans vue SQL et sans secrets.

**Changer** de dossier seulement si aucun réseau ne démarre, ne tourne ou ne s’arrête. Racines de lecteur ou système interdites. Optionnel copier le contenu vers le nouveau dossier ; l’ancien reste.

**Portable** ou un dossier imposé de l’extérieur : chemin **en lecture seule**.

**Conservation de l’historique :** 30 / 90 / 365 jours ou illimité (défaut 90). La page Historique peut purger les anciennes entrées en conséquence.

## À propos

Versions UI et API, statut Ollama approximatif, stores joignables. Pas de secrets, pas de chemins internes avec nom d’utilisateur sur une surface que tu partagerais.
