# Tableau de bord

La page d’accueil. Elle résume la configuration, le réseau actif et les dernières exécutions. Ce n’est **pas** de la supervision en direct ni un archive — il y a des pages dédiées.

## Configuration

La carte **Configuration** apparaît s’il manque quelque chose pour la première exécution, par exemple :

- Ollama injoignable → lien **Vérifier le runtime**
- Profil d’aide sans fournisseur ou modèle → **Configurer l’aide**
- Pas encore de réseau → **Nouveau réseau** ou **Importer un réseau**

Si l’environnement est complet, la carte disparaît. Les modèles optionnels manquants après un setup silencieux sans téléchargement ne sont pas un second assistant : le ping Runtime ou le chat d’aide montrent l’erreur.

## Ressources de l’hôte

La même carte que sous **Supervision** : CPU, mémoire et GPU/VRAM **de ce PC**, pas seulement du processus de l’app. Les valeurs se mettent à jour en continu, même sans exécution active.

## Statut

Indique si le service est **arrêté**, **démarre**, **en cours** ou **s’arrête**, plus le réseau actif. Pendant l’indexation des connaissances, le statut dit **Indexation des connaissances** et le nom du nœud. La même ligne est sur le bouton Démarrer. Réseau en cours : lien **Supervision** et éventuellement « en cours depuis … ». Sans sélection rapide : mention et lien vers la **Bibliothèque**.

Démarrer et arrêter restent dans l’**en-tête**, pas sur cette carte.

## Réseau actif

Nom, nombre de nœuds/arêtes, Valide/Invalide, dernière modification. Actions : **Modifier** (éditeur), **Bibliothèque**, **Nouveau réseau**.

Invalide signifie : la validation de l’éditeur échoue (par exemple modèle manquant sur un nœud LLM). Tu ne devrais pas démarrer ces réseaux.

## Récemment utilisés

Courte liste des réseaux enregistrés par dernière utilisation. Un clic ouvre l’éditeur. Vide : pas encore de réseaux.

## Dernières exécutions

Les dernières entrées de l’historique (succès, erreur, annulé, délai dépassé, ou encore en cours). Une entrée en cours mène à **Supervision**, les terminées à l’**Historique**. Si le store d’historique est en panne, un avis avec lien **Données** apparaît.

## 7 derniers jours

Petite statistique : nombre d’exécutions, réussies, échouées. Lien **Historique** pour filtres et graphiques. C’est un résumé, pas un second archive.

## Environnement

- Ollama joignable ou non, nombre approximatif de modèles
- Problèmes de store (paramètres, aide, espace de travail, historique)
- **Mode économique**, si l’aide est passée au modèle de repli

Liens : **Données**, Runtime.

## Accès rapide

**Nouveau réseau**, **Importer** (bibliothèque), **Runtime**. Les mêmes actions via la navigation et Paramètres.
