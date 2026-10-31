# Media Hub 1.5.1 — extension QGIS

**Media Hub** est une extension pour **QGIS 3.44.x (Qt5) sur Windows 64 bits**, développée par [JulienH77](https://github.com/JulienH77), sous licence MIT.

## Fonctionnalités

- **Vidéo :** lecture de fichiers locaux ou de liens directs, dossier vidéo mémorisé, liste déroulante et actualisation, pause, ±10 secondes, vitesse réglable de 0,1× à 5×, audio et sous-titres multiples avec VLC, sous-titres externes.
- **PiP :** petite fenêtre flottante, boutons de lecture centrés, barre de commandes sur seulement deux lignes avec volume compact et vitesse, plein écran et retour à QGIS. Nouveau mode sombre et commandes masquables par un petit bouton permanent (également en plein écran) ou avec H.
- **Radio :** une seule entrée **France**, avec cinq radios (RTL, Franceinfo, France Inter, FIP, RMC). Les autres pays proposent jusqu'à cinq stations depuis Radio Browser, mises en cache. Les radios ajoutées manuellement sont rattachées au pays choisi et n'apparaissent plus partout ; les anciennes stations sans pays restent conservées dans « Mes radios sans pays ». Il est possible de changer le pays d'une radio personnelle.
- **Web :** navigateur Qt WebEngine facultatif, raccourci YouTube ; repli vers le navigateur Windows si WebEngine manque.
- **Notes :** bloc-notes enregistré automatiquement dans les paramètres locaux de QGIS.
- **Paramètres (⚙) :** modifier les raccourcis vidéo (ou les rétablir), activer/désactiver ces raccourcis, afficher le panneau au démarrage, régler l'utilisation du proxy radio et le volume, et choisir la langue **Automatique / Français / English** (anglais par défaut hors locale française).

## Raccourcis par défaut

| Touche | Action |
| --- | --- |
| Espace | Lecture / Pause |
| ← / → | Retour / avance de 10 secondes |
| ↑ / ↓ | Augmenter / réduire le volume de 5 % |
| S | Vitesse 1,0× |
| Q / D | Ralentir / accélérer de 0,1× |
| H | Masquer/afficher les commandes du PiP et du plein écran |
| Échap | Quitter le plein écran du PiP |

Ces raccourcis sont destinés à l'onglet Vidéo et au PiP, pas à l'ensemble des fenêtres QGIS.

## Installation

**Extensions → Installer/Gérer les extensions → Installer depuis un ZIP** : utiliser l'archive qui contient le dossier `media_hub/`. Installer **VLC 64 bits** pour lire la vidéo et les radios. Le navigateur intégré nécessite PyQtWebEngine (Qt5) dans l'environnement QGIS ; son absence ne bloque pas l'extension.

## Limites

Les flux radio dépendent de leurs serveurs, des redirections et des règles du réseau. Le flux Franceinfo de l'utilisateur est intégré avec des flux de secours, mais la disponibilité n'est pas garantie. Les images des stations sont des vignettes textuelles créées pour l'extension, pas des logos officiels. La compatibilité QGIS 4 / Qt6 n'a pas été validée.

Les préférences et les listes de radios précédemment récupérées sont conservées localement. Choisir un pays international lance une requête vers l’annuaire public Radio Browser via le réseau de QGIS. Les clics de cet annuaire ne constituent pas un classement national d’audience. Aucun suivi d’utilisation par l’extension.

Historique détaillé : [CHANGELOG.md](CHANGELOG.md). Source : https://github.com/JulienH77/qgis-media-hub

### Ajustements de l’interface (Media Hub 1.5.1)
La fenêtre vidéo flottante et le plein écran possèdent une barre de progression synchronisée, avec les temps écoulé et total. Le volume compact permet de couper le son ou d’amplifier VLC jusqu’à 200 %, et le champ de vitesse est identique à celui du panneau QGIS : saisie directe de 0,1× à 5,0×, par pas de 0,1. Les commandes restent repliables avec le bouton Afficher/Masquer ou le raccourci H.

Les radios ont des carrés réduits et leurs noms sous les images ; les stations sans logo affichent des initiales. L’onglet Web est modernisé, avec un accès direct à YouTube et un repli vers le navigateur système si Qt WebEngine est indisponible.


## ZIP d'installation et téléchargement GitHub

Utilisez le **ZIP d'installation QGIS**, qui doit contenir le dossier
`media_hub/` à sa racine, avec `__init__.py` et `metadata.txt`.

Le bouton **Code → Download ZIP** de GitHub ne convient pas directement :
GitHub crée un dossier comme `qgis-media-hub-main` ou
`qgis-media-hub-1.5.1`, que Python ne peut pas importer dans QGIS.

Pour installer les sources manuellement, copiez les fichiers dans un dossier
`media_hub` situé dans le répertoire `python/plugins` de votre profil QGIS,
puis redémarrez QGIS.
