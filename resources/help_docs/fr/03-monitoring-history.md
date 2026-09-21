# Supervision et historique

**Supervision** = maintenant, une exécution. **Historique** = archive et statistiques. L’historique n’est **pas** un second tableau de bord ni un journal en direct. Démarrer et arrêter restent dans l’**en-tête**.

## Direct contre archive

| | Supervision | Historique |
|---|------------|----------|
| Quand | le service démarre, tourne ou s’arrête | après la fin de l’exécution (et lien tant qu’elle tourne encore) |
| Graphe | mini-graphe, lecture seule, état des nœuds | instantané enregistré, pas de mise à jour en direct |
| Journal | flux, plus récent en haut, pause possible | lignes figées, filtrables |
| Chat | chat de l’exécution, seulement pendant l’exécution | transcription enregistrée, pas de suite |

Une entrée d’historique encore en cours n’est qu’un saut vers Supervision (« Voir en direct »).

## Supervision sans exécution

Sans exécution active, la page montre la **dernière exécution enregistrée** en lecture (graphe, activité, journal, chat). Une mention dit que rien n’est en direct. La page n’est tout à fait vide que s’il n’y a encore aucune exécution : **Aucune exécution**, plus le réseau actif ou l’avis que la sélection rapide est vide. Déconnecté / erreur / démarre / s’arrête ont leurs textes. Pendant l’indexation, l’avis de démarrage passe au nom du nœud de connaissances. Les dernières valeurs peuvent rester grisées jusqu’à la connexion.

## Pendant une exécution

En-tête : ID d’exécution, heure de début, durée, étape approximative, LLM actifs (local vs cloud).

**Réseau (lecture seule) :** le même graphe, couleurs de nœuds selon l’état (inactif, en attente, en cours, terminé, erreur). Un clic sur un nœud filtre journal/activité et ouvre le détail (rôle, statut, attente LLM/outil/saisie/index, dernier message, jetons). Pas d’édition, pas de second éditeur.

Si des connaissances sont reliées à un agent, le démarrage montre déjà l’exécution pendant l’indexation : le nœud tourne avec le motif d’attente **index**, le journal nomme la lecture et les embeddings, et l’en-tête comme le tableau de bord montrent le même nom. Un index déjà à jour est sauté et seulement noté comme actuel.

**Activité :** nœuds actuels, progression « étape x sur y », jetons entrée/sortie, fenêtre de contexte optionnelle.

**Ressources de l’hôte :** CPU, RAM, GPU/VRAM **de ce PC**, pas seulement de l’app. Sans GPU local (typique des exécutions cloud) : un avis, pas une erreur.

## Chat réseau (supervision)

Onglet **Chat** : conversation du graphe en cours. Actif seulement pendant l’exécution. Sans orchestrateur, le chat attend la première ligne et la passe à la chaîne. Avec orchestrateur, tu ne parles qu’à lui. Les questions restent ouvertes dans la même exécution. Les textes des agents et les ordres internes n’apparaissent pas ici.

Ce n’est **pas** la bulle d’aide. Historique et outils sont ceux du réseau.

## Journal (supervision)

Onglet **Journal** : lignes avec niveau (debug, info, avertissement, erreur), nœud, heure. Plus récent en haut. Pause arrête le suivi ; « Aller aux plus récents » saute de nouveau à la fin. Filtres : recherche, niveau à partir de, un nœud, erreurs seulement. Export des lignes visibles.

Les charges utiles et messages **masquent** les secrets (par exemple `Bearer`, préfixes de clé). Ne les transmets pas non filtrés.

## Historique

Ruban : Actualiser, supprimer les exécutions sélectionnées, exporter les journaux, purger les anciennes selon la conservation (voir Paramètres → Données, défaut 90 jours).

**Un filtre** pilote tout : période (aujourd’hui, 7/30 jours, de–à), réseau, modèle, recherche (ID d’exécution, réseau, erreur). KPI, graphique « exécutions par jour », erreurs fréquentes, onglets Historique / Par modèle / Par réseau et la liste utilisent le même filtre.

## Résultats d’une exécution

| Résultat | Signification |
|----------|-----------|
| En cours | encore active — dans l’historique seulement comme lien |
| Succès | terminée normalement |
| Erreur | une étape ou le service a échoué |
| Annulé | Arrêter dans l’en-tête, fenêtre fermée, ou fin de l’app (aussi après un crash, au prochain démarrage) |
| Délai dépassé | dépassement de temps |

**Annulé n’est pas une erreur.** Délais et annulations sont comptés à part dans les KPI (pied de « Erreur »).

## Détail de l’exécution

Côté droit ou vue dédiée : méta, mini-graphe, onglets **Journal**, **Étapes**, **Chat**. Étapes : nœud, rôle, statut, erreur. Chat : transcription, lecture seule. Exporter un journal isolé.

Supprimer des entrées d’historique ne change pas les réseaux enregistrés.
