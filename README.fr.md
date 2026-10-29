# Media Hub 1.4.0 — extension QGIS

**Media Hub** est une extension pour **QGIS 3.44.x (Qt5) sur Windows 64 bits**, développée par [JulienH77](https://github.com/JulienH77), sous licence MIT.

## Fonctionnalités

- **Vidéo :** lecture de fichiers locaux ou de liens directs, dossier vidéo mémorisé, liste déroulante et actualisation, pause, ±10 secondes, vitesse réglable de 0,1× à 5×, audio et sous-titres multiples avec VLC, sous-titres externes.
- **PiP :** petite fenêtre flottante, boutons de lecture centrés, volume et vitesse, plein écran et retour à QGIS.
- **Radio :** 15 stations intégrées en carrés compacts (RTL, France Inter, FIP, RMC, Franceinfo, Europe 1, NRJ, Nostalgie, Chérie FM, RTL2, France Culture, France Musique, RFM, Skyrock, Fun Radio), et possibilité d'ajouter ses propres stations.
- **Web :** navigateur Qt WebEngine facultatif, raccourci YouTube ; repli vers le navigateur Windows si WebEngine manque.
- **Notes :** bloc-notes enregistré automatiquement dans les paramètres locaux de QGIS.
- **Paramètres (⚙) :** modifier les raccourcis vidéo (ou les rétablir), activer/désactiver ces raccourcis, afficher le panneau au démarrage, régler l'utilisation du proxy radio et le volume.

## Raccourcis par défaut

| Touche | Action |
| --- | --- |
| Espace | Lecture / Pause |
| ← / → | Retour / avance de 10 secondes |
| ↑ / ↓ | Augmenter / réduire le volume de 5 % |
| S | Vitesse 1,0× |
| Q / D | Ralentir / accélérer de 0,1× |
| Échap | Quitter le plein écran du PiP |

Ces raccourcis sont destinés à l'onglet Vidéo et au PiP, pas à l'ensemble des fenêtres QGIS.

## Installation

**Extensions → Installer/Gérer les extensions → Installer depuis un ZIP** : utiliser l'archive qui contient le dossier `media_hub/`. Installer **VLC 64 bits** pour lire la vidéo et les radios. Le navigateur intégré nécessite PyQtWebEngine (Qt5) dans l'environnement QGIS ; son absence ne bloque pas l'extension.

## Limites

Les flux radio dépendent de leurs serveurs, des redirections et des règles du réseau. Le flux Franceinfo de l'utilisateur est intégré avec des flux de secours, mais la disponibilité n'est pas garantie. Les images des stations sont des vignettes textuelles créées pour l'extension, pas des logos officiels. La compatibilité QGIS 4 / Qt6 n'a pas été validée.

Toutes les données de préférences sont conservées en local. Aucun suivi d'utilisation.

Historique détaillé : [CHANGELOG.md](CHANGELOG.md). Source : https://github.com/JulienH77/qgis-media-hub
