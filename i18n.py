# -*- coding: utf-8 -*-
"""French/English UI strings for Media Hub. French is the source language.

Language follows QGIS' locale by default and can be overridden in Preferences.
Do not translate URLs, file paths, station names or stored user notes.
"""
from qgis.PyQt.QtCore import QLocale, QSettings

PREFIX = "qgis_media_hub/"
EN = {
    "Media Hub — Vidéo flottante": "Media Hub — Floating video",
    "↩ QGIS": "↩ QGIS", "Replacer la vidéo dans QGIS": "Return video to QGIS",
    "Reculer de 10 secondes": "Back 10 seconds", "Avancer de 10 secondes": "Forward 10 seconds",
    "Lecture / Pause (Espace)": "Play / Pause (Space)",
    "Lecture / Pause": "Play / Pause", "Pause": "Pause", "Lecture": "Play",
    "Plein écran / retour": "Toggle fullscreen",
    "Plein écran": "Fullscreen", "Plein écran vidéo ; Échap pour quitter": "Fullscreen video; Esc to exit",
    "Son": "Sound", "Vitesse": "Speed", "Volume": "Volume",
    "Volume 0–200 % (moteur VLC)": "Volume 0–200% (VLC engine)",
    "☾ Sombre": "☾ Dark", "☀ Clair": "☀ Light",
    "Basculer entre le thème clair et le thème sombre": "Switch between light and dark theme",
    "⌄ Masquer": "⌄ Hide", "⌃ Afficher": "⌃ Show",
    "Masquer/afficher les commandes (H)": "Hide/show controls (H)",
    "Afficher les commandes (H)": "Show controls (H)",
    "Masquer les commandes (H)": "Hide controls (H)",
    "par JulienH77": "by JulienH77", "licence MIT": "MIT license",
    "Mode sombre : thème sombre / clair de Media Hub": "Dark mode: switch Media Hub light/dark theme",
    "Paramètres et diagnostics": "Settings and diagnostics",
    "Initialisation des lecteurs…": "Initializing players…",
    "Au démarrage": "On startup",
    "Afficher automatiquement ce panneau au lancement de QGIS": "Show this panel when QGIS starts",
    "Revenir au thème clair": "Switch to light theme",
    "Activer le mode sombre": "Enable dark mode",
    "Mes vidéos": "My videos",
    "Fichiers MP4, MKV, AVI… ou liens directs vers un média.": "MP4, MKV, AVI files… or direct media URLs.",
    "Choisir le dossier contenant tes vidéos": "Choose a folder containing videos",
    "Dossier…": "Folder…", "Sélectionne un dossier pour afficher ses vidéos": "Choose a folder to list its videos",
    "Actualiser les vidéos du dossier": "Refresh folder videos",
    "Aucun dossier vidéo sélectionné": "No video folder selected",
    "Ouvrir…": "Open…", "Chemin ou URL directe…": "File path or direct URL…",
    "Lire": "Play", "Ouvre une vidéo pour commencer.": "Open a video to get started.",
    "Aucun média": "No media", "Nom de la vidéo": "Video title",
    "▶ Lecture": "▶ Play", "⏸ Pause": "⏸ Pause", "▶ Reprendre": "▶ Resume",
    "▶ Écouter": "▶ Listen", "▶ Réessayer": "▶ Retry",
    "Audio": "Audio", "Sous-titres": "Subtitles",
    "Choisir une piste audio incluse dans le fichier": "Select an embedded audio track",
    "Activer ou désactiver une piste de sous-titres": "Enable or disable subtitle track",
    "Charger des sous-titres externes .srt, .ass ou .vtt": "Load external .srt, .ass or .vtt subtitles",
    "Raccourcis (vidéo et PiP) : Espace lecture/pause · ←/→ ±10 s · ↑/↓ son · S vitesse 1× · Q/D ±0,1×":
        "Video shortcuts: Space play/pause · ←/→ ±10s · ↑/↓ volume · S speed 1× · Q/D ±0.1×",
    "Mini-lecteur flottant toujours au premier plan": "Floating player, always on top",
    "Muet": "Mute", "Activer son": "Unmute",
    "Volume VLC de 0 à 200 %. Au-delà de 100 %, risque de saturation.":
        "VLC volume from 0 to 200%; amplification above 100% may distort sound.",
    "Vidéo": "Video", "Média : indisponible": "Media: unavailable",
    "Dossier précédent introuvable · choisis-en un autre": "Previous folder not found · choose another",
    "Dossier inaccessible · choisis-en un autre": "Folder inaccessible · choose another",
    "Lecture du dossier impossible": "Cannot read folder",
    "Vidéo en ligne": "Online video",
    "La radio est en cours de lecture.\nReviens aux vidéos pour lire un fichier.":
        "Radio is playing.\nReturn to Videos to play a file.",
    "Vidéo dans la mini-fenêtre. Clique sur « QGIS » pour la récupérer.":
        "Video is in the floating window. Click QGIS to return it here.",
    "Navigateur": "Browser",
    "Rechercher ou saisir une adresse…": "Search or enter a website…",
    "Ouvrir l'adresse": "Open address",
    "Ouvrir le favori": "Open bookmark",
    "Ouvrir dans mon navigateur ↗": "Open in my browser ↗",
    "Choisis un raccourci ou saisis une adresse pour commencer.":
        "Choose a shortcut or enter a website to get started.",
    "Navigateur intégré si Qt WebEngine est disponible.":
        "Embedded browser when Qt WebEngine is available.",
    "Position de lecture (déplacer pour avancer ou reculer)":
        "Playback position (drag to seek)",
    "Vitesse de lecture": "Playback speed",
    "Vitesse de lecture, modifiable par pas de 0,1":
        "Playback speed, adjustable by 0.1 steps",
    "Couper ou rétablir le son": "Mute or unmute",
    "⌕ Recherche": "⌕ Search",
    "Page précédente": "Previous page", "Page suivante": "Next page",
    "Actualiser": "Refresh", "Adresse Internet ou recherche…": "Website address or search…",
    "Aller": "Go", "Recherche": "Search", "Favoris": "Bookmarks",
    "Ouvrir cette page dans le navigateur normal": "Open this page in your default browser",
    "Enregistrer l'adresse actuelle": "Bookmark current address",
    "Supprimer ce favori": "Remove bookmark",
    "Le navigateur Chromium s'initialisera à l'ouverture de cet onglet.":
        "Chromium will initialize when you open this tab.",
    "Fonctionne même si Chromium n'est pas disponible dans QGIS":
        "Works even if Chromium is unavailable in QGIS",
    "Ouvrir le site dans mon navigateur ↗": "Open in my browser ↗",
    "Qt WebEngine : un navigateur intégré ne sera pas forcément aussi rapide que Firefox.":
        "Qt WebEngine: embedded browsing may be slower than Firefox.",
    "Web": "Web", "Media Hub — Navigateur plein écran": "Media Hub — Fullscreen browser",
    "Quitter le plein écran (Échap)": "Exit fullscreen (Esc)",
    "Chromium intégré (Qt WebEngine). Certaines vidéos et connexions protégées peuvent échouer.":
        "Embedded Chromium (Qt WebEngine). Protected videos and logins may not work.",
    "Favori enregistré.": "Bookmark saved.", "Favori supprimé.": "Bookmark removed.",
    "Impossible d'enregistrer cette adresse en favori.": "Could not bookmark this address.",
    "Écouter la radio": "Listen to radio",
    "Écouter": "Listen",
    "Flux directs, sans charger tout le site web.": "Direct streams, without loading the entire website.",
    "Choisis un pays puis clique sur une station.": "Choose a country, then click a station.",
    "Pays": "Country", "Actualiser les cinq radios de ce pays": "Refresh five stations for this country",
    "France : cinq stations populaires.": "France: five popular stations.",
    "France : cinq radios populaires, dont RTL et Franceinfo.":
        "France: five popular radio stations including RTL and Franceinfo.",
    "Radios non classées : attribue-leur un pays lors de l'ajout.":
        "Uncategorized stations: choose a country when adding new ones.",
    "Cinq stations populaires sur Radio Browser (classement non officiel).":
        "Five popular stations from Radio Browser (unofficial ranking).",
    "Annuaire en ligne nécessaire pour ce pays.": "Online directory required for this country.",
    "Connexion via QGIS (proxy du réseau)": "Connect through QGIS (network proxy)",
    "Fait passer l'audio Internet par les paramètres réseau et proxy de QGIS, puis transmet le flux à VLC en local. Utile sur un PC professionnel.":
        "Uses QGIS network/proxy settings to forward audio locally to VLC. Useful on corporate networks.",
    "■ Arrêter": "■ Stop", "Autre flux": "Other stream", "Essayer un serveur alternatif": "Try alternative server",
    "Dans VLC ↗": "Open in VLC ↗", "Ouvrir ce flux avec l'application VLC, hors de QGIS":
        "Open this stream in VLC outside QGIS",
    "Site radio ↗": "Radio website ↗", "Écouter la station sur son site officiel dans Firefox/Chrome":
        "Listen on the official radio website in Firefox/Chrome",
    "Volume de la radio, avec amplification à 200 % si moteur VLC":
        "Radio volume, up to 200% with VLC",
    "Ajouter une station personnelle": "Add a custom station",
    "Nom (par exemple RTL)": "Name (e.g. RTL)",
    "https://…/stream.mp3 ou .m3u8": "https://…/stream.mp3 or .m3u8",
    "Pays de cette station": "Station country",
    "+ Ajouter": "+ Add", "Supprimer la station": "Remove station",
    "Changer de pays": "Change country",
    "Choisis une radio personnelle à déplacer.": "Select a custom radio station to move.",
    "Station déplacée vers le pays choisi.": "Station moved to the selected country.",
    "Choisis une station puis clique sur Écouter.": "Choose a station, then click Listen.",
    "Moteur non initialisé": "Engine not initialized",
    "Jouer un court son local pour verifier la sortie audio": "Play a short local sound to test audio",
    "Tester le son": "Test sound", "Copier le flux": "Copy stream URL",
    "Sur un réseau de bureau, coche Connexion via QGIS pour utiliser le proxy de QGIS. Si le son ne fonctionne pas, ouvre le site officiel dans Firefox.":
        "On a corporate network, enable Connect through QGIS to use its proxy. If audio fails, open the official website in Firefox.",
    "Recherche des cinq radios les plus consultées…": "Looking up five popular stations…",
    "Liste précédemment enregistrée (actualisation impossible).":
        "Showing previously saved stations (refresh failed).",
    "Annuaire inaccessible. Réessaie sur un autre réseau ou ajoute tes propres stations.":
        "Directory unavailable. Try another network or add your own stations.",
    "Connexion…": "Connecting…",
    "Langue de l'interface": "Interface language",
    "Automatique (QGIS / système)": "Automatic (QGIS / system)",
    "Ces touches sont actives uniquement dans l'onglet Vidéo ou le PiP. Clique dans le champ d'un raccourci, puis presse la nouvelle touche.":
        "These keys only work in the Video tab or floating PiP. Click a shortcut field and press your desired key.",
    "France : cinq stations intégrées dont RTL et Franceinfo. Autres pays : cinq stations de Radio Browser. Radios personnelles classées par pays.":
        "France: five built-in stations including RTL and Franceinfo. Other countries: five Radio Browser stations. Custom stations are grouped by country.",
    "Mode navigateur externe (plus rapide pour YouTube). Impossible d'embarquer Chromium sans PyQtWebEngine.":
        "External browser mode (faster for YouTube). Cannot embed Chromium without PyQtWebEngine.",
    "Moteur non initialisé": "Player not initialized",
    "Media Hub — Vidéo, Web, Radio (JulienH77)": "Media Hub — Video, Web, Radio (JulienH77)",
    "Media Hub — par JulienH77 · QGIS 3.44": "Media Hub — by JulienH77 · QGIS 3.44",
    "Impossible d'ouvrir le panneau :\n\n{}": "Could not open the panel:\n\n{}",
    "Raccourci invalide pour « {} ». Définis une combinaison unique, hors Échap et Tab.":
        "Invalid shortcut for '{}'. Choose a unique key combination, excluding Esc and Tab.",
    "Vitesse ×1,0": "Speed ×1.0",
    "Lecture / pause": "Play / pause",
    "Reculer de 10 secondes": "Go back 10 seconds",
    "Avancer de 10 secondes": "Go forward 10 seconds",
    "Augmenter le volume": "Increase volume",
    "Diminuer le volume": "Decrease volume",
    "Ralentir de ×0,1": "Decrease speed by ×0.1",
    "Accélérer de ×0,1": "Increase speed by ×0.1",
    "Afficher/masquer les commandes du PiP": "Show/hide PiP controls",
    "Media Hub — Erreur": "Media Hub — Error",
    "Lecteur indisponible. Installe VLC 64 bits puis relance QGIS.": "Player unavailable. Install 64-bit VLC and restart QGIS.",
    "Ouvre une vidéo avec VLC avant de charger un fichier SRT.": "Open a video with VLC before loading an SRT file.",
    "VLC n'a pas pu charger ce fichier de sous-titres.": "VLC could not load this subtitle file.",
    "Fichier supprimé ou déplacé. Actualise le dossier.": "File moved or deleted. Refresh the folder.",
    "Pour YouTube, utilise l'onglet Web (une page YouTube n'est pas un flux MP4 direct).":
        "For YouTube, use the Web tab (a YouTube page is not a direct MP4 stream).",
    "Aucun moteur multimédia disponible. Installe VLC 64 bits.": "No multimedia engine found. Install 64-bit VLC.",
    "Aucun moteur audio disponible. Installe VLC 64 bits puis relance QGIS.":
        "No audio engine found. Install 64-bit VLC and restart QGIS.",
    "Pistes audio et sous-titres : VLC requis.": "Audio/subtitle tracks require VLC.",
    "Chargement de la vidéo…": "Loading video…",
    "Connexion au direct…": "Connecting to live stream…",
    "Lance d'abord une vidéo.": "Start a video first.",
    "Aucun site valide pour cette station.": "No valid website for this station.",
    "Aucun flux HTTP(S) valide à ouvrir.": "No valid HTTP(S) stream to open.",
    "VLC.exe est introuvable sur ce PC.": "VLC.exe was not found on this computer.",
    "Flux ouvert dans VLC (fenêtre externe).": "Stream opened in external VLC.",
    "Lecteur audio indisponible : installe VLC 64 bits.": "Audio player unavailable: install 64-bit VLC.",
    "Test audio local : un bip discret doit être audible.": "Local audio test: a short beep should be audible.",
    "Test audio en cours — bip local.": "Audio test in progress — local beep.",
    "Impossible de lancer VLC (échec du processus Qt).": "Could not launch VLC (Qt process failed).",
    "Impossible d'activer cette piste audio.": "Could not activate this audio track.",
    "Impossible d'activer ces sous-titres.": "Could not enable these subtitles.",
    "Média : indisponible": "Media: unavailable",
    "Écouter": "Listen",
    "Le serveur ne répond pas": "Server timed out",
    "Connexion à": "Connecting to",
    "Station personnelle ajoutée.": "Custom station added.",
    "Station personnelle ajoutée.": "Custom station added.",
    "Les stations proposées ne peuvent pas être supprimées.": "Featured stations cannot be removed.",
    "Indique un nom et un flux HTTP(S) valide.": "Enter a name and a valid HTTP(S) stream.",
    "Nom trop long (70 caractères maximum).": "Name too long (maximum 70 characters).",
    "Une station de ce nom existe déjà dans ce pays.": "A station with this name already exists in this country.",
    "Radio arrêtée.": "Radio stopped.",
    "Lien du flux copié dans le presse-papiers.": "Stream URL copied to clipboard.",
    "Bloc-notes": "Notepad",
    "Une idée, une requête SQL ou un lien utile ? Ces notes restent sur ce PC.":
        "An idea, SQL query or useful link? Your notes stay on this computer.",
    "Mes notes…": "My notes…", "Sauvegarde automatique": "Autosave",
    "Copier": "Copy", "Vider": "Clear", "Notes": "Notes",
    "Effacer les notes": "Clear notes", "Effacer toutes les notes enregistrées ?": "Delete all saved notes?",
    "Media Hub — Paramètres": "Media Hub — Settings",
    "Activer les raccourcis vidéo": "Enable video shortcuts",
    "Appuie sur la touche souhaitée (une seule combinaison).": "Press the desired key (one combination only).",
    "Raccourcis par défaut": "Reset shortcuts", "Raccourcis": "Shortcuts",
    "Ouvrir Media Hub au démarrage de QGIS": "Open Media Hub when QGIS starts",
    "Utiliser le réseau / proxy QGIS pour la radio": "Use QGIS network/proxy for radio",
    "Mode sombre dans Media Hub et le PiP": "Dark mode in Media Hub and PiP",
    "Replier les commandes du PiP par défaut": "Hide PiP controls by default",
    "Le bouton Afficher/Masquer reste toujours visible en plein écran (H par défaut). Le mode sombre ne modifie pas le thème général de QGIS.":
        "The Show/Hide button remains visible in fullscreen (H by default). Dark mode does not change the global QGIS theme.",
    "Un proxy professionnel peut limiter l'accès aux radios même si la navigation Web fonctionne.":
        "Corporate proxies may block radio even when website browsing works.",
    "Les notes, les favoris Web et le dossier vidéo sont enregistrés localement dans QGIS.":
        "Notes, bookmarks and video folder settings are saved locally in QGIS.",
    "Préférences": "Preferences", "Auteur : JulienH77 · Licence MIT": "Author: JulienH77 · MIT license",
    "Ouvrir les problèmes GitHub": "Open GitHub issues", "Diagnostic": "Diagnostics",
    "Une même combinaison a été attribuée plusieurs fois.": "A key combination was assigned more than once.",
    "Media Hub — Raccourcis": "Media Hub — Shortcuts",
    "Volume actuel : {} %": "Current volume: {}%",
    "Aucune connexion audio": "No audio connection", "Moteur :": "Engine:",
    "Réseau QGIS": "QGIS network", "VLC direct": "Direct VLC",
}


def language():
    """QGIS language override takes priority over the OS locale when enabled."""
    settings = QSettings()
    selected = str(settings.value(PREFIX + "ui_language", "auto") or "auto")
    if selected in ("fr", "en"):
        return selected
    override = str(settings.value("locale/overrideFlag", "false")).lower()
    if override in ("true", "1"):
        loc = str(settings.value("locale/userLocale", "") or "")
    else:
        loc = QLocale.system().name()
    return "fr" if loc.lower().startswith("fr") else "en"


def tr_ui(value):
    """Translate known user-facing messages, leaving custom names/paths intact."""
    if language() == "fr" or not isinstance(value, str):
        return value
    if value in EN:
        return EN[value]
    return value
