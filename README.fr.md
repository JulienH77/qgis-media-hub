# Media Hub — extension QGIS 3.44

**Auteur : JulienH77** · **Version : 1.3.2 (expérimentale)** · **Licence : MIT**.

Une extension à l'interface claire qui rassemble quatre onglets dans un panneau QGIS :

- **Vidéo :** lecture MP4 et autres formats pris en charge par VLC, ±10 secondes, pause, vitesse 0,1× à 5×, PiP et plein écran, volume VLC jusqu'à 200 %.
- **Web :** mini-navigateur Qt WebEngine basé sur Chromium, raccourci YouTube et favoris. Le navigateur peut ne pas fonctionner sur toutes les installations.
- **Radio :** RTL, France Inter, FIP, RMC, stations personnalisées, gestion des redirections et relais réseau QGIS pour certains proxys. Fonctionnement non garanti selon le réseau.
- **Notes :** bloc-notes avec sauvegarde automatique.

## Installation

QGIS 3.44.x (Qt 5) sous Windows 64 bits : Extensions → Installer/Gérer les extensions → Installer depuis un ZIP. Installer séparément VLC 64 bits, recommandé pour la vidéo et la radio. L'onglet Web nécessite Qt WebEngine (sur OSGeo4W, paquet `python3-pyqtwebengine`).

Dans QGIS, utiliser **Extensions → Media Hub** ou la barre d'outils Media Hub. Cocher « Au démarrage » dans le panneau pour le rouvrir à chaque lancement.

## Limites

La version 1.3 avait un problème de radio identifié sur un réseau professionnel ; le correctif de redirection n'a pas encore été confirmé opérationnel dans cette situation. La version 1.3.2 concerne la **publication et la reconnaissance de l'auteur**, pas le moteur radio. Il faut la tester réellement sur QGIS avant de cocher la case correspondante sur le site officiel.

Page du projet (après création du dépôt public) : https://github.com/JulienH77/qgis-media-hub

L'extension n'enregistre pas de télémétrie. Préférences, favoris et notes restent locaux. Les marques QGIS, VLC et YouTube appartiennent à leurs propriétaires respectifs.
