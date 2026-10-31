# -*- coding: utf-8 -*-
"""Interface claire pour QGIS 3.44 : vidéo, WebEngine, radio, notes.

Le navigateur et les moteurs multimédias sont chargés à la demande : l'absence
 d'un module optionnel ne doit jamais empêcher le plugin de démarrer.
"""
import importlib
import json
import os
import shutil
import time
from pathlib import Path
from urllib.parse import quote_plus, urlparse, urlencode

from qgis.PyQt.QtCore import Qt, QEvent, QProcess, QProcessEnvironment, QSettings, QTimer, QUrl, QSize, QSignalBlocker
from qgis.PyQt.QtGui import QDesktopServices, QKeySequence, QIcon, QPixmap, QPainter, QColor, QFont
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDockWidget, QDoubleSpinBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QShortcut,
    QSizePolicy, QSlider, QTabWidget, QTextEdit, QScrollArea, QGridLayout,
    QApplication, QToolButton, QVBoxLayout, QWidget, QDialog, QDialogButtonBox,
    QKeySequenceEdit, QFormLayout,
)

from .vlc_backend import VLCBackend, QMediaPlayer, find_vlc
from .i18n import tr_ui, language
from .ui_localize import apply_localization
from .radio_catalog import (COUNTRIES, FRANCE_FEATURED, parse_directory_stations,
                            normalize_saved_stations_v2, stations_for_country,
                            COUNTRIES_EN, valid_stream_url)

SETTINGS = "qgis_media_hub/"
# Flux publies par les annuaires de radios (oct. 2026). Des serveurs peuvent
# etre injoignables depuis les reseaux professionnels : aucune garantie reseau.
RTL_STREAM = "https://icecast.rtl.fr/rtl-1-44-128"
RADIO_ALTERNATIVES = {
    "RTL": [
        RTL_STREAM,
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
    "RMC": ["https://audio.bfmtv.com/rmcradio_128.mp3"],
    "Franceinfo": [
        # Original user-provided high-quality AAC URL (HTTP may redirect).
        "http://direct.franceinfo.fr/live/franceinfo-hifi.aac",
        "https://icecast.radiofrance.fr/franceinfo-hifi.aac",
        "https://icecast.radiofrance.fr/franceinfo-midfi.mp3",
        "http://direct.franceinfo.fr/live/franceinfo-midfi.mp3",
    ],
    "Europe 1": [
        "https://stream.europe1.fr/europe1.aac",
        "https://stream.europe1.fr/europe1.mp3",
    ],
    "NRJ": [
        "https://streaming.nrjaudio.fm/oumvmk8fnozc?origine=fluxradios",
    ],
    "Nostalgie": [
        "https://streaming.nrjaudio.fm/oug7girb92oc?origine=fluxradios",
    ],
    "Chérie FM": [
        "https://streaming.nrjaudio.fm/ouuku85n3nje?origine=fluxradios",
    ],
    "RTL2": [
        "https://icecast.rtl2.fr/rtl2-1-44-128",
        "http://icecast.rtl2.fr/rtl2-1-44-128",
    ],
    "France Culture": [
        "https://icecast.radiofrance.fr/franceculture-midfi.mp3",
        "http://direct.franceculture.fr/live/franceculture-midfi.mp3",
    ],
    "France Musique": [
        "https://icecast.radiofrance.fr/francemusique-midfi.mp3",
    ],
    "RFM": [
        "https://stream.rfm.fr/rfm.aac",
        "https://stream.rfm.fr/rfm.mp3",
    ],
    "Skyrock": [
        "http://icecast.skyrock.net/s/natio_mp3_128k",
        "http://icecast.skyrock.net/s/natio_aac_128k",
    ],
    "Fun Radio": [
        "https://icecast.funradio.fr/fun-1-44-128",
        "http://icecast.funradio.fr/fun-1-44-128",
    ],
}
DEFAULT_RADIOS = [(name, sources[0]) for name, sources in RADIO_ALTERNATIVES.items()]
RADIO_ATTEMPT_TIMEOUT_MS = 16000

# The keyboard layout is editable from Settings > Keyboard shortcuts.
# Shortcuts are active only inside the Video tab or the floating player.
DEFAULT_VIDEO_SHORTCUTS = {
    "toggle": ("Lecture / pause", "Space"),
    "back": ("Reculer de 10 secondes", "Left"),
    "forward": ("Avancer de 10 secondes", "Right"),
    "volume_up": ("Augmenter le volume", "Up"),
    "volume_down": ("Diminuer le volume", "Down"),
    "speed_normal": ("Vitesse ×1,0", "S"),
    "speed_down": ("Ralentir de ×0,1", "Q"),
    "speed_up": ("Accélérer de ×0,1", "D"),
    "toggle_controls": ("Afficher/masquer les commandes du PiP", "H"),
}


def normalize_shortcut(sequence):
    """Normalize a Qt keyboard sequence for matching and collision detection."""
    return QKeySequence(sequence).toString(QKeySequence.SequenceFormat.PortableText)


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


def media_slider_css(dark=False, compact=False):
    """Flat VLC-inspired track: the filled section reflects the current value."""
    groove = "#4c5663" if dark else "#dce3e9"
    active = "#68a5d8" if dark else "#287fbd"
    handle = "#eaf3fc" if dark else "#ffffff"
    diameter = 10 if compact else 12
    return (
        "QSlider::groove:horizontal {{ height: 4px; border-radius: 2px; "
        "background: {}; }} "
        "QSlider::sub-page:horizontal {{ background: {}; border-radius: 2px; }} "
        "QSlider::handle:horizontal {{ width: {}px; height: {}px; "
        "margin: -{}px 0; border-radius: {}px; border: 1px solid {}; "
        "background: {}; }}".format(
            groove, active, diameter, diameter,
            (diameter - 4) // 2, diameter // 2, active, handle))


def media_speed_css(dark=False):
    """Shared style for the QGIS dock and the PiP/fullscreen speed field."""
    return (
        "QDoubleSpinBox {{ background: {}; color: {}; border: 1px solid {}; "
        "border-radius: 5px; padding: 3px 7px; font-weight: 600; }}".format(
            "#2c3239" if dark else "#f5f8fa",
            "#f1f4f6" if dark else "#283642",
            "#566472" if dark else "#d1dce5"))


def configure_speed_spinbox(spinbox):
    """Exactly the same speed behaviour in the dock, PiP and fullscreen."""
    spinbox.setRange(0.1, 5.0)
    spinbox.setDecimals(1)
    spinbox.setSingleStep(0.1)
    spinbox.setSuffix("×")
    spinbox.setFixedWidth(72)
    spinbox.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
    spinbox.setToolTip("Vitesse de lecture, modifiable par pas de 0,1")


class FloatPlayer(QWidget):
    """PiP léger qui accueille la *même* surface vidéo, sans second lecteur."""

    def __init__(self, dock):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.dock = dock
        self.setWindowTitle("Media Hub — Vidéo flottante")
        self.setMinimumSize(375, 200)
        self.resize(520, 345)
        self.setObjectName("mediaHubFloatPlayer")
        self.setAutoFillBackground(True)
        self._controls_hidden = False
        self._dark_mode = False
        base = QVBoxLayout(self)
        base.setContentsMargins(4, 3, 4, 3)
        base.setSpacing(2)
        self.canvas_layout = QVBoxLayout()
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        base.addLayout(self.canvas_layout, 1)
        # Playback timeline shared with the dock's media player. A second Qt
        # slider is intentional: VLC continues to own ONE media instance.
        self._seek_pressed = False
        self.seek_container = QWidget(self)
        timeline = QHBoxLayout(self.seek_container)
        timeline.setContentsMargins(3, 0, 3, 0)
        timeline.setSpacing(5)
        self.elapsed_label = QLabel(time_label(dock.player.position()) if dock.player else "00:00")
        self.elapsed_label.setFixedWidth(43)
        self.elapsed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, max(0, dock.current_duration))
        self.seek_slider.setValue(min(max(0, dock.player.position()),
                                      dock.current_duration) if dock.player else 0)
        self.seek_slider.setEnabled(dock.current_duration > 0)
        self.seek_slider.setToolTip("Position de lecture (déplacer pour avancer ou reculer)")
        self.seek_slider.sliderPressed.connect(self._begin_seek)
        self.seek_slider.sliderReleased.connect(self._finish_seek)
        self.seek_slider.valueChanged.connect(self._preview_seek)
        timeline.addWidget(self.elapsed_label)
        timeline.addWidget(self.seek_slider, 1)
        self.total_label = QLabel(time_label(dock.current_duration))
        self.total_label.setFixedWidth(43)
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timeline.addWidget(self.total_label)
        self.seek_container.setMaximumHeight(23)
        base.addWidget(self.seek_container)
        # Commandes PiP : zones latérales de largeur identique. Le groupe
        # -10 / Lecture / +10 reste ainsi au centre GEOMETRIQUE de la fenêtre,
        # même quand celle-ci est redimensionnée.
        navigation = QGridLayout()
        navigation.setContentsMargins(0, 0, 0, 0)
        navigation.setHorizontalSpacing(0)
        navigation.setColumnMinimumWidth(0, 76)
        navigation.setColumnMinimumWidth(2, 76)
        # The two side columns grow equally: the playback cluster stays in
        # the exact geometric center even if the PiP window is resized.
        navigation.setColumnStretch(0, 1)
        navigation.setColumnStretch(1, 0)
        navigation.setColumnStretch(2, 1)

        self.close_button = make_button("↩ QGIS", self.return_to_dock,
                                        "Replacer la vidéo dans QGIS")
        self.close_button.setFixedSize(76, 26)
        self.close_button.setStyleSheet(self._secondary_button_style())
        navigation.addWidget(self.close_button, 0, 0, Qt.AlignmentFlag.AlignLeft)

        center_controls = QWidget(self)
        centered_row = QHBoxLayout(center_controls)
        centered_row.setContentsMargins(0, 0, 0, 0)
        centered_row.setSpacing(4)
        back = make_button("−10 s", lambda: dock.skip(-10000),
                           "Reculer de 10 secondes")
        back.setFixedSize(47, 26)
        back.setStyleSheet(self._secondary_button_style())
        centered_row.addWidget(back)
        self.play_button = make_button("Pause", dock.toggle_play,
                                       "Lecture / Pause (Espace)")
        self.play_button.setFixedSize(78, 26)
        self.play_button.setStyleSheet(
            "QPushButton { font-weight: 600; color: #223e57; background-color: #e8f1f9; "
            "border: 1px solid #a4c3df; border-radius: 5px; } "
            "QPushButton:hover { background-color: #d9eafb; } "
            "QPushButton:pressed { background-color: #c1daf2; }")
        centered_row.addWidget(self.play_button)
        forward = make_button("+10 s", lambda: dock.skip(10000),
                              "Avancer de 10 secondes")
        forward.setFixedSize(47, 26)
        forward.setStyleSheet(self._secondary_button_style())
        centered_row.addWidget(forward)
        navigation.addWidget(center_controls, 0, 1, Qt.AlignmentFlag.AlignHCenter)

        self.fullscreen_button = make_button("⛶", self.toggle_fullscreen,
                                             "Plein écran / retour")
        self.fullscreen_button.setFixedSize(36, 26)
        self.fullscreen_button.setStyleSheet(self._secondary_button_style())
        navigation.addWidget(self.fullscreen_button, 0, 2,
                             Qt.AlignmentFlag.AlignRight)
        self.navigation_container = QWidget(self)
        self.navigation_container.setLayout(navigation)
        self.navigation_container.setMaximumHeight(28)
        base.addWidget(self.navigation_container)

        # Secondary actions share ONE compact row. Unlike the old 3-row
        # toolbar, PiP and fullscreen reserve much more height for the film.
        # When playback controls are collapsed, only the theme and show
        # buttons remain visible, so the user is never locked out.
        secondary = QHBoxLayout()
        secondary.setContentsMargins(0, 0, 0, 0)
        secondary.setSpacing(3)
        self.sound_controls = QWidget(self)
        sound = QHBoxLayout(self.sound_controls)
        sound.setContentsMargins(0, 0, 0, 0)
        sound.setSpacing(3)
        self.sound_icon = make_button("🔊", dock._toggle_mute,
                                      "Couper ou rétablir le son")
        self.sound_icon.setFixedSize(26, 22)
        sound.addWidget(self.sound_icon)
        if dock.player and dock.player.isMuted():
            self.sound_icon.setText("🔇")
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, dock.volume_slider.maximum())
        self.volume.setFixedWidth(70)
        self.volume.setValue(dock.volume_slider.value())
        self.volume.setToolTip("Volume 0–200 % (moteur VLC)")
        self.volume.valueChanged.connect(dock.volume_slider.setValue)
        dock.volume_slider.valueChanged.connect(self.volume.setValue)
        sound.addWidget(self.volume)
        self.volume_value = QLabel("{}%".format(self.volume.value()))
        self.volume_value.setFixedWidth(34)
        self.volume_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.volume.valueChanged.connect(
            lambda value: self.volume_value.setText("{}%".format(value)))
        sound.addWidget(self.volume_value)
        # PiP and fullscreen use the SAME QDoubleSpinBox as the main QGIS
        # video panel, instead of an ordered dropdown list. Both directions
        # are connected to the existing dock speed field / VLC playback rate.
        self.speed_box = QDoubleSpinBox(self)
        self.speed_box.setAccessibleName("Vitesse de lecture")
        configure_speed_spinbox(self.speed_box)
        self.speed_box.setFixedHeight(23)
        self.speed_box.setValue(dock.speed.value())
        self.speed_box.valueChanged.connect(dock.speed.setValue)
        dock.speed.valueChanged.connect(self.speed_box.setValue)
        sound.addWidget(self.speed_box)
        secondary.addWidget(self.sound_controls)
        secondary.addStretch(1)
        self.theme_button = make_button("☾ Sombre", dock.toggle_dark_mode,
                                        "Basculer entre le thème clair et le thème sombre")
        self.theme_button.setFixedSize(68, 22)
        secondary.addWidget(self.theme_button)
        self.controls_button = make_button("⌄ Masquer", self.toggle_controls,
                                          "Masquer/afficher les commandes (H)")
        self.controls_button.setFixedSize(76, 22)
        secondary.addWidget(self.controls_button)
        self.sound_container = QWidget(self)
        self.sound_container.setLayout(secondary)
        self.sound_container.setMaximumHeight(26)
        base.addWidget(self.sound_container)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._shortcuts = []
        dock._register_video_shortcuts(self, self._shortcuts)
        self._esc = QShortcut(QKeySequence("Escape"), self)
        self._esc.activated.connect(self._on_escape)
        self._returning = False
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.apply_theme(dock._dark_mode)
        apply_localization(self)
        self.set_controls_hidden(str(dock.prefs.value(
            SETTINGS + "pip_controls_hidden", "false")).lower() in ("true", "1"))

    def _begin_seek(self):
        self._seek_pressed = True

    def _preview_seek(self, value):
        if self._seek_pressed:
            self.elapsed_label.setText(time_label(value))

    def _finish_seek(self):
        self._seek_pressed = False
        if (self.dock.player and self.dock.current_kind == "video"
                and self.dock.player.isSeekable()):
            self.dock.player.setPosition(self.seek_slider.value())
        elif self.dock.player:
            self.update_position(self.dock.player.position())

    def update_position(self, milliseconds):
        if not self._seek_pressed:
            self.seek_slider.setValue(max(0, min(self.seek_slider.maximum(), int(milliseconds))))
            self.elapsed_label.setText(time_label(milliseconds))

    def update_duration(self, milliseconds):
        duration = max(0, int(milliseconds))
        self.seek_slider.setRange(0, duration)
        self.seek_slider.setEnabled(duration > 0)
        self.total_label.setText(time_label(duration))

    def apply_theme(self, dark):
        """Theme only this floating window; QGIS' global appearance is untouched."""
        self._dark_mode = bool(dark)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor("#181b20" if dark else "#f8f9fb"))
        palette.setColor(palette.WindowText, QColor("#f2f4f7" if dark else "#26323d"))
        self.setPalette(palette)
        bg = "#242a32" if dark else "#f3f5f7"
        fg = "#f2f4f7" if dark else "#273742"
        edge = "#515b67" if dark else "#bfcbd3"
        over = "#35404a" if dark else "#e3edf5"
        button_css = (
            "QPushButton {{ color: {}; background-color: {}; border: 1px solid {}; "
            "border-radius: 4px; font-weight: 500; }} "
            "QPushButton:hover {{ background-color: {}; }}".format(fg, bg, edge, over))
        for widget in (self.close_button, self.fullscreen_button,
                       self.theme_button, self.controls_button):
            widget.setStyleSheet(button_css)
        for item in self.navigation_container.findChildren(QPushButton):
            if item is not self.play_button:
                item.setStyleSheet(button_css)
        self.play_button.setStyleSheet(
            "QPushButton {{ color: {}; background: {}; border: 1px solid {}; "
            "border-radius: 5px; font-weight: 600; }}".format(
                "#ffffff" if dark else "#223e57",
                "#31577b" if dark else "#e8f1f9",
                "#6f99bd" if dark else "#a4c3df"))
        self.setStyleSheet(
            "QWidget#mediaHubFloatPlayer {{ background: {}; color: {}; }} "
            "QLabel {{ color: {}; background: transparent; }} "
            "QDoubleSpinBox {{ color: {}; background: {}; border: 1px solid {}; }}".format(
                "#181b20" if dark else "#f8f9fb", fg, fg, fg, bg, edge))
        self.seek_slider.setStyleSheet(media_slider_css(dark))
        self.volume.setStyleSheet(media_slider_css(dark, compact=True))
        self.speed_box.setStyleSheet(media_speed_css(dark))
        self.sound_icon.setStyleSheet(button_css)
        # Keep explicit per-button CSS: on some Windows Qt styles it prevents
        # the +/-10-second buttons from appearing as black empty rectangles.
        theme_label = "☀ Clair" if dark else "☾ Sombre"
        self.theme_button.setProperty("mediahub_original_label", theme_label)
        self.theme_button.setText(tr_ui(theme_label))

    def set_controls_hidden(self, hidden):
        self._controls_hidden = bool(hidden)
        self.navigation_container.setVisible(not hidden)
        self.seek_container.setVisible(not hidden)
        self.sound_controls.setVisible(not hidden)
        toggle_label = "⌃ Afficher" if hidden else "⌄ Masquer"
        self.controls_button.setProperty("mediahub_original_label", toggle_label)
        self.controls_button.setText(tr_ui(toggle_label))
        self.controls_button.setToolTip("Afficher les commandes (H)" if hidden
                                        else "Masquer les commandes (H)")
        self.dock.prefs.setValue(SETTINGS + "pip_controls_hidden", hidden)

    def toggle_controls(self):
        self.set_controls_hidden(not self._controls_hidden)

    @staticmethod
    def _secondary_button_style():
        """Visible on Windows regardless of native VLC surface paint/theme."""
        return (
            "QPushButton { color: #273742; background-color: #f3f5f7; "
            "border: 1px solid #bfcbd3; border-radius: 4px; "
            "font-weight: 500; } "
            "QPushButton:hover { background-color: #e3edf5; } "
            "QPushButton:pressed { background-color: #d2e2f0; }"
        )

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
        self._dark_mode = str(self.prefs.value(SETTINGS + "dark_mode", "false")).lower() in ("true", "1")
        self._seek_pressed = False
        self._directory_reply = None
        self._country_catalogs = {}
        self._country_homepages = {}
        self.user_radios = []
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
        self._station_tiles = []
        self._video_shortcuts = []
        self._shortcut_bindings = self._load_video_shortcut_settings()
        self._shortcut_enabled = str(self.prefs.value(
            SETTINGS + "keyboard_enabled", "true")).lower() in ("true", "1")
        self._video_folder = ""
        self._keyboard_filter_installed = False
        self._notes_timer = QTimer(self)
        self._notes_timer.setSingleShot(True)
        self._notes_timer.setInterval(650)
        self._notes_timer.timeout.connect(self._save_notes)

        body = QWidget(self)
        self.setWidget(body)
        body.setObjectName("mediaHubBody")
        self._body = body
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
        self.theme_btn = QToolButton()
        self.theme_btn.setToolTip("Mode sombre : thème sombre / clair de Media Hub")
        self.theme_btn.clicked.connect(self.toggle_dark_mode)
        head.addWidget(self.theme_btn)
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
        self._restore_video_folder()
        self._load_radio_presets()
        self._apply_theme()
        self._apply_language()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._keyboard_filter_installed = True
        saved_tab = int(self.prefs.value(SETTINGS + "tab", 0) or 0)
        self.tabs.setCurrentIndex(max(0, min(3, saved_tab)))
        if self.tabs.currentIndex() == 1:
            self._initialize_web()

    def toggle_dark_mode(self):
        self._dark_mode = not self._dark_mode
        self.prefs.setValue(SETTINGS + "dark_mode", self._dark_mode)
        self._apply_theme()

    def _apply_theme(self):
        """Light by default; dark mode remains scoped to Media Hub widgets."""
        dark = self._dark_mode
        self.theme_btn.setText("☀" if dark else "☾")
        self.theme_btn.setToolTip(tr_ui("Revenir au thème clair" if dark else "Activer le mode sombre"))
        if dark:
            self._body.setStyleSheet("""
                QWidget#mediaHubBody, QTabWidget::pane, QScrollArea,
                QScrollArea > QWidget, QWidget#radioContent {
                    background: #20242a; color: #edf0f3; }
                QLabel { color: #e4e8ed; }
                QTabBar::tab { background: #2c323a; color: #e9edf1;
                    padding: 6px 10px; border: 1px solid #525b67; }
                QTabBar::tab:selected { background: #3c4651; }
                QLineEdit, QComboBox, QTextEdit, QDoubleSpinBox, QKeySequenceEdit {
                    color: #f1f3f6; background: #2c3239;
                    border: 1px solid #65707c; border-radius: 3px; }
                QPushButton, QToolButton { color: #f1f4f6; background: #343d47;
                    border: 1px solid #56616e; padding: 4px; border-radius: 4px; }
                QPushButton:hover, QToolButton:hover { background: #45515f; }
                QCheckBox { color: #eef1f5; }
            """)
            self.video_placeholder.setStyleSheet(
                "background: #14171c; color: #d1d8df; border: 1px solid #414a54;")
            self.play_video_btn.setStyleSheet(
                "QPushButton { background: #31577b; color: white; font-weight: 600; "
                "border: 1px solid #7199bd; border-radius: 5px; }")
        else:
            self._body.setStyleSheet("")
            self.video_placeholder.setStyleSheet(
                "background: #eef1f4; color: #74818d; border: 1px solid #dce2e6;")
            self.play_video_btn.setStyleSheet(
                "QPushButton { font-weight: 600; background: #e8f1f9; "
                "border: 1px solid #a4c3df; border-radius: 5px; } "
                "QPushButton:hover { background: #d9eafb; }")
        for item in self._body.findChildren(QLabel):
            style = item.styleSheet()
            if "font-weight: 600; color: #35434e" in style or "font-weight: 600; color: #e4e8ed" in style:
                item.setStyleSheet("font-size: 14px; font-weight: 600; color: {};".format(
                    "#e4e8ed" if dark else "#35434e"))
            elif style in ("color: #6e7983; font-size: 11px;",
                           "color: #a8b5c2; font-size: 11px;"):
                item.setStyleSheet("color: {}; font-size: 11px;".format(
                    "#a8b5c2" if dark else "#6e7983"))
        self._style_radio_tiles()
        self._style_web_controls()
        self.seek.setStyleSheet(media_slider_css(dark))
        self.volume_slider.setStyleSheet(media_slider_css(dark))
        self.speed.setStyleSheet(media_speed_css(dark))
        if self._popup is not None:
            self._popup.apply_theme(dark)

    def _apply_language(self):
        """UI-only translations; never alter station names, streams or notes."""
        apply_localization(self._body)
        self._refresh_country_labels()
        if self._popup is not None:
            apply_localization(self._popup)
        self._style_radio_tiles()

    def _refresh_country_labels(self):
        selected = self.radio_country_combo.currentData()
        for combo in (self.radio_country_combo, self.custom_country):
            for index, (code, display) in enumerate(COUNTRIES):
                combo.setItemText(index,
                    COUNTRIES_EN.get(code, display) if language() == "en" else display)
        index = self.radio_country_combo.findData(selected)
        if index >= 0:
            blocker = QSignalBlocker(self.radio_country_combo)
            self.radio_country_combo.setCurrentIndex(index)
            del blocker

    def _style_radio_tiles(self):
        dark = self._dark_mode
        for tile in self._station_tiles:
            tile.setStyleSheet(
                "QToolButton#mediaHubStationTile {{ background: {}; border: 1px solid {}; "
                "border-radius: 5px; padding: 2px; }} "
                "QToolButton#mediaHubStationTile:hover {{ border-color: #89b4db; }} "
                "QToolButton#mediaHubStationTile:checked {{ border: 2px solid #3988c9; }}".format(
                    "#343b44" if dark else "#ffffff",
                    "#67727e" if dark else "#d8dfe5"))
        for cell in getattr(self, "_radio_cells", []):
            for caption in cell.findChildren(QLabel, "mediaHubStationCaption"):
                caption.setStyleSheet("color: {}; font-size: 11px; font-weight: 500; "
                                      "background: transparent;".format(
                                          "#e6ebef" if dark else "#334352"))

    # ------ VIDÉOS ------
    def _create_video_tab(self):
        page = QWidget()
        self.video_page = page
        lay = QVBoxLayout(page)
        lay.setContentsMargins(7, 12, 7, 9)
        lay.setSpacing(9)
        lay.addWidget(title("Mes vidéos"))
        lay.addWidget(label("Fichiers MP4, MKV, AVI… ou liens directs vers un média.", True))
        # Bibliothèque vidéo : après sélection d'un dossier, les fichiers
        # apparaissent dans cette liste sans rouvrir l'explorateur Windows.
        library_row = QHBoxLayout()
        library_row.setSpacing(5)
        self.video_folder_btn = make_button("Dossier…", self._choose_video_folder,
                                            "Choisir le dossier contenant tes vidéos")
        self.video_folder_btn.setFixedWidth(77)
        library_row.addWidget(self.video_folder_btn)
        self.video_library_combo = QComboBox()
        self.video_library_combo.setMinimumContentsLength(12)
        self.video_library_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.video_library_combo.addItem("Choisir un dossier…", None)
        self.video_library_combo.setEnabled(False)
        self.video_library_combo.setToolTip("Sélectionne un dossier pour afficher ses vidéos")
        self.video_library_combo.currentIndexChanged.connect(self._play_library_choice)
        library_row.addWidget(self.video_library_combo, 1)
        refresh_button = make_button("↻", lambda: self._refresh_video_library(),
                                     "Actualiser les vidéos du dossier")
        refresh_button.setFixedSize(30, 28)
        library_row.addWidget(refresh_button)
        lay.addLayout(library_row)
        self.library_info = label("Aucun dossier vidéo sélectionné", True)
        self.library_info.setWordWrap(False)
        lay.addWidget(self.library_info)
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
        self.vlc_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
        controls.setSpacing(5)
        rewind_button = make_button("−10 s", lambda: self.skip(-10000))
        rewind_button.setFixedWidth(62)
        controls.addWidget(rewind_button)
        self.play_video_btn = make_button("▶ Lecture", self.toggle_play)
        self.play_video_btn.setMinimumSize(108, 38)
        self.play_video_btn.setStyleSheet(
            "QPushButton { font-weight: 600; background: #e8f1f9; "
            "border: 1px solid #a4c3df; border-radius: 5px; } "
            "QPushButton:hover { background: #d9eafb; } "
            "QPushButton:pressed { background: #c1daf2; }")
        controls.addWidget(self.play_video_btn)
        forward_button = make_button("+10 s", lambda: self.skip(10000))
        forward_button.setFixedWidth(62)
        controls.addWidget(forward_button)
        controls.addStretch(1)
        controls.addWidget(label("Vitesse"))
        self.speed = QDoubleSpinBox()
        configure_speed_spinbox(self.speed)
        self.speed.setValue(float(self.prefs.value(SETTINGS + "speed", 1.0) or 1.0))
        self.speed.valueChanged.connect(self._set_speed)
        controls.addWidget(self.speed)
        lay.addLayout(controls)

        tracks_row = QHBoxLayout()
        tracks_row.addWidget(label("Audio"))
        self.audio_tracks_combo = QComboBox()
        self.audio_tracks_combo.setMinimumWidth(85)
        self.audio_tracks_combo.setToolTip("Choisir une piste audio incluse dans le fichier")
        self.audio_tracks_combo.currentIndexChanged.connect(self._choose_audio_track)
        tracks_row.addWidget(self.audio_tracks_combo, 1)
        tracks_row.addWidget(label("Sous-titres"))
        self.subtitle_tracks_combo = QComboBox()
        self.subtitle_tracks_combo.setMinimumWidth(85)
        self.subtitle_tracks_combo.setToolTip("Activer ou désactiver une piste de sous-titres")
        self.subtitle_tracks_combo.currentIndexChanged.connect(self._choose_subtitle_track)
        tracks_row.addWidget(self.subtitle_tracks_combo, 1)
        tracks_row.addWidget(make_button("SRT…", self._add_subtitle_file,
                                         "Charger des sous-titres externes .srt, .ass ou .vtt"))
        lay.addLayout(tracks_row)
        self._reset_tracks()
        lay.addWidget(label("Raccourcis (vidéo et PiP) : Espace lecture/pause · ←/→ ±10 s · ↑/↓ son · S vitesse 1× · Q/D ±0,1×", True))
        # Les raccourcis s’appliquent à tout l’onglet vidéo, et pas seulement
        # au cadre natif VLC (qui ne reçoit pas forcément le focus Qt).
        self._register_video_shortcuts(self.video_page, self._video_shortcuts)
        self.vlc_canvas.installEventFilter(self)

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
                self.player.tracksChanged.connect(self._tracks_changed)
                self.engine_detail = "VLC : " + dll_path
            except (Exception,) as exc:
                self.engine_detail = "VLC détecté mais inutilisable : {}".format(exc)
        if self.player is None:
            try:
                try:
                    from qgis.PyQt.QtMultimedia import QMediaContent, QMediaPlayer as QtMedia
                    from qgis.PyQt.QtMultimediaWidgets import QVideoWidget
                except ImportError:
                    # Some QGIS installations do not expose optional Qt modules
                    # through qgis.PyQt. Keep a native-binding fallback rather
                    # than disabling the video decoder on those installations.
                    from qgis.PyQt.QtCore import PYQT_VERSION_STR
                    qt_binding = "PyQt6" if PYQT_VERSION_STR.startswith("6.") else "PyQt5"
                    multimedia = importlib.import_module(qt_binding + ".QtMultimedia")
                    multimedia_widgets = importlib.import_module(qt_binding + ".QtMultimediaWidgets")
                    QMediaContent = multimedia.QMediaContent  # Qt5 fallback only
                    QtMedia = multimedia.QMediaPlayer
                    QVideoWidget = multimedia_widgets.QVideoWidget
                self.qt_media_content = QMediaContent
                self.qt_canvas = QVideoWidget(self.video_holder)
                self.qt_canvas.installEventFilter(self)
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

    def _load_video_shortcut_settings(self):
        """Ignore malformed preferences, keep safe default bindings."""
        raw = self.prefs.value(SETTINGS + "keyboard_shortcuts", "{}")
        try:
            values = json.loads(raw) if isinstance(raw, str) else {}
        except (TypeError, ValueError):
            values = {}
        if not isinstance(values, dict):
            values = {}
        bindings = {}
        for action, (_, default) in DEFAULT_VIDEO_SHORTCUTS.items():
            value = values.get(action, default)
            if not isinstance(value, str) or not value or len(value) > 60:
                value = default
            bindings[action] = normalize_shortcut(value) or default
        return bindings

    def _video_actions(self):
        """Callbacks shared by Qt shortcuts and the focus-aware event filter."""
        return {
            "toggle": self.toggle_play,
            "back": lambda: self.skip(-10000),
            "forward": lambda: self.skip(10000),
            "volume_up": lambda: self._volume_step(5),
            "volume_down": lambda: self._volume_step(-5),
            "speed_normal": lambda: self.speed.setValue(1.0),
            "speed_down": lambda: self._speed_step(-0.1),
            "speed_up": lambda: self._speed_step(0.1),
            "toggle_controls": lambda: self._popup.toggle_controls() if self._popup else None,
        }

    def _register_video_shortcuts(self, target, keep):
        """Local Qt shortcuts; never steal keys from the QGIS map canvas."""
        if not self._shortcut_enabled:
            return
        for action, callback in self._video_actions().items():
            sequence = self._shortcut_bindings.get(action, "")
            if not sequence:
                continue
            shortcut = QShortcut(QKeySequence(sequence), target)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut if isinstance(target, FloatPlayer)
                                else Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            keep.append(shortcut)

    def _rebuild_video_shortcuts(self):
        targets = [(self.video_page, self._video_shortcuts)]
        if self._popup is not None:
            targets.append((self._popup, self._popup._shortcuts))
        for target, shortcuts in targets:
            for item in shortcuts:
                item.setEnabled(False)
                item.deleteLater()
            shortcuts.clear()
            self._register_video_shortcuts(target, shortcuts)

    def _video_key_action(self, key, modifiers):
        """Use the same editable bindings when Qt routes a key to native VLC."""
        if not self._shortcut_enabled:
            return None
        code = int(key) | int(modifiers)
        incoming = QKeySequence(code).toString(QKeySequence.SequenceFormat.PortableText)
        for action, shortcut in self._shortcut_bindings.items():
            if incoming == shortcut:
                return self._video_actions()[action]
        return None

    def eventFilter(self, watched, event):  # noqa: N802
        """Handle Qt key focus, including when libVLC renders in a native widget.

        Active only when focus is in the video tab or the standalone PiP.
        Never intercept typing in a text field or speed spinbox, and never
        change QGIS map-canvas shortcuts while QGIS map has keyboard focus.
        """
        event_type = event.type()
        if (event_type == QEvent.Type.Resize and hasattr(self, "radio_scroll")
                and watched is self.radio_scroll.viewport()):
            QTimer.singleShot(0, self._layout_radio_tiles)
        if event_type == QEvent.Type.MouseButtonPress and watched in (self.vlc_canvas, self.qt_canvas):
            watched.setFocus(Qt.FocusReason.MouseFocusReason)
        if event_type != QEvent.Type.KeyPress or event.isAutoRepeat():
            return super().eventFilter(watched, event)
        app = QApplication.instance()
        focus = app.focusWidget() if app is not None else None
        if focus is None:
            return super().eventFilter(watched, event)
        # Ctrl+C etc. and normal text editing must work in every tab.
        if isinstance(focus, (QLineEdit, QTextEdit, QDoubleSpinBox, QComboBox)):
            return super().eventFilter(watched, event)
        in_popup = (self._popup is not None and self._popup.isVisible() and
                    (focus is self._popup or self._popup.isAncestorOf(focus)))
        in_dock = (self._popup is None and self.tabs.currentIndex() == 0 and
                   (focus is self.video_page or self.video_page.isAncestorOf(focus)))
        if not (in_popup or in_dock):
            return super().eventFilter(watched, event)
        action = self._video_key_action(event.key(), event.modifiers())
        if action is not None:
            action()
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _volume_step(self, delta):
        self.volume_slider.setValue(max(0, min(200, self.volume_slider.value() + delta)))

    def _speed_step(self, delta):
        # Arrondi au dixième pour éviter les flottants 1.3000000000000003.
        tenths = round(self.speed.value() * 10) + round(delta * 10)
        self.speed.setValue(max(1, min(50, tenths)) / 10.0)

    def _reset_tracks(self):
        for combo, message in ((self.audio_tracks_combo, "Audio : chargement…"),
                               (self.subtitle_tracks_combo, "Sous-titres : chargement…")):
            with QSignalBlocker(combo):
                combo.clear()
                combo.addItem(message, -9999)
                combo.setEnabled(False)

    def _tracks_changed(self, audio, subtitles, selected_audio, selected_sub):
        if self.current_kind != "video":
            return
        self._fill_tracks(self.audio_tracks_combo, audio, selected_audio, "Audio indisponible")
        if not any(t[0] == -1 for t in subtitles):
            subtitles = [(-1, "Désactivés")] + list(subtitles)
        self._fill_tracks(self.subtitle_tracks_combo, subtitles, selected_sub, "Aucun sous-titre")

    @staticmethod
    def _fill_tracks(combo, tracks, current, empty):
        with QSignalBlocker(combo):
            combo.clear()
            if not tracks:
                combo.addItem(empty, -9999)
                combo.setEnabled(False)
                return
            for track_id, name in tracks:
                combo.addItem(name, track_id)
            ix = combo.findData(current)
            combo.setCurrentIndex(ix if ix >= 0 else 0)
            combo.setEnabled(len(tracks) > 1)

    def _add_subtitle_file(self):
        if not self.player or self.engine != "vlc" or self.current_kind != "video":
            self._set_video_status("Ouvre une vidéo avec VLC avant de charger un fichier SRT.", True)
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir des sous-titres", str(Path.home()),
            "Sous-titres (*.srt *.ass *.ssa *.vtt *.sub);;Tous les fichiers (*)")
        if not path:
            return
        if self.player.add_external_subtitle(path):
            self._set_video_status("Sous-titres ajoutés : {}".format(os.path.basename(path)))
            QTimer.singleShot(800, self.player._refresh_tracks)
        else:
            self._set_video_status("VLC n'a pas pu charger ce fichier de sous-titres.", True)

    def _choose_audio_track(self, unused):
        if self.engine == "vlc" and self.current_kind == "video" and self.player:
            track = self.audio_tracks_combo.currentData()
            if track is not None and int(track) != -9999:
                if not self.player.set_audio_track(int(track)):
                    self._set_video_status("Impossible d'activer cette piste audio.", True)

    def _choose_subtitle_track(self, unused):
        if self.engine == "vlc" and self.current_kind == "video" and self.player:
            track = self.subtitle_tracks_combo.currentData()
            if track is not None and int(track) != -9999:
                if not self.player.set_subtitle_track(int(track)):
                    self._set_video_status("Impossible d'activer ces sous-titres.", True)

    @staticmethod
    def _list_videos(directory):
        """Return direct child video files only, sorted case-insensitively.

        No recursive scanning: network folders with thousands of subfolders
        must not freeze QGIS. The refresh button re-reads the directory.
        """
        extensions = {
            ".mp4", ".m4v", ".mkv", ".avi", ".mov", ".wmv",
            ".webm", ".mpg", ".mpeg", ".m2ts", ".ts", ".flv",
            ".ogv", ".3gp",
        }
        paths = []
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_file() and os.path.splitext(entry.name)[1].lower() in extensions:
                    paths.append(entry.path)
        return sorted(paths, key=lambda path: os.path.basename(path).casefold())

    def _restore_video_folder(self):
        directory = str(self.prefs.value(SETTINGS + "video_folder", "") or "")
        if directory and os.path.isdir(directory):
            self._set_video_folder(directory)
        elif directory:
            self.library_info.setText("Dossier précédent introuvable · choisis-en un autre")
            self.library_info.setToolTip(directory)

    def _choose_video_folder(self):
        start = (self._video_folder or
                 str(self.prefs.value(SETTINGS + "last_directory", "") or "") or
                 os.path.expanduser("~"))
        chosen = QFileDialog.getExistingDirectory(self, "Choisir un dossier de vidéos", start)
        if chosen:
            self._set_video_folder(chosen)

    def _set_video_folder(self, directory, selected_path=None):
        directory = os.path.normpath(os.path.abspath(directory))
        self._video_folder = directory
        self.prefs.setValue(SETTINGS + "video_folder", directory)
        self.prefs.setValue(SETTINGS + "last_directory", directory)
        self._refresh_video_library(selected_path=selected_path)

    def _refresh_video_library(self, selected_path=None):
        directory = self._video_folder
        if not directory:
            return
        if not os.path.isdir(directory):
            with QSignalBlocker(self.video_library_combo):
                self.video_library_combo.clear()
                self.video_library_combo.addItem("Dossier inaccessible", None)
                self.video_library_combo.setEnabled(False)
            self.library_info.setText("Dossier inaccessible · choisis-en un autre")
            self.library_info.setToolTip(directory)
            return
        if selected_path is None and self.video_library_combo.currentIndex() > 0:
            selected_path = self.video_library_combo.currentData()
        try:
            videos = self._list_videos(directory)
        except OSError as exc:
            self.library_info.setText("Lecture du dossier impossible")
            self.library_info.setToolTip(str(exc))
            return
        with QSignalBlocker(self.video_library_combo):
            self.video_library_combo.clear()
            self.video_library_combo.addItem("Choisir une vidéo…", None)
            for path in videos:
                self.video_library_combo.addItem(os.path.basename(path), path)
            if selected_path:
                key = os.path.normcase(os.path.normpath(selected_path))
                for index, path in enumerate(videos, start=1):
                    if os.path.normcase(os.path.normpath(path)) == key:
                        self.video_library_combo.setCurrentIndex(index)
                        break
            self.video_library_combo.setEnabled(bool(videos))
        count = len(videos)
        short_dir = os.path.basename(directory) or directory
        self.library_info.setText("{} · {} vidéo{}".format(
            short_dir, count, "s" if count != 1 else ""))
        self.library_info.setToolTip(directory)
        self.video_library_combo.setToolTip(directory)

    def _play_library_choice(self, index):
        if index <= 0:
            return
        source = self.video_library_combo.itemData(index)
        if not source:
            return
        if not os.path.isfile(source):
            self._set_video_status("Fichier supprimé ou déplacé. Actualise le dossier.", True)
            return
        self.video_url.setText(source)
        self._play_from_text()

    def _sync_library_choice(self, source):
        if not self._video_folder:
            return
        directory = os.path.normcase(os.path.normpath(os.path.dirname(source)))
        if directory != os.path.normcase(os.path.normpath(self._video_folder)):
            return
        with QSignalBlocker(self.video_library_combo):
            for i in range(1, self.video_library_combo.count()):
                path = self.video_library_combo.itemData(i)
                if path and os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(source)):
                    self.video_library_combo.setCurrentIndex(i)
                    return

    def _open_file(self):
        recent = str(self.prefs.value(SETTINGS + "last_directory", str(Path.home())) or str(Path.home()))
        if not os.path.isdir(recent):
            recent = str(Path.home())
        source, _ = QFileDialog.getOpenFileName(self, "Choisir une vidéo", recent,
                         "Vidéos (*.mp4 *.mkv *.avi *.mov *.webm *.m4v *.wmv *.mpg *.mpeg *.ts);;Tous les fichiers (*)")
        if source:
            self.prefs.setValue(SETTINGS + "last_directory", os.path.dirname(source))
            self._set_video_folder(os.path.dirname(source), selected_path=source)
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
        if kind == "local":
            self._sync_library_choice(source)
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
        self._reset_tracks()
        if mode == "video" and self.engine != "vlc":
            self._set_video_status("Pistes audio et sous-titres : VLC requis.")
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
            self.active_canvas.setFocus(Qt.FocusReason.OtherFocusReason)
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
        self.video_status.setText(tr_ui(text))
        self.video_status.setStyleSheet("color: #ad3838;" if error else "color: #71808a; font-size: 11px;")
        self.video_status.setToolTip(tr_ui(text))

    def _set_radio_status(self, text, error=False):
        self.radio_status.setText(tr_ui(text))
        self.radio_status.setStyleSheet("color: #ad3838;" if error else "color: #71808a; font-size: 11px;")
        self.radio_status.setToolTip(tr_ui(text))

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
        if self._popup:
            self._popup.update_position(ms)
        if not self._seek_pressed:
            self.seek.setValue(max(0, min(self.seek.maximum(), int(ms))))

    def _duration_changed(self, ms):
        if self.current_kind != "video":
            return
        self.current_duration = max(0, int(ms))
        if self._popup:
            self._popup.update_duration(self.current_duration)
        self.seek.setRange(0, self.current_duration)
        self.total.setText(time_label(self.current_duration))

    def _state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.loaded = True
        self.play_video_btn.setText(tr_ui("⏸ Pause" if state == QMediaPlayer.PlayingState else "▶ Lecture"))
        self.radio_play_btn.setText(tr_ui("⏸ Pause" if state == QMediaPlayer.PlayingState and self.current_kind == "radio" else "▶ Reprendre"))
        if self._popup:
            self._popup.play_button.setText(tr_ui("Pause" if state == QMediaPlayer.PlayingState else "Lecture"))
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
            if self._popup:
                self._popup.sound_icon.setText("🔇" if now else "🔊")

    def _transition_canvas(self, target_layout, new_parent):
        if not self.player:
            return
        was_playing = self.player.state() == QMediaPlayer.PlayingState
        was_paused = self.player.state() == QMediaPlayer.PausedState
        position = self.player.position()
        selected_audio = self.player.audio_track() if self.engine == "vlc" else -1
        selected_sub = self.player.subtitle_track() if self.engine == "vlc" else -1
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
                    QTimer.singleShot(700, lambda: self._restore_position(
                        position, was_paused, selected_audio, selected_sub))
            elif self.engine == "qt":
                self.player.setVideoOutput(self.active_canvas)
            self._moving = False
        QTimer.singleShot(180, reconnect)

    def _restore_position(self, position, paused, selected_audio=-1, selected_sub=-1):
        if not self.player or self.current_kind != "video":
            return
        if position > 0 and self.player.isSeekable():
            self.player.setPosition(position)
        if self.engine == "vlc":
            if selected_audio >= 0:
                self.player.set_audio_track(selected_audio)
            self.player.set_subtitle_track(selected_sub)
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
        self._popup.activateWindow()
        self.video_placeholder.setText("Vidéo dans la mini-fenêtre. Clique sur « QGIS » pour la récupérer.")
        self.video_placeholder.show()
        self._transition_canvas(self._popup.canvas_layout, self._popup)
        QTimer.singleShot(350, lambda: self.active_canvas.setFocus(
            Qt.FocusReason.OtherFocusReason) if self._popup is not None else None)

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
        """Minimal, adaptive web toolbar using Qt-native controls."""
        self.browser_page = QWidget()
        self.browser_page.setObjectName("mediaHubWebPage")
        lay = QVBoxLayout(self.browser_page)
        lay.setContentsMargins(7, 9, 7, 7)
        lay.setSpacing(8)

        heading = QHBoxLayout()
        heading.setSpacing(6)
        heading.addWidget(title("Navigateur"))
        heading.addStretch(1)
        self.web_mode_badge = QLabel("WEB")
        self.web_mode_badge.setObjectName("webModeBadge")
        heading.addWidget(self.web_mode_badge)
        lay.addLayout(heading)

        self.web_toolbar = QFrame(self.browser_page)
        self.web_toolbar.setObjectName("mediaHubWebToolbar")
        actions = QHBoxLayout(self.web_toolbar)
        actions.setContentsMargins(5, 5, 5, 5)
        actions.setSpacing(4)
        self.back_btn = make_button("‹", self._web_back, "Page précédente")
        self.next_btn = make_button("›", self._web_forward, "Page suivante")
        self.reload_btn = make_button("↻", self._web_reload, "Actualiser")
        for btn in (self.back_btn, self.next_btn, self.reload_btn):
            btn.setObjectName("mediaHubWebNav")
            btn.setFixedSize(27, 28)
            actions.addWidget(btn)
        self.address = QLineEdit()
        self.address.setObjectName("mediaHubAddress")
        self.address.setMinimumWidth(70)
        self.address.setPlaceholderText("Rechercher ou saisir une adresse…")
        self.address.setClearButtonEnabled(True)
        self.address.returnPressed.connect(self._open_address)
        actions.addWidget(self.address, 1)
        self.go_btn = make_button("→", self._open_address, "Ouvrir l'adresse")
        self.go_btn.setObjectName("mediaHubWebGo")
        self.go_btn.setFixedSize(29, 28)
        actions.addWidget(self.go_btn)
        lay.addWidget(self.web_toolbar)

        shortcuts = QHBoxLayout()
        shortcuts.setSpacing(5)
        self.web_quicklinks = []
        for text, target in (
                ("▶ YouTube", "https://www.youtube.com/"),
                ("⌕ Recherche", "https://www.google.com/"),
                ("QGIS", "https://docs.qgis.org/3.44/fr/docs/")):
            btn = make_button(text, lambda checked=False, url=target: self._navigate(url))
            btn.setObjectName("mediaHubWebQuicklink")
            btn.setFixedHeight(28)
            shortcuts.addWidget(btn)
            self.web_quicklinks.append(btn)
        shortcuts.addStretch(1)
        self.web_open_external = make_button("↗", self._web_external,
                                              "Ouvrir cette page dans le navigateur normal")
        self.web_open_external.setObjectName("mediaHubWebNav")
        self.web_open_external.setFixedSize(29, 28)
        shortcuts.addWidget(self.web_open_external)
        lay.addLayout(shortcuts)

        self.web_bookmarks = QFrame(self.browser_page)
        self.web_bookmarks.setObjectName("mediaHubBookmarks")
        favorites_row = QHBoxLayout(self.web_bookmarks)
        favorites_row.setContentsMargins(7, 5, 7, 5)
        favorites_row.setSpacing(5)
        favorites_row.addWidget(label("Favoris", True))
        self.favorites_combo = QComboBox()
        self.favorites_combo.setSizePolicy(QSizePolicy.Policy.Expanding,
                                           QSizePolicy.Policy.Fixed)
        favorites_row.addWidget(self.favorites_combo, 1)
        for caption, callback, tip in (
                ("↗", self._favorite_go, "Ouvrir le favori"),
                ("+", self._favorite_add, "Enregistrer l'adresse actuelle"),
                ("−", self._favorite_remove, "Supprimer ce favori")):
            btn = make_button(caption, callback, tip)
            btn.setObjectName("mediaHubWebNav")
            btn.setFixedSize(26, 26)
            favorites_row.addWidget(btn)
        lay.addWidget(self.web_bookmarks)
        self._load_favorites()

        self.web_container = QVBoxLayout()
        self.web_container.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(self.web_container, 1)
        self.web_empty_card = QFrame(self.browser_page)
        self.web_empty_card.setObjectName("mediaHubWebEmpty")
        empty = QVBoxLayout(self.web_empty_card)
        empty.setContentsMargins(18, 20, 18, 20)
        empty.setSpacing(8)
        empty.addStretch(1)
        icon = QLabel("◎")
        icon.setObjectName("mediaHubWebEmptyIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.addWidget(icon)
        self.web_placeholder = label(
            "Choisis un raccourci ou saisis une adresse pour commencer.", True)
        self.web_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.web_placeholder.setWordWrap(True)
        empty.addWidget(self.web_placeholder)
        self.web_fallback = make_button("Ouvrir dans mon navigateur ↗",
                                        self._web_external,
                                        "Fonctionne même si Chromium n'est pas disponible dans QGIS")
        self.web_fallback.setObjectName("mediaHubWebFallback")
        self.web_fallback.setMinimumHeight(32)
        empty.addWidget(self.web_fallback, 0, Qt.AlignmentFlag.AlignHCenter)
        empty.addStretch(1)
        self.web_container.addWidget(self.web_empty_card)
        self.web_info = label("Navigateur intégré si Qt WebEngine est disponible.", True)
        self.web_info.setWordWrap(True)
        lay.addWidget(self.web_info)
        self.tabs.addTab(self.browser_page, "Web")

    def _style_web_controls(self):
        """Theme-aware, restrained design; no global QGIS stylesheet changes."""
        if not hasattr(self, "web_toolbar"):
            return
        dark = self._dark_mode
        fg = "#e7edf2" if dark else "#314454"
        bg = "#292f37" if dark else "#f7f9fa"
        panel = "#242a31" if dark else "#ffffff"
        edge = "#586472" if dark else "#dce5eb"
        hover = "#374553" if dark else "#e8f2f9"
        self.web_toolbar.setStyleSheet(
            "QFrame#mediaHubWebToolbar {{ background: {}; border: 1px solid {}; "
            "border-radius: 8px; }}".format(panel, edge))
        self.web_bookmarks.setStyleSheet(
            "QFrame#mediaHubBookmarks {{ background: {}; border: 1px solid {}; "
            "border-radius: 7px; }}".format(bg, edge))
        self.web_empty_card.setStyleSheet(
            "QFrame#mediaHubWebEmpty {{ background: {}; border: 1px dashed {}; "
            "border-radius: 9px; }}".format(bg, edge))
        self.web_mode_badge.setStyleSheet(
            "color: {}; font-size: 10px; font-weight: 600; padding: 3px 5px;".format(fg))
        self.web_open_external.setStyleSheet("")  # styled below with all navigation buttons
        for widget in self.browser_page.findChildren(QPushButton):
            name = widget.objectName()
            if name in ("mediaHubWebNav", "mediaHubWebQuicklink"):
                widget.setStyleSheet(
                    "QPushButton {{ background: {}; color: {}; border: 1px solid {}; "
                    "border-radius: 6px; padding: 3px 6px; }} "
                    "QPushButton:hover {{ background: {}; }}".format(bg, fg, edge, hover))
            elif name in ("mediaHubWebGo", "mediaHubWebFallback"):
                widget.setStyleSheet(
                    "QPushButton {{ background: {}; color: white; border: none; "
                    "border-radius: 6px; font-weight: 600; padding: 4px 8px; }} "
                    "QPushButton:hover {{ background: #256b9d; }}".format(
                        "#317fae" if dark else "#287fb6"))
        self.address.setStyleSheet(
            "QLineEdit {{ background: {}; color: {}; border: 1px solid {}; "
            "border-radius: 5px; padding: 4px 6px; }}".format(bg, fg, edge))
        self.web_placeholder.setStyleSheet(
            "color: {}; font-size: 12px;".format(fg))
        for widget in self.web_empty_card.findChildren(QLabel, "mediaHubWebEmptyIcon"):
            widget.setStyleSheet("font-size: 40px; color: {};".format(
                "#88b1d0" if dark else "#8aafc6"))

    def _initialize_web(self):
        if self._web_initialized:
            return
        self._web_initialized = True
        try:
            try:
                from qgis.PyQt.QtWebEngineWidgets import QWebEngineView
                from qgis.PyQt.QtWebEngineCore import QWebEngineSettings
            except ImportError:
                # WebEngine is optional and not consistently forwarded by
                # qgis.PyQt. Resolve the matching Qt binding only on demand.
                from qgis.PyQt.QtCore import PYQT_VERSION_STR
                qt_binding = "PyQt6" if PYQT_VERSION_STR.startswith("6.") else "PyQt5"
                web_widgets = importlib.import_module(qt_binding + ".QtWebEngineWidgets")
                QWebEngineView = web_widgets.QWebEngineView
                if qt_binding == "PyQt6":
                    web_core = importlib.import_module(qt_binding + ".QtWebEngineCore")
                    QWebEngineSettings = web_core.QWebEngineSettings
                else:
                    QWebEngineSettings = web_widgets.QWebEngineSettings
            self.web = QWebEngineView(self.browser_page)
            self.web.setMinimumHeight(250)
            self.web.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            st = self.web.settings()
            web_attribute = getattr(QWebEngineSettings, "WebAttribute", QWebEngineSettings)
            st.setAttribute(web_attribute.PluginsEnabled, True)
            st.setAttribute(web_attribute.JavascriptEnabled, True)
            try:
                st.setAttribute(web_attribute.FullScreenSupportEnabled, True)
            except AttributeError:
                pass
            self.web.urlChanged.connect(self._web_url_changed)
            self.web.loadFinished.connect(self._web_finished)
            self.web.page().fullScreenRequested.connect(self._web_fullscreen_requested)
            self.web_empty_card.hide()
            self.web_container.addWidget(self.web)
            self.web_mode_badge.setText("CHROMIUM")
            self.web_info.setText(tr_ui("Chromium intégré (Qt WebEngine). Certaines vidéos et connexions protégées peuvent échouer."))
            # Pas de requête Internet au démarrage tant que l'utilisateur n'a pas choisi de site.
            self._navigate(str(self.prefs.value(SETTINGS + "web_last", "https://www.youtube.com/") or "https://www.youtube.com/"))
        except Exception as exc:
            self.web = None
            self.web_mode_badge.setText("EXTERNAL")
            if language() == "en":
                self.web_placeholder.setText(
                    "Embedded browser unavailable.\n\n"
                    "Website addresses and shortcuts open in your default browser.\n\n"
                    "To enable Chromium: OSGeo4W Setup → Advanced Install → "
                    "python3-pyqtwebengine → Install → restart QGIS.\n\n"
                    "Details: {}".format(exc))
            else:
                self.web_placeholder.setText(
                    "Navigateur intégré indisponible.\n\n"
                    "Les adresses et raccourcis s'ouvrent dans ton navigateur Windows.\n\n"
                    "Pour intégrer Chromium : OSGeo4W Setup → Advanced Install → "
                    "python3-pyqtwebengine → Installer → redémarrer QGIS.\n\n"
                    "Diagnostic : {}".format(exc))
            self.web_info.setText(tr_ui("Mode navigateur externe (plus rapide pour YouTube). "
                                  "Impossible d'embarquer Chromium sans PyQtWebEngine."))

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
            self.prefs.setValue(SETTINGS + "web_last", url.toString())
            QDesktopServices.openUrl(url)

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
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_scroll = QScrollArea(page)
        page_scroll.setWidgetResizable(True)
        page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.radio_scroll = page_scroll
        page_scroll.viewport().installEventFilter(self)
        content = QWidget()
        content.setObjectName("radioContent")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(8)
        page_scroll.setWidget(content)
        page_layout.addWidget(page_scroll)
        lay.addWidget(title("Écouter la radio"))
        lay.addWidget(label("Flux directs, sans charger tout le site web.", True))
        lay.addWidget(label("Choisis un pays puis clique sur une station."))
        country_row = QHBoxLayout()
        country_row.addWidget(QLabel("Pays"))
        self.radio_country_combo = QComboBox()
        for code, display in COUNTRIES:
            self.radio_country_combo.addItem(display, code)
        country_value = str(self.prefs.value(SETTINGS + "radio_country", "FR"))
        if country_value in ("FR_TOP", "FR_ALL"):
            country_value = "FR"  # Migrate QGIS 1.5.0 settings.
        country_index = self.radio_country_combo.findData(country_value)
        if country_index >= 0:
            self.radio_country_combo.setCurrentIndex(country_index)
        country_row.addWidget(self.radio_country_combo, 1)
        self.country_refresh = make_button("↻", self._refresh_country_catalog,
                                           "Actualiser les cinq radios de ce pays")
        self.country_refresh.setFixedSize(30, 28)
        country_row.addWidget(self.country_refresh)
        lay.addLayout(country_row)
        self.country_info = label("France : cinq stations populaires.", True)
        lay.addWidget(self.country_info)
        self.radio_country_combo.currentIndexChanged.connect(self._on_country_changed)
        # Combo cachée : conserve la logique de sélection des versions précédentes.
        self.station_combo = QComboBox()
        self.station_combo.hide()
        self.radio_grid_content = QWidget()
        self.radio_grid = QGridLayout(self.radio_grid_content)
        self.radio_grid.setContentsMargins(2, 3, 2, 3)
        self.radio_grid.setSpacing(8)
        lay.addWidget(self.radio_grid_content)
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
        country_custom_row = QHBoxLayout()
        country_custom_row.addWidget(QLabel("Pays de cette station"))
        self.custom_country = QComboBox()
        for country_code, country_display in COUNTRIES:
            self.custom_country.addItem(country_display, country_code)
        country_custom_row.addWidget(self.custom_country, 1)
        lay.addLayout(country_custom_row)
        self.radio_country_combo.currentIndexChanged.connect(self._sync_custom_country)
        self._sync_custom_country()
        extras = QHBoxLayout()
        extras.addWidget(make_button("+ Ajouter", self.add_station))
        extras.addWidget(make_button("Changer de pays", self.move_station_country))
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
        """Migrate 1.x custom stations once, without losing user edits."""
        marker = SETTINGS + "user_radios_v2"
        saved = self.prefs.value(marker, None)
        is_migration = saved is None
        if is_migration:
            saved = self.prefs.value(SETTINGS + "user_radios", "[]")
        try:
            data = json.loads(saved) if isinstance(saved, str) else saved
        except (TypeError, ValueError):
            data = []
        self.user_radios = normalize_saved_stations_v2(data)
        if is_migration:
            self._save_stations()  # Never import old data a second time.
        self._country_catalogs = {"FR": [(name, RADIO_ALTERNATIVES[name][0])
                                         for name in FRANCE_FEATURED]}
        for code, _ in COUNTRIES:
            if code in ("FR", "PERSONAL"):
                continue
            raw_cache = self.prefs.value(SETTINGS + "country_cache_" + code, "[]")
            try:
                entries = json.loads(raw_cache) if isinstance(raw_cache, str) else []
            except (ValueError, TypeError):
                entries = []
            valid_entries = parse_directory_stations(entries)
            if valid_entries:
                self._country_catalogs[code] = [(item["name"], item["url"])
                                                for item in valid_entries]
                self._country_homepages[code] = {item["name"]: item["homepage"]
                                                 for item in valid_entries}
        self._update_country_radios()
        code = self.radio_country_combo.currentData()
        if code not in ("FR", "PERSONAL"):
            self._request_country_top(code)

    def _sync_custom_country(self, unused=None):
        """Preselect the current country when adding a personal station."""
        code = self.radio_country_combo.currentData() or "FR"
        index = self.custom_country.findData(code)
        if index >= 0:
            self.custom_country.setCurrentIndex(index)

    def _on_country_changed(self, unused=None):
        code = self.radio_country_combo.currentData()
        if not code:
            return
        self.prefs.setValue(SETTINGS + "radio_country", code)
        self._update_country_radios()
        if code not in ("FR", "PERSONAL"):
            self._request_country_top(code)

    def _update_country_radios(self):
        code = self.radio_country_combo.currentData() or "FR"
        builtins = list(self._country_catalogs.get(code, []))
        self._radio_builtin_count = len(builtins)
        seen = {name.casefold() for name, url in builtins}
        custom = [(name, url) for name, url in stations_for_country(self.user_radios, code)
                  if name.casefold() not in seen]
        self.radio_presets = builtins + custom
        if code == "FR":
            description = "France : cinq radios populaires, dont RTL et Franceinfo."
        elif code == "PERSONAL":
            description = "Radios non classées : attribue-leur un pays lors de l'ajout."
        elif builtins:
            description = "Cinq stations populaires sur Radio Browser (classement non officiel)."
        else:
            description = "Annuaire en ligne nécessaire pour ce pays."
        self.country_info.setProperty("mediahub_original_label", description)
        self.country_info.setText(tr_ui(description))
        self._refresh_radios()

    def _refresh_country_catalog(self):
        code = self.radio_country_combo.currentData()
        if code in ("FR", "PERSONAL"):
            self._update_country_radios()
            return
        self.prefs.setValue(SETTINGS + "country_updated_" + code, 0)
        self._request_country_top(code)

    def _request_country_top(self, code):
        """Nonblocking QGIS-network request; retains cached stations on error."""
        if code in ("FR", "PERSONAL"):
            return
        now = time.time()
        last = float(self.prefs.value(SETTINGS + "country_updated_" + code, 0) or 0)
        if self._country_catalogs.get(code) and now - last < 12 * 3600:
            return
        if self._directory_reply is not None:
            previous = self._directory_reply
            self._directory_reply = None
            previous.abort()
            previous.deleteLater()
        try:
            from qgis.core import QgsNetworkAccessManager
            params = urlencode({"countrycode": code, "order": "clickcount",
                                "reverse": "true", "hidebroken": "true", "limit": 40})
            url = QUrl("https://de1.api.radio-browser.info/json/stations/search?" + params)
            req = QNetworkRequest(url)
            req.setRawHeader(b"User-Agent", b"QGIS-Media-Hub/1.5.0 (+https://github.com/JulienH77/qgis-media-hub)")
            req.setRawHeader(b"Accept", b"application/json")
            # Qt5 sometimes defaults to manual redirects on corporate systems.
            if hasattr(QNetworkRequest.Attribute, "RedirectPolicyAttribute"):
                req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                                 QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
            reply = QgsNetworkAccessManager.instance().get(req)
            self._directory_reply = reply
            reply.finished.connect(lambda r=reply, c=code: self._country_response(r, c))
            QTimer.singleShot(12000, lambda r=reply: self._country_timeout(r))
            if not self._country_catalogs.get(code):
                self.country_info.setText(tr_ui("Recherche des cinq radios les plus consultées…"))
        except Exception as exc:
            self._set_country_error(code, str(exc))

    def _country_timeout(self, reply):
        if reply is self._directory_reply and not reply.isFinished():
            reply.abort()

    def _country_response(self, reply, code):
        if reply is not self._directory_reply:
            reply.deleteLater()
            return
        self._directory_reply = None
        try:
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise ValueError(reply.errorString())
            if status is None or int(status) != 200:
                raise ValueError("Réponse HTTP {}".format(status))
            raw = bytes(reply.readAll())
            if len(raw) > 256 * 1024:
                raise ValueError("Réponse de l'annuaire trop volumineuse")
            entries = parse_directory_stations(json.loads(raw.decode("utf-8")))
            if not entries:
                raise ValueError("Aucune radio accessible dans l'annuaire")
            self._country_catalogs[code] = [(v["name"], v["url"]) for v in entries]
            self._country_homepages[code] = {v["name"]: v["homepage"] for v in entries}
            self.prefs.setValue(SETTINGS + "country_cache_" + code,
                                json.dumps(entries, ensure_ascii=False))
            self.prefs.setValue(SETTINGS + "country_updated_" + code, time.time())
            if self.radio_country_combo.currentData() == code:
                self._update_country_radios()
        except (ValueError, TypeError, UnicodeError) as exc:
            self._set_country_error(code, str(exc))
        finally:
            reply.deleteLater()

    def _set_country_error(self, code, detail):
        if self.radio_country_combo.currentData() == code:
            if self._country_catalogs.get(code):
                self.country_info.setText(tr_ui("Liste précédemment enregistrée (actualisation impossible)."))
            else:
                self.country_info.setText(tr_ui(
                    "Annuaire inaccessible. Réessaie sur un autre réseau ou ajoute tes propres stations."))
            self.country_info.setToolTip("Radio Browser : " + str(detail))

    def _refresh_radios(self):
        current = self.station_combo.currentText()
        self.station_combo.clear()
        for name, url in self.radio_presets:
            self.station_combo.addItem(name, url)
        idx = self.station_combo.findText(current)
        if idx >= 0:
            self.station_combo.setCurrentIndex(idx)
        self._render_radio_tiles()

    def _radio_tile_icon(self, name):
        logo = {
            "RTL": "rtl.png",
            "France Inter": "france_inter.png",
            "FIP": "fip.png",
            "RMC": "rmc.png",
            "Franceinfo": "franceinfo.png",
            "Europe 1": "europe1.png",
            "NRJ": "nrj.png",
            "Nostalgie": "nostalgie.png",
            "Chérie FM": "cheriefm.png",
            "RTL2": "rtl2.png",
            "France Culture": "france_culture.png",
            "France Musique": "france_musique.png",
            "RFM": "rfm.png",
            "Skyrock": "skyrock.png",
            "Fun Radio": "fun_radio.png",
        }.get(name)
        if logo:
            return QIcon(os.path.join(os.path.dirname(__file__), "radio_icons", logo))
        # Radios sans logo : initiales lisibles + nom complet sous le carré.
        img = QPixmap(180, 180)
        img.fill(QColor("#eef2f5"))
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QColor("#34495e"))
        font = QFont()
        font.setBold(True)
        font.setPointSize(29)
        painter.setFont(font)
        rect = img.rect().adjusted(8, 8, -8, -8)
        initials = "".join(part[0] for part in name.split()[:2]).upper() or "♪"
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), initials)
        painter.end()
        return QIcon(img)

    def _render_radio_tiles(self):
        """Compact icons with a readable station name beneath every square."""
        while self.radio_grid.count():
            item = self.radio_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._station_tiles = []
        self._radio_cells = []
        for ix, (name, _) in enumerate(self.radio_presets):
            cell = QWidget(self.radio_grid_content)
            cell.setObjectName("mediaHubRadioCell")
            cell.setFixedWidth(90)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(1, 1, 1, 0)
            cell_layout.setSpacing(3)
            tile = QToolButton(cell)
            tile.setObjectName("mediaHubStationTile")
            tile.setIcon(self._radio_tile_icon(name))
            tile.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            tile.setIconSize(QSize(68, 68))
            tile.setFixedSize(80, 80)
            tile.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            tile.setToolTip("{} {}".format(tr_ui("Écouter"), name))
            tile.setAccessibleName("{} {}".format(tr_ui("Écouter"), name))
            tile.setCheckable(True)
            tile.clicked.connect(lambda checked=False, index=ix: self._select_radio_tile(index))
            caption = QLabel(name, cell)
            caption.setObjectName("mediaHubStationCaption")
            caption.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            caption.setWordWrap(True)
            caption.setFixedWidth(88)
            caption.setFixedHeight(32)
            caption.setToolTip(name)
            cell_layout.addWidget(tile, 0, Qt.AlignmentFlag.AlignHCenter)
            cell_layout.addWidget(caption, 0, Qt.AlignmentFlag.AlignHCenter)
            self._station_tiles.append(tile)
            self._radio_cells.append(cell)
        self._radio_columns = None
        self._layout_radio_tiles()
        self._highlight_radio_tile(self.station_combo.currentIndex())
        self._style_radio_tiles()

    def _layout_radio_tiles(self):
        """Arrange 90-pixel cells in responsive columns, without stretching logos."""
        if not self._station_tiles:
            return
        width = self.radio_grid_content.width()
        if hasattr(self, "radio_scroll"):
            width = self.radio_scroll.viewport().width() - 16
        cell_size = 98  # 90 px tile + 8 px grid gap
        columns = max(2, min(6, max(200, width) // cell_size))
        if (getattr(self, "_radio_columns", None) == columns
                and self.radio_grid.count() == len(self._radio_cells)):
            return
        self._radio_columns = columns
        while self.radio_grid.count():
            self.radio_grid.takeAt(0)
        for ix, cell in enumerate(self._radio_cells):
            self.radio_grid.addWidget(cell, ix // columns, ix % columns,
                                      Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.radio_grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    def _highlight_radio_tile(self, active):
        for index, button in enumerate(self._station_tiles):
            button.setChecked(index == active)

    def _select_radio_tile(self, ix):
        self.station_combo.setCurrentIndex(ix)
        self._highlight_radio_tile(ix)
        self.start_radio()

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
        country = self.radio_country_combo.currentData()
        # Do not accidentally fall back to France's RTL if an unrelated
        # foreign broadcaster has the same station name.
        candidates = (list(RADIO_ALTERNATIVES.get(self.radio_name, []))
                      if country == "FR" and
                      self.radio_name in dict(self._country_catalogs.get(country, [])) and
                      primary == dict(self._country_catalogs.get(country, [])).get(self.radio_name)
                      else [])
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
            self.radio_play_btn.setText(tr_ui("▶ Réessayer"))
            self._set_radio_status(
                "Impossible de lire {} ({} flux essayés). {}. "
                "Teste « Dans VLC » : si ça échoue aussi, le réseau bloque peut-être la radio.".format(
                    self.radio_name, len(self._radio_sources),
                    self._radio_last_error or "Aucune connexion audio"), True)
            return
        url = self._radio_sources[self._radio_attempt_index]
        self._radio_last_url = url
        self.radio_play_btn.setText(tr_ui("Connexion…"))
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
            self.radio_play_btn.setText(tr_ui("▶ Écouter"))
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
            "Franceinfo": "https://www.franceinfo.fr/",
            "Europe 1": "https://www.europe1.fr/",
            "NRJ": "https://www.nrj.fr/",
            "Nostalgie": "https://www.nostalgie.fr/",
            "Chérie FM": "https://www.cheriefm.fr/",
            "RTL2": "https://www.rtl2.fr/",
            "France Culture": "https://www.radiofrance.fr/franceculture",
            "France Musique": "https://www.radiofrance.fr/francemusique",
            "RFM": "https://www.rfm.fr/",
            "Skyrock": "https://skyrock.fm/",
            "Fun Radio": "https://www.funradio.fr/",
        }
        name = self.station_combo.currentText()
        code = self.radio_country_combo.currentData()
        homepage = self._country_homepages.get(code, {}).get(name, "")
        # A foreign station may share a name with a French preset.
        if code == "FR":
            url = sites.get(name) or str(self.station_combo.currentData() or "")
        else:
            url = homepage or str(self.station_combo.currentData() or "")
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
        self.radio_play_btn.setText(tr_ui("▶ Écouter"))
        self._set_radio_status("Test audio local : un bip discret doit être audible.")
        self.radio_detail.setText("Test sonore local, sans connexion Internet · {}".format(
            self.engine.upper()))

    def open_rtl_site(self):
        # Ouvrir dans le navigateur habituel, même si Qt WebEngine est absent.
        QDesktopServices.openUrl(QUrl("https://www.rtl.fr/direct"))

    def add_station(self):
        name = self.custom_name.text().strip()
        stream = self.custom_stream.text().strip()
        code = self.custom_country.currentData() or "PERSONAL"
        if not name or not valid_stream_url(stream):
            self._set_radio_status("Indique un nom et un flux HTTP(S) valide.", True)
            return
        if len(name) > 70:
            self._set_radio_status("Nom trop long (70 caractères maximum).", True)
            return
        # Duplicate names are allowed across *different countries*, but
        # never within the same country's displayed station grid.
        existing = {item["name"].casefold() for item in self.user_radios
                    if item["country"] == code}
        builtins = {n.casefold() for n, _ in self._country_catalogs.get(code, [])}
        if name.casefold() in existing | builtins:
            self._set_radio_status("Une station de ce nom existe déjà dans ce pays.", True)
            return
        self.user_radios.append({"name": name, "url": stream, "country": code})
        self._save_stations()
        index = self.radio_country_combo.findData(code)
        if index >= 0:
            self.radio_country_combo.setCurrentIndex(index)
        self._update_country_radios()
        self.station_combo.setCurrentIndex(self.station_combo.findText(name))
        self._highlight_radio_tile(self.station_combo.currentIndex())
        self.custom_name.clear()
        self.custom_stream.clear()
        self._set_radio_status("Station personnelle ajoutée.")

    def move_station_country(self):
        """Reassign a saved personal station without losing its stream URL."""
        name = self.station_combo.currentText()
        url = self.station_combo.currentData()
        source_code = self.radio_country_combo.currentData()
        target_code = self.custom_country.currentData()
        index = next((ix for ix, item in enumerate(self.user_radios)
                      if item["name"] == name and item["url"] == url
                      and item["country"] == source_code), -1)
        if index < 0:
            self._set_radio_status("Choisis une radio personnelle à déplacer.", True)
            return
        if source_code == target_code:
            return
        existing = {item["name"].casefold() for item in self.user_radios
                    if item["country"] == target_code}
        builtins = {n.casefold() for n, _ in self._country_catalogs.get(target_code, [])}
        if name.casefold() in existing | builtins:
            self._set_radio_status("Une station de ce nom existe déjà dans ce pays.", True)
            return
        self.user_radios[index]["country"] = target_code
        self._save_stations()
        country_index = self.radio_country_combo.findData(target_code)
        if country_index >= 0:
            self.radio_country_combo.setCurrentIndex(country_index)
        self._update_country_radios()
        self.station_combo.setCurrentIndex(self.station_combo.findText(name))
        self._highlight_radio_tile(self.station_combo.currentIndex())
        self._set_radio_status("Station déplacée vers le pays choisi.")

    def remove_station(self):
        name = self.station_combo.currentText()
        code = self.radio_country_combo.currentData()
        url = self.station_combo.currentData()
        if not name:
            return
        index = next((ix for ix, item in enumerate(self.user_radios)
                      if item["name"] == name and item["country"] == code
                      and item["url"] == url), -1)
        if index < 0:
            self._set_radio_status("Les stations proposées ne peuvent pas être supprimées.")
            return
        if self.current_kind == "radio" and self.radio_name == name:
            self.stop_radio()
        del self.user_radios[index]
        self._save_stations()
        self._update_country_radios()
        self._set_radio_status("Station « {} » supprimée.".format(name))

    def _save_stations(self):
        self.prefs.setValue(SETTINGS + "user_radios_v2",
                            json.dumps(self.user_radios, ensure_ascii=False))

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
        if QMessageBox.question(self, tr_ui("Effacer les notes"), tr_ui("Effacer toutes les notes enregistrées ?"),
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.notes.clear()
            self._save_notes()

    # ------ OPTIONS / CYCLE DE VIE ------
    def _tab_changed(self, index):
        self.prefs.setValue(SETTINGS + "tab", int(index))
        if index == 1:
            self._initialize_web()

    def _settings_dialog(self):
        """Editable settings with keyboard bindings and local preferences."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Media Hub — Paramètres")
        dialog.resize(510, 495)
        outer = QVBoxLayout(dialog)
        pages = QTabWidget(dialog)
        outer.addWidget(pages, 1)

        shortcuts_page = QWidget()
        key_layout = QVBoxLayout(shortcuts_page)
        key_layout.addWidget(label(
            "Ces touches sont actives uniquement dans l'onglet Vidéo ou le PiP. "
            "Clique dans le champ d'un raccourci, puis presse la nouvelle touche.", True))
        shortcuts_enabled = QCheckBox("Activer les raccourcis vidéo")
        shortcuts_enabled.setChecked(self._shortcut_enabled)
        key_layout.addWidget(shortcuts_enabled)
        form = QFormLayout()
        edits = {}
        for action, (caption, _) in DEFAULT_VIDEO_SHORTCUTS.items():
            edit = QKeySequenceEdit(QKeySequence(self._shortcut_bindings[action]))
            edit.setToolTip("Appuie sur la touche souhaitée (une seule combinaison).")
            edits[action] = edit
            form.addRow(tr_ui(caption), edit)
        key_layout.addLayout(form)
        reset = make_button("Raccourcis par défaut", lambda: [
            edits[action].setKeySequence(QKeySequence(default))
            for action, (_, default) in DEFAULT_VIDEO_SHORTCUTS.items()])
        key_layout.addWidget(reset)
        key_layout.addStretch(1)
        pages.addTab(shortcuts_page, "Raccourcis")

        prefs_page = QWidget()
        prefs_layout = QVBoxLayout(prefs_page)
        start_enabled = QCheckBox("Ouvrir Media Hub au démarrage de QGIS")
        start_enabled.setChecked(self.start_checkbox.isChecked())
        prefs_layout.addWidget(start_enabled)
        radio_network = QCheckBox("Utiliser le réseau / proxy QGIS pour la radio")
        radio_network.setChecked(self.use_qgis_network.isChecked())
        prefs_layout.addWidget(radio_network)
        language_row = QHBoxLayout()
        language_row.addWidget(QLabel("Langue de l'interface"))
        language_combo = QComboBox()
        language_combo.addItem("Automatique (QGIS / système)", "auto")
        language_combo.addItem("Français", "fr")
        language_combo.addItem("English", "en")
        selected_lang = str(self.prefs.value(SETTINGS + "ui_language", "auto"))
        index = language_combo.findData(selected_lang)
        language_combo.setCurrentIndex(max(0, index))
        language_row.addWidget(language_combo, 1)
        prefs_layout.addLayout(language_row)
        cinema_enabled = QCheckBox("Mode sombre dans Media Hub et le PiP")
        cinema_enabled.setChecked(self._dark_mode)
        prefs_layout.addWidget(cinema_enabled)
        controls_hidden = QCheckBox("Replier les commandes du PiP par défaut")
        controls_hidden.setChecked(self._popup._controls_hidden if self._popup else
                                   str(self.prefs.value(SETTINGS + "pip_controls_hidden", "false")).lower()
                                   in ("true", "1"))
        prefs_layout.addWidget(controls_hidden)
        prefs_layout.addWidget(label(
            "Le bouton Afficher/Masquer reste toujours visible en plein écran "
            "(H par défaut). Le mode sombre ne modifie pas le thème général de QGIS.", True))
        prefs_layout.addWidget(label(
            "Un proxy professionnel peut limiter l'accès aux radios même si "
            "la navigation Web fonctionne.", True))
        current_volume = QLabel(tr_ui("Volume actuel : {} %").format(self.volume_slider.value()))
        prefs_layout.addWidget(current_volume)
        volume = QSlider(Qt.Orientation.Horizontal)
        volume.setRange(0, 200 if self.engine == "vlc" else 100)
        volume.setValue(self.volume_slider.value())
        volume.valueChanged.connect(
            lambda value: current_volume.setText(tr_ui("Volume actuel : {} %").format(value)))
        prefs_layout.addWidget(volume)
        prefs_layout.addWidget(label(
            "Les notes, les favoris Web et le dossier vidéo sont enregistrés "
            "localement dans QGIS.", True))
        prefs_layout.addStretch(1)
        pages.addTab(prefs_page, "Préférences")

        diag_page = QWidget()
        diag_layout = QVBoxLayout(diag_page)
        diag_layout.addWidget(title("Media Hub — QGIS 3.44"))
        diag_layout.addWidget(label("Auteur : JulienH77 · Licence MIT", True))
        diag_layout.addWidget(label("Moteur média : {} — {}".format(
            self.engine.upper(), self.engine_detail or "non initialisé")))
        diag_layout.addWidget(label("Web : {}".format(
            "Qt WebEngine disponible" if self.web else
            "WebEngine absent/non chargé — navigateur externe possible")))
        diag_layout.addWidget(label(
            "France : cinq stations intégrées dont RTL et Franceinfo. Autres pays : "
            "cinq stations de Radio Browser. Radios personnelles classées par pays."))
        diag_layout.addWidget(make_button("Ouvrir les problèmes GitHub", lambda:
            QDesktopServices.openUrl(QUrl("https://github.com/JulienH77/qgis-media-hub/issues"))))
        diag_layout.addStretch(1)
        pages.addTab(diag_page, "Diagnostic")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        outer.addWidget(buttons)
        apply_localization(dialog)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = {}
        for action, edit in edits.items():
            value = edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            if not value or "," in value or value in ("Esc", "Escape", "Tab", "Backtab"):
                QMessageBox.warning(self, tr_ui("Media Hub — Raccourcis"),
                                    tr_ui("Raccourci invalide pour « {} ». Définis une combinaison unique, hors Échap et Tab.").format(
                                        tr_ui(DEFAULT_VIDEO_SHORTCUTS[action][0])))
                return
            values[action] = value
        if len(set(values.values())) != len(values):
            QMessageBox.warning(self, tr_ui("Media Hub — Raccourcis"),
                                tr_ui("Une même combinaison a été attribuée plusieurs fois."))
            return
        self._shortcut_bindings = values
        self._shortcut_enabled = shortcuts_enabled.isChecked()
        self.prefs.setValue(SETTINGS + "keyboard_shortcuts", json.dumps(values, ensure_ascii=False))
        self.prefs.setValue(SETTINGS + "keyboard_enabled", self._shortcut_enabled)
        self._rebuild_video_shortcuts()
        self.start_checkbox.setChecked(start_enabled.isChecked())
        self.use_qgis_network.setChecked(radio_network.isChecked())
        self.volume_slider.setValue(volume.value())
        self.prefs.setValue(SETTINGS + "ui_language", language_combo.currentData())
        self._dark_mode = cinema_enabled.isChecked()
        self.prefs.setValue(SETTINGS + "dark_mode", self._dark_mode)
        self._apply_theme()
        self._apply_language()
        self.prefs.setValue(SETTINGS + "pip_controls_hidden", controls_hidden.isChecked())
        if self._popup is not None:
            self._popup.set_controls_hidden(controls_hidden.isChecked())

    def shutdown(self):
        if self._directory_reply is not None:
            pending = self._directory_reply
            self._directory_reply = None
            pending.abort()
            pending.deleteLater()
        if self._radio_relay:
            self._radio_relay.shutdown()
            self._radio_relay = None
        if self._keyboard_filter_installed:
            app = QApplication.instance()
            if app is not None:
                app.removeEventFilter(self)
            self._keyboard_filter_installed = False
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
