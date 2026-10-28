# -*- coding: utf-8 -*-
"""Interface claire pour QGIS 3.44 : vidéo, WebEngine, radio, notes.

Le navigateur et les moteurs multimédias sont chargés à la demande : l'absence
 d'un module optionnel ne doit jamais empêcher le plugin de démarrer.
"""
import json
import os
import shutil
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from qgis.PyQt.QtCore import Qt, QProcess, QProcessEnvironment, QSettings, QTimer, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QKeySequence
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDockWidget, QDoubleSpinBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QShortcut,
    QSizePolicy, QSlider, QStackedWidget, QTabWidget, QTextEdit,
    QToolButton, QVBoxLayout, QWidget,
)

from .vlc_backend import VLCBackend, QMediaPlayer, find_vlc

SETTINGS = "qgis_media_hub/"
# Flux publies par les annuaires de radios (oct. 2026). Des serveurs peuvent
# etre injoignables depuis les reseaux professionnels : aucune garantie reseau.
RTL_STREAM = "https://icecast.rtl.fr/rtl-1-44-128"
RADIO_ALTERNATIVES = {
    "RTL": [
        "https://icecast.rtl.fr/rtl-1-44-128",
        "https://icecast.rtl.fr/rtl-1-44-64",
        "https://icecast.rtl.fr/rtl-1-44-128?listen=webCdn",
    ],
    "France Inter": [
        "https://icecast.radiofrance.fr/franceinter-midfi.mp3?id=openapi",
        "https://direct.franceinter.fr/live/franceinter-midfi.mp3",
    ],
    "FIP": [
        "https://icecast.radiofrance.fr/fip-midfi.mp3?id=openapi",
        "https://direct.fipradio.fr/live/fip-midfi.mp3",
    ],
    "RMC": [
        "https://audio.bfmtv.com/rmcradio_128.mp3",
    ],
}
DEFAULT_RADIOS = [(name, sources[0]) for name, sources in RADIO_ALTERNATIVES.items()]
RADIO_ATTEMPT_TIMEOUT_MS = 16000


def label(text, muted=False):
    w = QLabel(text)
    w.setWordWrap(True)
    if muted:
        w.setStyleSheet("color: #6e7983; font-size: 11px;")
    return w


def title(text):
    w = QLabel(text)
    w.setStyleSheet("font-size: 14px; font-weight: 600; color: #35434e;")
    return w


def make_button(text, callback, tooltip=None):
    b = QPushButton(text)
    b.clicked.connect(callback)
    if tooltip:
        b.setToolTip(tooltip)
    return b


def time_label(milliseconds):
    seconds = max(0, int(milliseconds) // 1000)
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)
    return "{:02d}:{:02d}".format(minutes, seconds)


def normalize_media(value):
    """Retourne (type, source), sans requêtes réseau ni lancement de schéma dangereux."""
    raw = (value or "").strip().strip('"')
    if not raw:
        raise ValueError("Choisis un fichier ou renseigne une URL.")
    parsed = urlparse(raw)
    if parsed.scheme.lower() in ("http", "https"):
        if not parsed.netloc:
            raise ValueError("URL Internet incomplète.")
        return "web", raw
    if raw.lower().startswith("file://"):
        path = QUrl(raw).toLocalFile()
    elif len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha():
        path = raw  # Lecteur Windows : D:\\video.mp4
    elif parsed.scheme:
        raise ValueError("Seuls les fichiers locaux et les liens HTTP(S) sont acceptés.")
    else:
        path = os.path.expanduser(raw)
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise ValueError("Fichier introuvable : {}".format(path))
    return "local", path


class FloatPlayer(QWidget):
    """PiP léger qui accueille la *même* surface vidéo, sans second lecteur."""

    def __init__(self, dock):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.dock = dock
        self.setWindowTitle("Media Hub — Vidéo flottante")
        self.setMinimumSize(330, 220)
        self.resize(520, 345)
        self.setStyleSheet("background-color: #f8f9fb;")
        base = QVBoxLayout(self)
        base.setContentsMargins(5, 5, 5, 5)
        base.setSpacing(5)
        self.canvas_layout = QVBoxLayout()
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        base.addLayout(self.canvas_layout, 1)
        buttons = QHBoxLayout()
        self.close_button = make_button("↩ QGIS", self.return_to_dock)
        buttons.addWidget(self.close_button)
        buttons.addWidget(make_button("−10 s", lambda: dock.skip(-10000)))
        self.play_button = make_button("Pause", dock.toggle_play)
        buttons.addWidget(self.play_button)
        buttons.addWidget(make_button("+10 s", lambda: dock.skip(10000)))
        self.speed_box = QDoubleSpinBox()
        self.speed_box.setRange(0.1, 5.0)
        self.speed_box.setSingleStep(0.1)
        self.speed_box.setDecimals(1)
        self.speed_box.setSuffix("×")
        self.speed_box.setValue(dock.speed.value())
        self.speed_box.setMaximumWidth(80)
        self.speed_box.valueChanged.connect(dock.speed.setValue)
        dock.speed.valueChanged.connect(self.speed_box.setValue)
        buttons.addWidget(self.speed_box)
        buttons.addWidget(make_button("⛶", self.toggle_fullscreen, "Plein écran / retour"))
        base.addLayout(buttons)
        self._esc = QShortcut(QKeySequence("Escape"), self)
        self._esc.activated.connect(self._on_escape)
        self._returning = False
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _on_escape(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.return_to_dock()

    def return_to_dock(self):
        if not self._returning:
            self._returning = True
            self.dock.restore_video()

    def closeEvent(self, event):  # noqa: N802
        if not self._returning:
            event.ignore()
            self.return_to_dock()
        else:
            event.accept()


class MediaHubDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Media Hub", parent)
        self.setObjectName("qgisMediaHubDock")
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable |
                         QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.setMinimumWidth(330)
        self.resize(475, 680)
        self.prefs = QSettings()
        self.player = None
        self.engine = "none"
        self.engine_detail = ""
        self.current_kind = None
        self.current_source = None
        self.current_duration = 0
        self.loaded = False
        self._load_id = 0
        self._moving = False
        self._popup = None
        self._seek_pressed = False
        self._radio_session = 0
        self._radio_sources = []
        self._radio_attempt_index = -1
        self._radio_retry_pending = False
        self._radio_last_error = ""
        self._radio_last_url = ""
        self._radio_relay = None
        self._radio_relay_active = False
        self.web = None
        self._web_initialized = False
        self._web_full = None
        self._notes_timer = QTimer(self)
        self._notes_timer.setSingleShot(True)
        self._notes_timer.setInterval(650)
        self._notes_timer.timeout.connect(self._save_notes)

        body = QWidget(self)
        self.setWidget(body)
        outer = QVBoxLayout(body)
        outer.setContentsMargins(8, 9, 8, 7)
        outer.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(title("Media Hub"))
        author_tag = QLabel("par JulienH77")
        author_tag.setToolTip("Media Hub © 2026 JulienH77 — licence MIT — QGIS 3.44")
        author_tag.setStyleSheet("color: #7b858c; font-size: 10px;")
        head.addWidget(author_tag)
        head.addStretch(1)
        self.settings_btn = QToolButton()
        self.settings_btn.setText("⚙")
        self.settings_btn.setToolTip("Paramètres et diagnostics")
        self.settings_btn.clicked.connect(self._settings_dialog)
        head.addWidget(self.settings_btn)
        outer.addLayout(head)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        outer.addWidget(self.tabs, 1)
        self._create_video_tab()
        self._create_browser_tab()
        self._create_radio_tab()
        self._create_notes_tab()
        self.tabs.currentChanged.connect(self._tab_changed)

        footer = QHBoxLayout()
        self.global_state = label("Initialisation des lecteurs…", True)
        self.global_state.setWordWrap(False)
        footer.addWidget(self.global_state, 1)
        self.start_checkbox = QCheckBox("Au démarrage")
        self.start_checkbox.setToolTip("Afficher automatiquement ce panneau au lancement de QGIS")
        self.start_checkbox.setChecked(str(self.prefs.value(SETTINGS + "open_on_start", "false")).lower() in ("true", "1"))
        self.start_checkbox.toggled.connect(lambda checked: self.prefs.setValue(SETTINGS + "open_on_start", bool(checked)))
        footer.addWidget(self.start_checkbox)
        outer.addLayout(footer)
        self._initialize_player()
        self._load_radio_presets()
        saved_tab = int(self.prefs.value(SETTINGS + "tab", 0) or 0)
        self.tabs.setCurrentIndex(max(0, min(3, saved_tab)))
        if self.tabs.currentIndex() == 1:
            self._initialize_web()

    # ------ VIDÉOS ------
    def _create_video_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(7, 12, 7, 9)
        lay.setSpacing(9)
        lay.addWidget(title("Mes vidéos"))
        lay.addWidget(label("Fichiers MP4, MKV, AVI… ou liens directs vers un média.", True))
        row = QHBoxLayout()
        self.file_btn = make_button("Ouvrir…", self._open_file)
        row.addWidget(self.file_btn)
        self.video_url = QLineEdit()
        self.video_url.setPlaceholderText("Chemin ou URL directe…")
        self.video_url.setClearButtonEnabled(True)
        self.video_url.returnPressed.connect(self._play_from_text)
        row.addWidget(self.video_url, 1)
        row.addWidget(make_button("Lire", self._play_from_text))
        lay.addLayout(row)
        self.video_holder = QWidget()
        self.video_holder_layout = QVBoxLayout(self.video_holder)
        self.video_holder_layout.setContentsMargins(0, 0, 0, 0)
        self.video_holder_layout.setSpacing(0)
        self.video_placeholder = label("Ouvre une vidéo pour commencer.")
        self.video_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_placeholder.setStyleSheet("background: #eef1f4; color: #74818d; border: 1px solid #dce2e6;")
        self.video_placeholder.setMinimumHeight(175)
        self.video_holder_layout.addWidget(self.video_placeholder)
        self.video_holder.setMinimumHeight(185)
        self.video_holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(self.video_holder, 1)

        # Déjà enfant du dock AVANT de créer le HWND VLC : sinon Qt pourrait
        # recréer le handle natif au premier affichage (vidéo noire).
        self.vlc_canvas = QFrame(self.video_holder)
        self.vlc_canvas.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.vlc_canvas.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self.vlc_canvas.setStyleSheet("background: #121517;")
        self.vlc_canvas.setMinimumHeight(150)
        self.vlc_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_holder_layout.addWidget(self.vlc_canvas)
        self.vlc_canvas.hide()
        self.qt_canvas = None
        self.active_canvas = self.vlc_canvas

        self.video_title = label("Aucun média", True)
        self.video_title.setWordWrap(False)
        self.video_title.setToolTip("Nom de la vidéo")
        lay.addWidget(self.video_title)

        seek_row = QHBoxLayout()
        self.elapsed = label("00:00")
        self.total = label("00:00")
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.sliderPressed.connect(self._seek_press)
        self.seek.sliderReleased.connect(self._seek_release)
        seek_row.addWidget(self.elapsed)
        seek_row.addWidget(self.seek, 1)
        seek_row.addWidget(self.total)
        lay.addLayout(seek_row)

        controls = QHBoxLayout()
        controls.addWidget(make_button("−10 s", lambda: self.skip(-10000)))
        self.play_video_btn = make_button("▶ Lecture", self.toggle_play)
        controls.addWidget(self.play_video_btn)
        controls.addWidget(make_button("+10 s", lambda: self.skip(10000)))
        controls.addStretch(1)
        controls.addWidget(label("Vitesse"))
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.1, 5.0)
        self.speed.setDecimals(1)
        self.speed.setSingleStep(0.1)
        self.speed.setSuffix("×")
        self.speed.setFixedWidth(72)
        self.speed.setValue(float(self.prefs.value(SETTINGS + "speed", 1.0) or 1.0))
        self.speed.valueChanged.connect(self._set_speed)
        controls.addWidget(self.speed)
        lay.addLayout(controls)

        bottom = QHBoxLayout()
        bottom.addWidget(make_button("PiP", self.float_video, "Mini-lecteur flottant toujours au premier plan"))
        bottom.addWidget(make_button("Plein écran", self.fullscreen_video, "Plein écran vidéo ; Échap pour quitter"))
        self.mute_btn = make_button("Muet", self._toggle_mute)
        bottom.addWidget(self.mute_btn)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 200)
        self.volume_slider.setToolTip("Volume VLC de 0 à 200 %. Au-delà de 100 %, risque de saturation.")
        self.volume_slider.setValue(int(self.prefs.value(SETTINGS + "volume", 80)))
        self.volume_slider.valueChanged.connect(self._set_volume)
        bottom.addWidget(self.volume_slider, 1)
        self.volume_text = label("80 %")
        self.volume_text.setMinimumWidth(40)
        bottom.addWidget(self.volume_text)
        lay.addLayout(bottom)
        self.video_status = label("", True)
        lay.addWidget(self.video_status)
        self.tabs.addTab(page, "Vidéo")

    def _initialize_player(self):
        dll_path = find_vlc()
        self.engine_detail = "VLC 64 bits non trouvé."
        if dll_path:
            try:
                self.player = VLCBackend(self.vlc_canvas, dll_path, self)
                self.engine = "vlc"
                self.engine_detail = "VLC : " + dll_path
            except (Exception,) as exc:
                self.engine_detail = "VLC détecté mais inutilisable : {}".format(exc)
        if self.player is None:
            try:
                try:
                    from qgis.PyQt.QtMultimedia import QMediaContent, QMediaPlayer as QtMedia
                    from qgis.PyQt.QtMultimediaWidgets import QVideoWidget
                except ImportError:
                    from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer as QtMedia
                    from PyQt5.QtMultimediaWidgets import QVideoWidget
                self.qt_media_content = QMediaContent
                self.qt_canvas = QVideoWidget(self.video_holder)
                self.qt_canvas.setMinimumHeight(150)
                self.qt_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                self.video_holder_layout.addWidget(self.qt_canvas)
                self.qt_canvas.hide()
                self.player = QtMedia(self, QtMedia.VideoSurface)
                self.player.setVideoOutput(self.qt_canvas)
                self.active_canvas = self.qt_canvas
                self.engine = "qt"
                self.volume_slider.setMaximum(100)
                if not self.player.isAvailable():
                    self.engine_detail += " Qt Multimedia sans service de décodage opérationnel."
            except Exception as exc:
                self.engine_detail += " Qt Multimedia absent : {}".format(exc)
                self.player = None
                self.engine = "none"
        if self.player is None:
            self._set_video_status("Lecteur indisponible. Installe VLC 64 bits puis relance QGIS.", True)
            self.global_state.setText("Média : indisponible")
            return
        self.global_state.setText("Lecteur : " + ("VLC" if self.engine == "vlc" else "Qt (secours)"))
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.stateChanged.connect(self._state_changed)
        self.player.mediaStatusChanged.connect(self._media_status)
        if hasattr(self.player, "error"):
            self.player.error.connect(self._media_error)
        self._set_volume(self.volume_slider.value())
        self._set_speed(self.speed.value())
        self._set_video_status("Moteur : {}. {}".format(self.engine.upper(), "Prêt." if self.engine == "vlc" else "VLC recommandé."))

    def _open_file(self):
        recent = str(self.prefs.value(SETTINGS + "last_directory", str(Path.home())) or str(Path.home()))
        if not os.path.isdir(recent):
            recent = str(Path.home())
        source, _ = QFileDialog.getOpenFileName(self, "Choisir une vidéo", recent,
                         "Vidéos (*.mp4 *.mkv *.avi *.mov *.webm *.m4v *.wmv *.mpg *.mpeg *.ts);;Tous les fichiers (*)")
        if source:
            self.prefs.setValue(SETTINGS + "last_directory", os.path.dirname(source))
            self.video_url.setText(source)
            self._play_from_text()

    def _play_from_text(self):
        try:
            kind, source = normalize_media(self.video_url.text())
        except ValueError as exc:
            self._set_video_status(str(exc), True)
            return
        if kind == "web" and (urlparse(source).hostname or "").lower() in ("youtube.com", "www.youtube.com", "youtu.be"):
            self._set_video_status("Pour YouTube, utilise l'onglet Web (une page YouTube n'est pas un flux MP4 direct).", True)
            return
        self.play_source(kind, source, "video")

    def play_source(self, kind, source, mode):
        if not self.player:
            self._set_video_status("Aucun moteur multimédia disponible. Installe VLC 64 bits.", True)
            self._set_radio_status("Aucun moteur audio disponible. Installe VLC 64 bits puis relance QGIS.", True)
            return
        if self._popup:
            self.restore_video()
        self.loaded = False
        self._load_id += 1
        token = self._load_id
        self.current_kind = mode
        self.current_source = (kind, source)
        self.current_duration = 0
        self.seek.setRange(0, 0)
        self.elapsed.setText("00:00")
        self.total.setText("00:00")
        self.player.stop()
        if mode == "video":
            self._radio_session += 1
            self._radio_retry_pending = False
            if self._radio_relay:
                self._radio_relay._cancel_active()
            self._show_video_canvas()
            self.video_title.setText(os.path.basename(source.rstrip("/")) or "Vidéo en ligne")
            self.video_title.setToolTip(source)
            self._set_video_status("Chargement de la vidéo…")
            self.tabs.setCurrentIndex(0)
        else:
            self._hide_video_canvas()
            self._set_radio_status("Connexion au direct…")
        try:
            if self.engine == "vlc":
                success = self.player.load_media(kind, source)
                if not success:
                    raise RuntimeError(self.player.errorString() or "Source non chargée")
            else:
                url = QUrl(source) if kind == "web" else QUrl.fromLocalFile(source)
                self.player.setMedia(self.qt_media_content(url))
            self.player.setPlaybackRate(self.speed.value() if mode == "video" else 1.0)
            self.player.play()
            if mode == "video" and self.engine == "vlc":
                QTimer.singleShot(350, self._rebind_initial_video)
        except Exception as exc:
            self._media_failed(str(exc))
            return
        # La radio gere son propre minuteur et ses URL alternatives.
        if mode == "video":
            QTimer.singleShot(20000, lambda key=token: self._loading_timeout(key))

    def _rebind_initial_video(self):
        if self.engine == "vlc" and self.player and self.current_kind == "video" and not self._popup:
            try:
                self.player.rebind_surface()
            except Exception as exc:
                self._set_video_status("Surface vidéo indisponible : {}".format(exc), True)

    def _loading_timeout(self, token):
        if token != self._load_id or self.loaded or not self.player:
            return
        if self.player.state() == QMediaPlayer.PlayingState:
            self._state_changed(QMediaPlayer.PlayingState)
            return
        self._media_failed("Le flux ne démarre pas (délai de 20 secondes). Vérifie l'URL, le réseau ou le moteur VLC.")
        self.player.stop()

    def _media_failed(self, message):
        if self.current_kind == "radio":
            self._radio_last_error = str(message)
            if self.current_source and self.current_source[0] == "local":
                self._set_radio_status("Test sonore impossible : {}".format(message), True)
            else:
                self._schedule_radio_retry(str(message))
        else:
            self._set_video_status(message, True)

    def _show_video_canvas(self):
        self.video_placeholder.hide()
        if self.active_canvas.parent() is not self.video_holder:
            self.active_canvas.setParent(self.video_holder)
            self.video_holder_layout.addWidget(self.active_canvas)
        self.active_canvas.show()

    def _hide_video_canvas(self):
        self.active_canvas.hide()
        self.video_placeholder.setText("La radio est en cours de lecture.\nReviens aux vidéos pour lire un fichier.")
        self.video_placeholder.show()

    def _set_video_status(self, text, error=False):
        self.video_status.setText(text)
        self.video_status.setStyleSheet("color: #ad3838;" if error else "color: #71808a; font-size: 11px;")
        self.video_status.setToolTip(text)

    def _set_radio_status(self, text, error=False):
        self.radio_status.setText(text)
        self.radio_status.setStyleSheet("color: #ad3838;" if error else "color: #71808a; font-size: 11px;")
        self.radio_status.setToolTip(text)

    def toggle_play(self):
        if not self.player:
            return
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        elif self.current_source:
            self.player.play()
        elif self.video_url.text().strip():
            self._play_from_text()

    def skip(self, delta):
        if self.current_kind != "video" or not self.player or not self.player.isSeekable():
            return
        target = max(0, self.player.position() + int(delta))
        if self.current_duration > 0:
            target = min(self.current_duration, target)
        self.player.setPosition(target)

    def _seek_press(self):
        self._seek_pressed = True

    def _seek_release(self):
        self._seek_pressed = False
        if self.current_kind == "video" and self.player and self.player.isSeekable():
            self.player.setPosition(self.seek.value())

    def _position_changed(self, ms):
        if self.current_kind != "video":
            return
        self.elapsed.setText(time_label(ms))
        if not self._seek_pressed:
            self.seek.setValue(max(0, min(self.seek.maximum(), int(ms))))

    def _duration_changed(self, ms):
        if self.current_kind != "video":
            return
        self.current_duration = max(0, int(ms))
        self.seek.setRange(0, self.current_duration)
        self.total.setText(time_label(self.current_duration))

    def _state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.loaded = True
        self.play_video_btn.setText("⏸ Pause" if state == QMediaPlayer.PlayingState else "▶ Lecture")
        self.radio_play_btn.setText("⏸ Pause" if state == QMediaPlayer.PlayingState and self.current_kind == "radio" else "▶ Reprendre")
        if self._popup:
            self._popup.play_button.setText("Pause" if state == QMediaPlayer.PlayingState else "Lecture")
        if self.current_kind == "radio" and state == QMediaPlayer.PlayingState:
            self._radio_retry_pending = False
            self.radio_play_btn.setText("⏸ Pause")
            if self.current_source and self.current_source[0] == "local":
                self._set_radio_status("Test audio en cours — bip local.")
            else:
                self._set_radio_status("En direct — {} · moteur {} · flux {}/{}".format(
                    self.radio_name, self.engine.upper(),
                    self._radio_attempt_index + 1, max(1, len(self._radio_sources))))
        if self.current_kind == "video" and state == QMediaPlayer.PlayingState:
            self._set_video_status("Lecture en cours · {}".format(self.engine.upper()))

    def _media_status(self, status):
        if status == QMediaPlayer.InvalidMedia:
            self._media_failed(self.player.errorString() or "Média invalide ou codec indisponible.")

    def _media_error(self, *unused):
        self._media_failed(self.player.errorString() or "Erreur du lecteur audio/vidéo.")

    def _set_speed(self, value):
        self.prefs.setValue(SETTINGS + "speed", float(value))
        if self.player and self.current_kind != "radio":
            self.player.setPlaybackRate(float(value))

    def _set_volume(self, value):
        self.volume_text.setText("{} %".format(value))
        self.prefs.setValue(SETTINGS + "volume", int(value))
        if self.player:
            self.player.setVolume(int(value))

    def _toggle_mute(self):
        if self.player:
            now = not self.player.isMuted()
            self.player.setMuted(now)
            self.mute_btn.setText("Activer son" if now else "Muet")

    def _transition_canvas(self, target_layout, new_parent):
        if not self.player:
            return
        was_playing = self.player.state() == QMediaPlayer.PlayingState
        was_paused = self.player.state() == QMediaPlayer.PausedState
        position = self.player.position()
        self._moving = True
        if self.engine == "vlc" and self.current_source:
            self.player.stop()
        self.active_canvas.hide()
        self.active_canvas.setParent(new_parent)
        target_layout.addWidget(self.active_canvas)
        self.active_canvas.show()

        def reconnect():
            if self.engine == "vlc":
                try:
                    self.player.rebind_surface()
                except Exception as exc:
                    self._set_video_status("Échec du changement de fenêtre : {}".format(exc), True)
                    self._moving = False
                    return
                if was_playing or was_paused:
                    self.player.play()
                    # Attendre que VLC soit prêt pour replacer sa position de lecture.
                    QTimer.singleShot(550, lambda: self._restore_position(position, was_paused))
            elif self.engine == "qt":
                self.player.setVideoOutput(self.active_canvas)
            self._moving = False
        QTimer.singleShot(180, reconnect)

    def _restore_position(self, position, paused):
        if not self.player or self.current_kind != "video":
            return
        if position > 0 and self.player.isSeekable():
            self.player.setPosition(position)
        if paused:
            self.player.pause()

    def float_video(self):
        if self.current_kind != "video" or not self.player:
            self._set_video_status("Lance d'abord une vidéo.")
            return
        if self._popup:
            self._popup.raise_()
            self._popup.activateWindow()
            return
        self._popup = FloatPlayer(self)
        self._popup.show()
        self.video_placeholder.setText("Vidéo dans la mini-fenêtre. Clique sur « QGIS » pour la récupérer.")
        self.video_placeholder.show()
        self._transition_canvas(self._popup.canvas_layout, self._popup)

    def fullscreen_video(self):
        self.float_video()
        if self._popup:
            self._popup.showFullScreen()

    def restore_video(self):
        if not self._popup:
            return
        pop = self._popup
        self.video_placeholder.hide()
        self._transition_canvas(self.video_holder_layout, self.video_holder)
        self._popup = None
        pop._returning = True
        # Détruire après transfert du widget vidéo; ne pas toucher au lecteur.
        QTimer.singleShot(350, pop.close)

    # ------ WEB ------
    def _create_browser_tab(self):
        self.browser_page = QWidget()
        lay = QVBoxLayout(self.browser_page)
        lay.setContentsMargins(5, 10, 5, 7)
        lay.setSpacing(7)
        actions = QHBoxLayout()
        self.back_btn = make_button("‹", self._web_back, "Page précédente")
        actions.addWidget(self.back_btn)
        self.next_btn = make_button("›", self._web_forward, "Page suivante")
        actions.addWidget(self.next_btn)
        actions.addWidget(make_button("⟳", self._web_reload, "Actualiser"))
        self.address = QLineEdit()
        self.address.setPlaceholderText("Adresse Internet ou recherche…")
        self.address.returnPressed.connect(self._open_address)
        actions.addWidget(self.address, 1)
        actions.addWidget(make_button("Aller", self._open_address))
        lay.addLayout(actions)
        shortcuts = QHBoxLayout()
        shortcuts.addWidget(make_button("▶ YouTube", lambda: self._navigate("https://www.youtube.com/")))
        shortcuts.addWidget(make_button("Recherche", lambda: self._navigate("https://www.google.com/")))
        shortcuts.addWidget(make_button("QGIS", lambda: self._navigate("https://docs.qgis.org/3.44/fr/docs/")))
        shortcuts.addStretch(1)
        shortcuts.addWidget(make_button("↗", self._web_external, "Ouvrir cette page dans le navigateur normal"))
        lay.addLayout(shortcuts)
        favorites_row = QHBoxLayout()
        favorites_row.addWidget(label("Favoris", True))
        self.favorites_combo = QComboBox()
        self.favorites_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        favorites_row.addWidget(self.favorites_combo, 1)
        favorites_row.addWidget(make_button("Aller", self._favorite_go))
        favorites_row.addWidget(make_button("+", self._favorite_add, "Enregistrer l'adresse actuelle"))
        favorites_row.addWidget(make_button("−", self._favorite_remove, "Supprimer ce favori"))
        lay.addLayout(favorites_row)
        self._load_favorites()
        self.web_container = QVBoxLayout()
        self.web_container.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(self.web_container, 1)
        self.web_placeholder = label("Le navigateur Chromium s'initialisera à l'ouverture de cet onglet.", True)
        self.web_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.web_container.addWidget(self.web_placeholder)
        self.web_info = label("Qt WebEngine : un navigateur intégré ne sera pas forcément aussi rapide que Firefox.", True)
        lay.addWidget(self.web_info)
        self.tabs.addTab(self.browser_page, "Web")

    def _initialize_web(self):
        if self._web_initialized:
            return
        self._web_initialized = True
        try:
            try:
                from qgis.PyQt.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
            except ImportError:
                from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
            self.web = QWebEngineView(self.browser_page)
            self.web.setMinimumHeight(250)
            self.web.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            st = self.web.settings()
            st.setAttribute(QWebEngineSettings.PluginsEnabled, True)
            st.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            try:
                st.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
            except AttributeError:
                pass
            self.web.urlChanged.connect(self._web_url_changed)
            self.web.loadFinished.connect(self._web_finished)
            self.web.page().fullScreenRequested.connect(self._web_fullscreen_requested)
            self.web_placeholder.hide()
            self.web_container.addWidget(self.web)
            self.web_info.setText("Chromium intégré (Qt WebEngine). Certaines vidéos et connexions protégées peuvent échouer.")
            # Pas de requête Internet au démarrage tant que l'utilisateur n'a pas choisi de site.
            self._navigate(str(self.prefs.value(SETTINGS + "web_last", "https://www.youtube.com/") or "https://www.youtube.com/"))
        except Exception as exc:
            self.web = None
            self.web_placeholder.setText("Qt WebEngine est indisponible dans ce QGIS.\n\n"
                "Windows (OSGeo4W) : installer « python3-pyqtwebengine » depuis l'installeur avancé, puis redémarrer QGIS.\n\n"
                "Détail : {}".format(exc))
            self.web_info.setText("Le reste de Media Hub (vidéos, radio, notes) continue de fonctionner.")

    @staticmethod
    def _to_web_url(text):
        text = (text or "").strip()
        if not text:
            return QUrl("https://www.youtube.com/")
        if "://" in text:
            p = urlparse(text)
            if p.scheme.lower() not in ("http", "https") or not p.netloc:
                raise ValueError("Seules les adresses HTTP et HTTPS sont autorisées.")
            return QUrl(text)
        if " " in text or "." not in text:
            return QUrl("https://www.google.com/search?q=" + quote_plus(text))
        return QUrl("https://" + text)

    def _navigate(self, address):
        if not self._web_initialized:
            self._initialize_web()
        try:
            url = self._to_web_url(address)
        except ValueError as exc:
            self.web_info.setText(str(exc))
            return
        if self.web:
            self.web.setUrl(url)
        else:
            self.address.setText(url.toString())

    def _open_address(self):
        self._navigate(self.address.text())

    def _web_back(self):
        if self.web:
            self.web.back()

    def _web_forward(self):
        if self.web:
            self.web.forward()

    def _web_reload(self):
        if self.web:
            self.web.reload()

    def _load_favorites(self):
        saved = self.prefs.value(SETTINGS + "web_favorites", "[]")
        try:
            pairs = json.loads(saved) if isinstance(saved, str) else []
        except (ValueError, TypeError):
            pairs = []
        self.favorites = []
        for pair in pairs:
            if (isinstance(pair, list) and len(pair) == 2 and
                    all(isinstance(x, str) for x in pair) and
                    pair[1].startswith(("http://", "https://"))):
                self.favorites.append((pair[0], pair[1]))
        self._refresh_favorites()

    def _refresh_favorites(self):
        self.favorites_combo.clear()
        for name, link in self.favorites:
            self.favorites_combo.addItem(name, link)

    def _favorite_go(self):
        if self.favorites_combo.count():
            self._navigate(self.favorites_combo.currentData())

    def _favorite_add(self):
        try:
            url = self._to_web_url(self.address.text()).toString()
        except ValueError:
            self.web_info.setText("Impossible d'enregistrer cette adresse en favori.")
            return
        name = (urlparse(url).hostname or "Site")[:65]
        if url not in [v for _, v in self.favorites]:
            self.favorites.append((name, url))
            self.prefs.setValue(SETTINGS + "web_favorites", json.dumps(self.favorites, ensure_ascii=False))
            self._refresh_favorites()
            self.favorites_combo.setCurrentIndex(self.favorites_combo.count() - 1)
            self.web_info.setText("Favori enregistré.")

    def _favorite_remove(self):
        index = self.favorites_combo.currentIndex()
        if index < 0:
            return
        del self.favorites[index]
        self.prefs.setValue(SETTINGS + "web_favorites", json.dumps(self.favorites, ensure_ascii=False))
        self._refresh_favorites()
        self.web_info.setText("Favori supprimé.")

    def _web_fullscreen_requested(self, request):
        if request.toggleOn():
            request.accept()
            if self._web_full is None and self.web:
                self._web_full = QWidget(None, Qt.WindowType.Window)
                self._web_full.setWindowTitle("Media Hub — Navigateur plein écran")
                self._web_full.setStyleSheet("background: white;")
                holder = QVBoxLayout(self._web_full)
                holder.setContentsMargins(0, 0, 0, 0)
                exit_btn = make_button("Quitter le plein écran (Échap)", self._web_restore)
                holder.addWidget(exit_btn)
                self.web.setParent(self._web_full)
                holder.addWidget(self.web, 1)
                QShortcut(QKeySequence("Escape"), self._web_full).activated.connect(self._web_restore)
                self._web_full.showFullScreen()
        else:
            request.accept()
            self._web_restore()

    def _web_restore(self):
        if not self._web_full:
            return
        previous = self._web_full
        self._web_full = None
        if self.web:
            self.web.setParent(self.browser_page)
            self.web_container.addWidget(self.web)
            self.web.show()
        previous.close()
        previous.deleteLater()

    def _web_external(self):
        try:
            url = self._to_web_url(self.address.text())
        except ValueError as exc:
            self.web_info.setText(str(exc))
            return
        QDesktopServices.openUrl(url)

    def _web_url_changed(self, url):
        self.address.setText(url.toString())
        self.prefs.setValue(SETTINGS + "web_last", url.toString())

    def _web_finished(self, success):
        self.web_info.setText("Page chargée." if success else
            "Échec de chargement. Si YouTube est lent ou refuse la lecture : utilise le bouton ↗ (navigateur externe).")

    # ------ RADIOS ------
    def _create_radio_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(11)
        lay.addWidget(title("Écouter la radio"))
        lay.addWidget(label("Flux directs, sans charger tout le site web.", True))
        lay.addWidget(label("Stations enregistrées"))
        self.station_combo = QComboBox()
        lay.addWidget(self.station_combo)
        self.use_qgis_network = QCheckBox("Connexion via QGIS (proxy du réseau)")
        self.use_qgis_network.setToolTip(
            "Fait passer l'audio Internet par les paramètres réseau et proxy de QGIS, "
            "puis transmet le flux à VLC en local. Utile sur un PC professionnel.")
        self.use_qgis_network.setChecked(
            str(self.prefs.value(SETTINGS + "radio_qgis_network", "true")).lower() in ("true", "1"))
        self.use_qgis_network.toggled.connect(
            lambda checked: self.prefs.setValue(SETTINGS + "radio_qgis_network", bool(checked)))
        lay.addWidget(self.use_qgis_network)
        buttons = QHBoxLayout()
        self.radio_play_btn = make_button("▶ Écouter", self.toggle_radio)
        buttons.addWidget(self.radio_play_btn)
        buttons.addWidget(make_button("■ Arrêter", self.stop_radio))
        lay.addLayout(buttons)
        tools = QHBoxLayout()
        tools.addWidget(make_button("Autre flux", self.try_next_radio, "Essayer un serveur alternatif"))
        tools.addWidget(make_button("Dans VLC ↗", self.open_radio_in_vlc,
                                     "Ouvrir ce flux avec l'application VLC, hors de QGIS"))
        tools.addWidget(make_button("Site radio ↗", self.open_station_site,
                                     "Écouter la station sur son site officiel dans Firefox/Chrome"))
        lay.addLayout(tools)
        volume_row = QHBoxLayout()
        volume_row.addWidget(label("Volume"))
        self.radio_volume = QSlider(Qt.Orientation.Horizontal)
        self.radio_volume.setRange(0, self.volume_slider.maximum())
        self.radio_volume.setValue(self.volume_slider.value())
        self.radio_volume.setToolTip("Volume de la radio, avec amplification à 200 % si moteur VLC")
        self.radio_volume.valueChanged.connect(self.volume_slider.setValue)
        self.volume_slider.valueChanged.connect(self.radio_volume.setValue)
        volume_row.addWidget(self.radio_volume, 1)
        self.radio_volume_label = label("{} %".format(self.radio_volume.value()))
        self.radio_volume.valueChanged.connect(
            lambda v: self.radio_volume_label.setText("{} %".format(v)))
        volume_row.addWidget(self.radio_volume_label)
        lay.addLayout(volume_row)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(line)
        lay.addWidget(label("Ajouter une station personnelle"))
        self.custom_name = QLineEdit()
        self.custom_name.setPlaceholderText("Nom (par exemple RTL)")
        lay.addWidget(self.custom_name)
        self.custom_stream = QLineEdit()
        self.custom_stream.setPlaceholderText("https://…/stream.mp3 ou .m3u8")
        lay.addWidget(self.custom_stream)
        extras = QHBoxLayout()
        extras.addWidget(make_button("+ Ajouter", self.add_station))
        extras.addWidget(make_button("Supprimer la station", self.remove_station))
        lay.addLayout(extras)
        self.radio_status = label("Choisis une station puis clique sur Écouter.", True)
        lay.addWidget(self.radio_status)
        self.radio_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.radio_detail = label("Moteur non initialisé", True)
        self.radio_detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.radio_detail)
        tools2 = QHBoxLayout()
        tools2.addWidget(make_button("Tester le son", self.test_radio_sound,
                                     "Jouer un court son local pour verifier la sortie audio"))
        tools2.addWidget(make_button("Copier le flux", self.copy_radio_url))
        tools2.addStretch(1)
        lay.addLayout(tools2)
        lay.addStretch(1)
        lay.addWidget(label("Sur un réseau de bureau, coche Connexion via QGIS pour utiliser le proxy de QGIS. Si le son ne fonctionne pas, ouvre le site officiel dans Firefox.", True))
        self.tabs.addTab(page, "Radio")
        self.radio_name = "RTL"

    def _load_radio_presets(self):
        raw = self.prefs.value(SETTINGS + "user_radios", "[]")
        try:
            data = json.loads(raw) if isinstance(raw, str) else []
        except (ValueError, TypeError):
            data = []
        self.radio_presets = list(DEFAULT_RADIOS)
        for item in data:
            if (isinstance(item, list) and len(item) == 2 and
                    isinstance(item[0], str) and isinstance(item[1], str) and
                    item[1].startswith(("https://", "http://"))):
                self.radio_presets.append((item[0], item[1]))
        self._refresh_radios()

    def _refresh_radios(self):
        current = self.station_combo.currentText()
        self.station_combo.clear()
        for name, url in self.radio_presets:
            self.station_combo.addItem(name, url)
        idx = self.station_combo.findText(current)
        if idx >= 0:
            self.station_combo.setCurrentIndex(idx)

    def toggle_radio(self):
        # Si la connexion a echoue, relancer tous les flux au lieu de simplement
        # appeler play() sur un lecteur VLC deja en erreur.
        if (self.player and self.current_kind == "radio" and
                self.radio_name == self.station_combo.currentText() and
                self.current_source and self.loaded):
            self.toggle_play()
            return
        self.start_radio()

    def start_radio(self):
        if not self.station_combo.count():
            return
        self.radio_name = self.station_combo.currentText()
        self._radio_relay_active = False
        if self.use_qgis_network.isChecked():
            if not self._radio_relay:
                try:
                    from .radio_relay import QgisRadioRelay
                    self._radio_relay = QgisRadioRelay(self)
                    self._radio_relay.failed.connect(self._radio_network_error)
                    self._radio_relay.progress.connect(self._radio_network_progress)
                except Exception as exc:
                    self._set_radio_status("Réseau QGIS indisponible : {}. Essai VLC direct.".format(exc), True)
            self._radio_relay_active = self._radio_relay is not None
        if self._radio_relay and not self._radio_relay_active:
            self._radio_relay._cancel_active()
        primary = str(self.station_combo.currentData() or "")
        candidates = list(RADIO_ALTERNATIVES.get(self.radio_name, []))
        if primary and primary not in candidates:
            candidates.insert(0, primary)
        self._radio_sources = list(dict.fromkeys(candidates))
        self._radio_session += 1
        self._radio_attempt_index = -1
        self._radio_retry_pending = False
        self._radio_last_error = ""
        self._start_radio_attempt(self._radio_session)

    def _start_radio_attempt(self, session):
        if session != self._radio_session:
            return
        self._radio_retry_pending = False
        self._radio_attempt_index += 1
        if self._radio_attempt_index >= len(self._radio_sources):
            # Toutes les adresses ont echoue. Ne pas rester sur "Connexion...".
            self.loaded = False
            self.radio_play_btn.setText("▶ Réessayer")
            self._set_radio_status(
                "Impossible de lire {} ({} flux essayés). {}. "
                "Teste « Dans VLC » : si ça échoue aussi, le réseau bloque peut-être la radio.".format(
                    self.radio_name, len(self._radio_sources),
                    self._radio_last_error or "Aucune connexion audio"), True)
            return
        url = self._radio_sources[self._radio_attempt_index]
        self._radio_last_url = url
        self.radio_play_btn.setText("Connexion…")
        self.radio_detail.setText("Moteur : {} · Connexion : {} · Flux {}/{} · {}".format(
            self.engine.upper(), "réseau QGIS" if self._radio_relay_active else "VLC direct",
            self._radio_attempt_index + 1, len(self._radio_sources), url))
        self._set_radio_status("Connexion à {} (serveur {}/{})…".format(
            self.radio_name, self._radio_attempt_index + 1, len(self._radio_sources)))
        playback_url = url
        if self._radio_relay_active:
            try:
                playback_url = self._radio_relay.url_for(url)
            except Exception as exc:
                self._schedule_radio_retry("Relais QGIS indisponible : {}".format(exc))
                return
        self.play_source("web", playback_url, "radio")
        if session != self._radio_session:
            return
        index = self._radio_attempt_index
        QTimer.singleShot(1400,
                          lambda sid=session, ix=index: self._radio_fast_status(sid, ix))
        QTimer.singleShot(RADIO_ATTEMPT_TIMEOUT_MS,
                          lambda sid=session, ix=index: self._radio_attempt_timeout(sid, ix))

    def _radio_network_progress(self, message):
        if self.current_kind == "radio" and self._radio_relay_active:
            self._set_radio_status(str(message))

    def _radio_network_error(self, message):
        if self.current_kind == "radio" and self._radio_relay_active:
            self._schedule_radio_retry(str(message))

    def _radio_fast_status(self, session, index):
        if (session == self._radio_session and index == self._radio_attempt_index and
                self.current_kind == "radio" and self.player and
                self.player.state() == QMediaPlayer.PlayingState):
            self._state_changed(QMediaPlayer.PlayingState)

    def _radio_attempt_timeout(self, session, index):
        if session != self._radio_session or index != self._radio_attempt_index:
            return
        if self.current_kind != "radio" or not self.player:
            return
        if self.player.state() == QMediaPlayer.PlayingState:
            self.loaded = True
            return
        self._schedule_radio_retry("Le serveur ne répond pas après {} s".format(
            RADIO_ATTEMPT_TIMEOUT_MS // 1000))

    def _schedule_radio_retry(self, reason):
        if self.current_kind != "radio" or self._radio_retry_pending:
            return
        self._radio_retry_pending = True
        self._radio_last_error = reason
        session = self._radio_session
        if self._radio_attempt_index + 1 < len(self._radio_sources):
            self._set_radio_status("{} — essai du serveur suivant…".format(reason))
        else:
            self._set_radio_status("{} — dernier serveur indisponible.".format(reason), True)
        # Deferred pour eviter de recharger libVLC depuis son propre signal.
        QTimer.singleShot(200, lambda sid=session: self._start_radio_attempt(sid))

    def try_next_radio(self):
        if self.current_kind != "radio" or not self._radio_sources:
            self.start_radio()
            return
        if self._radio_attempt_index + 1 >= len(self._radio_sources):
            self.start_radio()  # Reprend le tour depuis la premiere URL.
        else:
            self._schedule_radio_retry("Serveur change manuellement")

    def stop_radio(self):
        self._radio_session += 1  # Annule les rappels des essais precedents.
        self._radio_retry_pending = False
        if self._radio_relay:
            self._radio_relay._cancel_active()
        if self.player and self.current_kind == "radio":
            self.player.stop()
            self.current_source = None
            self.current_kind = None
            self.loaded = False
            self.radio_play_btn.setText("▶ Écouter")
            self._set_radio_status("Radio arrêtée.")

    def copy_radio_url(self):
        from qgis.PyQt.QtWidgets import QApplication
        url = self._radio_last_url or str(self.station_combo.currentData() or "")
        if url:
            QApplication.clipboard().setText(url)
            self._set_radio_status("Lien du flux copié dans le presse-papiers.")

    def open_station_site(self):
        sites = {
            "RTL": "https://www.rtl.fr/direct",
            "France Inter": "https://www.radiofrance.fr/franceinter",
            "FIP": "https://www.radiofrance.fr/fip",
            "RMC": "https://rmc.bfmtv.com/",
        }
        name = self.station_combo.currentText()
        url = sites.get(name) or str(self.station_combo.currentData() or "")
        if not url.startswith(("https://", "http://")):
            self._set_radio_status("Aucun site valide pour cette station.", True)
            return
        QDesktopServices.openUrl(QUrl(url))

    def _vlc_executable(self):
        # Priorite a la meme installation que libvlc.dll.
        dll = find_vlc()
        candidates = []
        if dll:
            candidates.append(os.path.join(os.path.dirname(dll), "vlc.exe"))
        path = shutil.which("vlc.exe")
        if path:
            candidates.append(path)
        for entry in candidates:
            if os.path.isfile(entry):
                return entry
        return None

    def open_radio_in_vlc(self):
        url = self._radio_last_url or str(self.station_combo.currentData() or "")
        if not url.startswith(("https://", "http://")):
            self._set_radio_status("Aucun flux HTTP(S) valide à ouvrir.", True)
            return
        exe = self._vlc_executable()
        if not exe:
            self._set_radio_status("VLC.exe est introuvable sur ce PC.", True)
            return
        # Qt lance l'exécutable VLC identifié sans interpréteur de commandes.
        # Les arguments restent séparés ; aucun texte d'URL n'est exécuté.
        process = QProcess(self)
        process.setProgram(exe)
        process.setArguments([url])
        clean_env = QProcessEnvironment.systemEnvironment()
        # Évite les conflits de DLL Qt et de modules de QGIS/OSGeo4W.
        for key in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH",
                    "PYTHONPATH", "PYTHONHOME", "VLC_PLUGIN_PATH"):
            clean_env.remove(key)
        process.setProcessEnvironment(clean_env)
        try:
            result = process.startDetached()
            started = bool(result[0] if isinstance(result, tuple) else result)
            if not started:
                self._set_radio_status("Impossible de lancer VLC (échec du processus Qt).", True)
                return
            self._set_radio_status("Flux ouvert dans VLC (fenêtre externe).")
        except (OSError, RuntimeError) as exc:
            self._set_radio_status("Impossible de lancer VLC : {}".format(exc), True)

    def test_radio_sound(self):
        if not self.player:
            self._set_radio_status("Lecteur audio indisponible : installe VLC 64 bits.", True)
            return
        path = os.path.join(os.path.dirname(__file__), "test_son.wav")
        self._radio_session += 1
        self._radio_retry_pending = False
        if self._radio_relay:
            self._radio_relay._cancel_active()
        self.play_source("local", path, "radio")
        self.radio_play_btn.setText("▶ Écouter")
        self._set_radio_status("Test audio local : un bip discret doit être audible.")
        self.radio_detail.setText("Test sonore local, sans connexion Internet · {}".format(
            self.engine.upper()))

    def open_rtl_site(self):
        # Ouvrir dans le navigateur habituel, même si Qt WebEngine est absent.
        QDesktopServices.openUrl(QUrl("https://www.rtl.fr/direct"))

    def add_station(self):
        name = self.custom_name.text().strip()
        stream = self.custom_stream.text().strip()
        if not name or not stream.startswith(("http://", "https://")):
            self._set_radio_status("Indique un nom et un lien de flux HTTP(S) valide.", True)
            return
        if len(name) > 70 or len(stream) > 2048:
            self._set_radio_status("Nom ou adresse trop long.", True)
            return
        if name.casefold() in (n.casefold() for n, _ in self.radio_presets):
            self._set_radio_status("Une station de ce nom existe déjà.", True)
            return
        self.radio_presets.append((name, stream))
        self._save_stations()
        self._refresh_radios()
        self.station_combo.setCurrentIndex(self.station_combo.findText(name))
        self.custom_name.clear()
        self.custom_stream.clear()
        self._set_radio_status("Station ajoutée.")

    def remove_station(self):
        ix = self.station_combo.currentIndex()
        if ix < len(DEFAULT_RADIOS):
            self._set_radio_status("Les stations intégrées ne peuvent pas être supprimées.")
            return
        if ix < 0:
            return
        name = self.station_combo.currentText()
        del self.radio_presets[ix]
        self._save_stations()
        self._refresh_radios()
        self._set_radio_status("Station « {} » supprimée.".format(name))

    def _save_stations(self):
        self.prefs.setValue(SETTINGS + "user_radios", json.dumps(self.radio_presets[len(DEFAULT_RADIOS):], ensure_ascii=False))

    # ------ NOTES ------
    def _create_notes_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(8)
        lay.addWidget(title("Bloc-notes"))
        lay.addWidget(label("Une idée, une requête SQL ou un lien utile ? Ces notes restent sur ce PC.", True))
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Mes notes…")
        self.notes.setAcceptRichText(False)
        self.notes.setPlainText(str(self.prefs.value(SETTINGS + "notes", "") or ""))
        self.notes.textChanged.connect(self._notes_timer.start)
        lay.addWidget(self.notes, 1)
        row = QHBoxLayout()
        row.addWidget(label("Sauvegarde automatique", True))
        row.addStretch(1)
        row.addWidget(make_button("Copier", self._copy_notes))
        row.addWidget(make_button("Vider", self._clear_notes))
        lay.addLayout(row)
        self.tabs.addTab(page, "Notes")

    def _save_notes(self):
        self.prefs.setValue(SETTINGS + "notes", self.notes.toPlainText())

    def _copy_notes(self):
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.clipboard().setText(self.notes.toPlainText())

    def _clear_notes(self):
        if QMessageBox.question(self, "Effacer les notes", "Effacer toutes les notes enregistrées ?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.notes.clear()
            self._save_notes()

    # ------ OPTIONS / CYCLE DE VIE ------
    def _tab_changed(self, index):
        self.prefs.setValue(SETTINGS + "tab", int(index))
        if index == 1:
            self._initialize_web()

    def _settings_dialog(self):
        message = ("MEDIA HUB 1.3.2 — QGIS 3.44\n"
                   "Auteur : JulienH77  |  Licence : MIT\n"
                   "Projet : github.com/JulienH77/qgis-media-hub\n\n"
                   "VIDÉO / RADIO\nMoteur : {}\n{}\n\n"
                   "NAVIGATEUR\n{}\n\n"
                   "Volume > 100 % : réservé au moteur VLC.\n"
                   "Si YouTube refuse la lecture, utilise le bouton ↗ pour ouvrir Firefox.\n"
                   "Les stations et notes sont enregistrées localement dans QSettings.")
        browser = "Qt WebEngine opérationnel" if self.web else (
            "Qt WebEngine non encore ouvert" if not self._web_initialized else
            "Qt WebEngine indisponible (OSGeo4W : python3-pyqtwebengine)")
        QMessageBox.information(self, "Media Hub — Diagnostic",
                                message.format(self.engine.upper(), self.engine_detail, browser))

    def shutdown(self):
        if self._radio_relay:
            self._radio_relay.shutdown()
            self._radio_relay = None
        self._notes_timer.stop()
        self._save_notes()
        self._web_restore()
        if self._popup:
            # Au déchargement, pas de réassociation asynchrone à un lecteur
            # qui sera détruit quelques lignes plus bas.
            popup = self._popup
            self._popup = None
            popup._returning = True
            self.active_canvas.hide()
            self.active_canvas.setParent(self.video_holder)
            self.video_holder_layout.addWidget(self.active_canvas)
            popup.close()
        if self.player:
            self.player.stop()
            if self.engine == "vlc":
                self.player.close()
            self.player = None
        if self.web:
            self.web.stop()
            self.web.setParent(None)
            self.web.deleteLater()
            self.web = None
